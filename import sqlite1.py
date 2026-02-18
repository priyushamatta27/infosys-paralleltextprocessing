import sqlite3

def create_connection():
    conn = sqlite3.connect("text_data.db")
    return conn

def create_table():
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS texts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT,
        word_count INTEGER,
        pattern_found TEXT
    )
    """)

    conn.commit()
    conn.close()

def insert_text(content, word_count, pattern_found):
    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO texts (content, word_count, pattern_found)
    VALUES (?, ?, ?)
    """, (content, word_count, pattern_found))

    conn.commit()
    conn.close()
