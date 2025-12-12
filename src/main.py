from ctxvault.utils.text_extraction import extract_text
from ctxvault.utils.chuncking import chunking

if __name__ == "__main__":
    text = extract_text(path='./data/test.md') 
    
    print(chunking(text, chunk_size=50))