from concurrent.futures import ThreadPoolExecutor
from text_processor import clean_text, count_words
from patterns import find_pattern
from database import create_table, insert_text

sample_texts = [
    "Python is powerful for text processing.",
    "Database integration is important.",
    "Parallel processing improves performance."
]

keyword = "processing"

def process_text(text):
    cleaned = clean_text(text)
    word_count = count_words(cleaned)
    pattern_status = find_pattern(cleaned, keyword)

    insert_text(cleaned, word_count, pattern_status)

    print(f"Processed: {cleaned}")
    print(f"Word Count: {word_count}, Pattern: {pattern_status}\n")

if __name__ == "__main__":
    create_table()

    with ThreadPoolExecutor() as executor:
        executor.map(process_text, sample_texts)
