from typing import List

def chunking(text:str, chunk_size: int = 700, overlap: int = 100)->List[str]:
    text_splitted = text.split(" ")
    chunks = [text_splitted[i:chunk_size]for i in range (0, len(text_splitted), chunk_size-overlap)]
    return chunks