class UnsupportedFileTypeError(Exception):
    """Raised when a file type is not supported by the extractor."""
    pass

class ExtractionError(Exception):
    """Raised when text extraction fails for reasons other than file type."""
    pass
