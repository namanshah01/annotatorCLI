import sqlite3

DB_FILE = 'platform.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Annotators (users)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            email TEXT,
            wallet_balance REAL DEFAULT 0.0
        )
    ''')

    # Contributors
    c.execute('''
        CREATE TABLE IF NOT EXISTS contributors (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            email TEXT,
            wallet_balance REAL DEFAULT 100.0
        )
    ''')

    # Datasets
    c.execute('''
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY,
            contributor_id INTEGER,
            name TEXT,
            description TEXT,
            total_value REAL,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY (contributor_id) REFERENCES contributors(id)
        )
    ''')

    # Data files
    c.execute('''
        CREATE TABLE IF NOT EXISTS data (
            id INTEGER PRIMARY KEY,
            dataset_id INTEGER,
            cid TEXT,
            file_name TEXT,
            value REAL,
            is_labeled BOOLEAN DEFAULT 0,
            label INTEGER,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        )
    ''')

    # Data-annotator assignments
    c.execute('''
        CREATE TABLE IF NOT EXISTS data_annotator (
            id INTEGER PRIMARY KEY,
            data_id INTEGER,
            annotator_id INTEGER,
            status TEXT DEFAULT 'PENDING',
            grade INTEGER,
            timestamp TEXT,
            FOREIGN KEY (data_id) REFERENCES data(id),
            FOREIGN KEY (annotator_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ All tables initialized successfully.")

if __name__ == "__main__":
    init_db()
