import logging
import transformers
from sentence_transformers import SentenceTransformer

MODEL: SentenceTransformer = None

def get_model():
    global MODEL
    if MODEL is None:
        loggers = [
            "sentence_transformers",
            "transformers",
            "transformers.modeling_utils",
            "transformers.utils.logging",
            "huggingface_hub",
            "huggingface_hub.file_download",
            "huggingface_hub._commit_api",
        ]
        original_levels = {}
        for name in loggers:
            logger = logging.getLogger(name)
            original_levels[name] = logger.level
            logger.setLevel(logging.ERROR)

        original_verbosity = transformers.logging.get_verbosity()
        transformers.logging.set_verbosity_error()
        transformers.logging.disable_progress_bar()

        try:
            MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        finally:
            transformers.logging.set_verbosity(original_verbosity)
            transformers.logging.enable_progress_bar()
            for name, level in original_levels.items():
                logging.getLogger(name).setLevel(level)

    return MODEL

def embed_list(chunks: list[str]) -> list[list[float]]:
    return get_model().encode(sentences=chunks, show_progress_bar=False).tolist()