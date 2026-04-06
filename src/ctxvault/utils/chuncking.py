"""Chunking strategies for text splitting.

Three strategies are available:
- Markdown chunking: splits on markdown headers, preserving header hierarchy.
- Recursive character splitting: tries paragraph -> line -> word splits.
- Fixed-size splitting: simple word-based windowed chunks (original algorithm).

NOTE: Markdown chunking requires raw markdown input with headers intact.
The text_extraction module for .md files currently strips markdown formatting,
so if the text has already been processed through text_extraction, the markdown
strategy will not find headers and will gracefully fall back to recursive splitting.
To use markdown chunking effectively, pass raw markdown text directly.
"""

from __future__ import annotations

import re


def chunking(
    text: str,
    chunk_size: int = 400,
    overlap: int = 100,
    file_type: str | None = None,
) -> list[str]:
    """Split text into chunks using a strategy based on file_type.

    Args:
        text: The input text to chunk.
        chunk_size: Maximum number of words per chunk.
        overlap: Number of overlapping words between consecutive fixed-size chunks.
        file_type: File extension (e.g. ".md", ".txt"). When None, uses recursive strategy.

    Returns:
        A list of non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    if file_type == ".md":
        return _chunk_markdown(text, chunk_size, overlap)

    # .txt, .pdf, .docx, None, and anything else -> recursive
    return _chunk_recursive(text, chunk_size, overlap)


def _chunk_markdown(
    text: str, chunk_size: int, overlap: int
) -> list[str]:
    """Split markdown text on headers, preserving header hierarchy as context prefixes.

    Each section becomes a chunk prefixed with its full header hierarchy.
    Sections exceeding chunk_size words are further split using the recursive strategy.
    Falls back to recursive splitting if no markdown headers are found.
    """
    # Match lines that start with one or more '#' characters followed by a space
    header_pattern = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)

    headers = list(header_pattern.finditer(text))

    if not headers:
        # No markdown headers found (text may have been stripped by text_extraction).
        # Fall back to recursive strategy.
        return _chunk_recursive(text, chunk_size, overlap)

    # Build sections: each section is (header_hierarchy_prefix, body_text)
    sections: list[tuple[str, str]] = []

    # Track the current header stack for hierarchy context
    # Each entry is (level, header_text)
    header_stack: list[tuple[int, str]] = []

    # Collect any text before the first header as a preamble
    preamble = text[: headers[0].start()].strip()
    if preamble:
        sections.append(("", preamble))

    for i, match in enumerate(headers):
        level = len(match.group(1))
        header_text = match.group(2).strip()

        # Pop headers from the stack that are at the same level or deeper
        header_stack = [(lvl, txt) for lvl, txt in header_stack if lvl < level]
        header_stack.append((level, header_text))

        # Build the hierarchy prefix from the stack
        hierarchy_prefix = " > ".join(txt for _, txt in header_stack)

        # Extract body text between this header and the next header (or end of text)
        body_start = match.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[body_start:body_end].strip()

        sections.append((hierarchy_prefix, body))

    chunks: list[str] = []

    for prefix, body in sections:
        if prefix:
            section_text = f"{prefix}\n{body}" if body else prefix
        else:
            section_text = body

        word_count = len(section_text.split())

        if word_count <= chunk_size:
            if section_text.strip():
                chunks.append(section_text.strip())
        else:
            # Section too large; split body with recursive strategy and prepend prefix
            sub_chunks = _chunk_recursive(body if body else section_text, chunk_size, overlap)
            for sub in sub_chunks:
                if prefix:
                    chunk = f"{prefix}\n{sub}"
                else:
                    chunk = sub
                if chunk.strip():
                    chunks.append(chunk.strip())

    return chunks


def _chunk_recursive(
    text: str, chunk_size: int, overlap: int
) -> list[str]:
    """Recursively split text by paragraphs, then lines, then words.

    Tries splitting by double newlines (paragraphs) first. If any resulting piece
    exceeds chunk_size words, splits those pieces by single newlines (lines).
    If still too large, falls back to fixed-size word splitting with overlap.
    """
    if not text or not text.strip():
        return []

    # If the entire text fits, return it as a single chunk
    if len(text.split()) <= chunk_size:
        return [text.strip()]

    # Step 1: split by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    pieces = _merge_pieces(paragraphs, chunk_size)

    # Step 2: any piece still too large -> split by lines
    refined: list[str] = []
    for piece in pieces:
        if len(piece.split()) <= chunk_size:
            refined.append(piece)
        else:
            lines = [ln.strip() for ln in piece.split("\n") if ln.strip()]
            refined.extend(_merge_pieces(lines, chunk_size))

    # Step 3: any piece still too large -> fixed-size word split
    final: list[str] = []
    for piece in refined:
        if len(piece.split()) <= chunk_size:
            final.append(piece)
        else:
            final.extend(_chunk_fixed(piece, chunk_size, overlap))

    return [c for c in final if c.strip()]


def _merge_pieces(pieces: list[str], chunk_size: int) -> list[str]:
    """Merge small consecutive pieces together up to chunk_size words.

    Greedily combines pieces so that each merged chunk stays within the word limit.
    """
    merged: list[str] = []
    current: list[str] = []
    current_words = 0

    for piece in pieces:
        piece_words = len(piece.split())
        if current and current_words + piece_words > chunk_size:
            merged.append("\n\n".join(current))
            current = [piece]
            current_words = piece_words
        else:
            current.append(piece)
            current_words += piece_words

    if current:
        merged.append("\n\n".join(current))

    return merged


def _chunk_fixed(
    text: str, chunk_size: int = 400, overlap: int = 100
) -> list[str]:
    """Fixed-size word-based splitting with overlap.

    This is the original chunking algorithm, retained as an internal fallback.
    Splits text into windows of chunk_size words, stepping by (chunk_size - overlap).
    """
    words = text.split()
    if not words:
        return []

    step = max(chunk_size - overlap, 1)
    chunks = [
        " ".join(words[i : i + chunk_size])
        for i in range(0, len(words), step)
    ]
    return [c for c in chunks if c.strip()]
