from pypdf import PdfReader
from docx import Document
import markdown
from strip_tags import strip_tags
from pathlib import PurePosixPath
from ctxvault.core.exceptions import UnsupportedFileTypeError, ExtractionError

SUPPORTED_EXT = {'.txt', '.md', '.pdf', '.docx'}

def _extract_from_txt(path: str)->str:
    try:
        with open(file=path, mode='r', encoding='utf-8') as f:
            txt_content = f.read()
        return txt_content
    except Exception as e:
        raise ExtractionError(f"Failed to extract .txt {path}: {e}")

def _extract_from_md(path: str)->str:
    try:
        with open(file=path, mode='r', encoding='utf-8') as f:
            md_content = markdown.markdown(f.read())
        return strip_tags(input=md_content).strip()
    except Exception as e:
        raise ExtractionError(f"Failed to extract .md {path}: {e}")

def _extract_from_pdf(path: str)->str:
    try:
        reader = PdfReader(stream=path)
        pdf_content = ''.join([(p.extract_text() or '').strip() for p in reader.pages])
        return pdf_content
    except Exception as e:
        raise ExtractionError(f"Failed to extract .pdf {path}: {e}")

def _extract_from_docx(path: str)->str:
    try:
        f = open(file=path, mode='rb')
        document = Document(f)
        docx_content = ''.join([p.text.strip() for p in document.paragraphs if p.text.strip])
        f.close()
        return docx_content
    except Exception as e:
        raise ExtractionError(f"Failed to extract .docx {path}: {e}")

def extract_text(path: str)->str:
    suffix = PurePosixPath(path).suffix

    if suffix not in SUPPORTED_EXT:
        raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")
    
    if suffix == '.txt':
        return _extract_from_txt(path=path)
    elif suffix == '.md':
        return _extract_from_md(path=path)
    elif suffix == '.pdf':
        return _extract_from_pdf(path=path)
    elif suffix == '.docx':
        return _extract_from_docx(path=path)