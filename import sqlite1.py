import sqlite3
import csv

# connect to database (creates if not exists)
conn = sqlite3.connect("reviews.db")
cursor = conn.cursor()

# create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER,
    product_name TEXT,
    rating INTEGER,
    review_text TEXT
)
""")

# open csv file
with open("product_reviews_50000.csv", "r", encoding="utf-8") as file:
    reader = csv.reader(file)

    next(reader)  # skip header

    for row in reader:
        cursor.execute(
            "INSERT INTO reviews VALUES (?, ?, ?, ?)",
            (row[0], row[1], row[2], row[3])
        )

# save changes
conn.commit()

# print confirmation
print("CSV data successfully inserted into database")

# close connection
conn.close()
