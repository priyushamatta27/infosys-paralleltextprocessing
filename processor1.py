from concurrent.futures import ThreadPoolExecutor

# function to save a chunk
def save_chunk(chunk, num):
    with open(f"chunk_{num}.txt", "w") as f:
        f.writelines(chunk)

def chunk_file(file_name, chunk_size):

    with open(file_name, "r") as f:
        lines = f.readlines()

    chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]

    with ThreadPoolExecutor() as executor:
        for i, chunk in enumerate(chunks, 1):
            executor.submit(save_chunk, chunk, i)

# run program
chunk_file("product_reviews_50000.csv", 2000)
    with ThreadPoolExecutor() as executor:
        executor.map(process_text, sample_texts)

