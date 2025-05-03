import sqlite3
import hashlib

DB_FILE = 'platform.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def populate():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Annotators
    annotators = [
        ("ano1", "ano1", "ano1@example.com"),
        ("ano2", "ano2", "ano2@example.com"),
        ("ano3", "ano3", "ano3@example.com"),
        ("ano4", "ano4", "ano4@example.com"),
    ]

    for username, password, email in annotators:
        try:
            c.execute('''
                INSERT INTO users (username, password_hash, email)
                VALUES (?, ?, ?)
            ''', (username, hash_password(password), email))
        except sqlite3.IntegrityError:
            print(f"Annotator {username} already exists, skipping.")

    # Contributors
    contributors = [
        ("con1", "con1", "con1@example.com"),
        ("con2", "con2", "con2@example.com"),
    ]

    for username, password, email in contributors:
        try:
            c.execute('''
                INSERT INTO contributors (username, password_hash, email)
                VALUES (?, ?, ?)
            ''', (username, hash_password(password), email))
        except sqlite3.IntegrityError:
            print(f"Contributor {username} already exists, skipping.")

    conn.commit()
    conn.close()
    print("✅ Users populated successfully.")

if __name__ == "__main__":
    populate()
