import re

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def count_words(text):
    words = text.split()
    return len(words)
