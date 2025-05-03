import sqlite3
import hashlib
import getpass
import time
import os
import requests
import random
from datetime import datetime

# ------------------ UTILS ------------------
DB_FILE = 'platform.db'
LIGHTHOUSE_API_KEY = "03e85330.b6a227873ffa49d9a9b6899782736cdf"  # TODO: Replace with your Lighthouse API key
LIGHTHOUSE_ENDPOINT = "https://node.lighthouse.storage/api/v0/add"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ------------------ AUTH ------------------
def register(role):
    print(f"Registering new {role}...")
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    email = input("Email (optional): ")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    table = 'users' if role == 'annotator' else 'contributors'

    try:
        c.execute(f'''
            INSERT INTO {table} (username, password_hash, email)
            VALUES (?, ?, ?)
        ''', (username, hash_password(password), email))
        conn.commit()
        print("Registration successful.\n")
    except sqlite3.IntegrityError:
        print("Username already exists.\n")
    conn.close()

def login(role):
    print(f"Logging in as {role}...")
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    table = 'users' if role == 'annotator' else 'contributors'

    c.execute(f'''
        SELECT id, password_hash FROM {table} WHERE username = ?
    ''', (username,))
    row = c.fetchone()
    conn.close()

    if row and row[1] == hash_password(password):
        print(f"Login successful. Welcome {username}!\n")
        return {'role': role, 'id': row[0], 'username': username}
    else:
        print("Invalid credentials.\n")
        return None

# ------------------ MENUS ------------------
def main_menu():
    while True:
        print("\n=== Crowdsourced Annotation Platform ===")
        print("1. Register as Annotator")
        print("2. Register as Contributor")
        print("3. Login as Annotator")
        print("4. Login as Contributor")
        print("5. Exit")
        choice = input("Select an option: ")

        if choice == '1':
            register('annotator')
        elif choice == '2':
            register('contributor')
        elif choice == '3':
            session = login('annotator')
            if session:
                annotator_menu(session)
        elif choice == '4':
            session = login('contributor')
            if session:
                contributor_menu(session)
        elif choice == '5':
            print("Exiting... Goodbye!")
            break
        else:
            print("Invalid input. Try again.")

def contributor_menu(session):
    while True:
        print(f"\n[Logged in as Contributor: {session['username']}]")
        print("1. Upload Dataset")
        print("2. View Balance")
        print("3. View Results")
        print("4. Logout")
        choice = input("Select an option: ")

        if choice == '1':
            upload_dataset(session)
        elif choice == '2':
            view_balance(session)
        elif choice == '3':
            view_results(session)
        elif choice == '4':
            print("Logging out...")
            break
        else:
            print("Invalid input.")

def annotator_menu(session):
    while True:
        print(f"\n[Logged in as Annotator: {session['username']}]")
        print("1. Annotate Assigned Data")
        print("2. View Earnings")
        print("3. Logout")
        choice = input("Select an option: ")

        if choice == '1':
            annotate_data(session)
        elif choice == '2':
            view_earnings(session)
        elif choice == '3':
            print("Logging out...")
            break
        else:
            print("Invalid input.")

# ------------------ UPLOAD ------------------
def upload_file_to_ipfs(filepath):
    with open(filepath, 'rb') as f:
        files = {'file': (os.path.basename(filepath), f)}
        headers = {'Authorization': f'Bearer {LIGHTHOUSE_API_KEY}'}
        response = requests.post(LIGHTHOUSE_ENDPOINT, files=files, headers=headers)
        if response.status_code == 200:
            return response.json()['Hash']
        else:
            print(f"Failed to upload {filepath} to IPFS. Status: {response.status_code}")
            return None

def upload_dataset(session):
    contributor_id = session['id']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    name = input("Dataset name: ")
    description = input("Description: ")
    folder = input("Path to folder with files: ").strip()
    total_value = float(input("Total value (for full dataset): "))

    files = sorted(set(
        f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))
    ))
    if not files:
        print("No files found in folder.")
        return

    value_per_file = total_value / len(files)

    # Check contributor wallet balance
    c.execute("SELECT wallet_balance FROM contributors WHERE id = ?", (contributor_id,))
    balance = c.fetchone()[0]
    if balance < total_value:
        print(f"Insufficient balance. Available: {balance}")
        return

    # Deduct from wallet
    c.execute("UPDATE contributors SET wallet_balance = wallet_balance - ? WHERE id = ?", (total_value, contributor_id))

    # Insert dataset
    c.execute('''
        INSERT INTO datasets (contributor_id, name, description, total_value)
        VALUES (?, ?, ?, ?)
    ''', (contributor_id, name, description, total_value))
    dataset_id = c.lastrowid

    # Fetch all annotator IDs
    c.execute("SELECT id FROM users")
    annotators = [row[0] for row in c.fetchall()]
    if len(annotators) == 0:
        print("No annotators found. Aborting.")
        conn.rollback()
        return

    num_annotators = len(annotators)

    for idx, file in enumerate(files):
        # Skip if already inserted
        c.execute('''
            SELECT 1 FROM data
            WHERE dataset_id = ? AND file_name = ?
        ''', (dataset_id, file))
        if c.fetchone():
            print(f"Skipping duplicate file: {file}")
            continue

        path = os.path.join(folder, file)
        print(f"Uploading {file}...")
        cid = upload_file_to_ipfs(path)
        if not cid:
            continue

        # Insert file into data table
        c.execute('''
            INSERT INTO data (dataset_id, cid, file_name, value)
            VALUES (?, ?, ?, ?)
        ''', (dataset_id, cid, file, value_per_file))
        data_id = c.lastrowid

        # Assign to one annotator evenly
        assigned_annotator = annotators[idx % num_annotators]
        c.execute('''
            INSERT INTO data_annotator (data_id, annotator_id, status)
            VALUES (?, ?, 'PENDING')
        ''', (data_id, assigned_annotator))

    conn.commit()
    conn.close()
    print("✅ Dataset uploaded and data assigned to annotators.")

# ------------------ ANNOTATE ------------------
import shutil

def annotate_data(session):
    annotator_id = session['id']
    username = session['username']
    download_folder = f"./downloads_{username}/"
    os.makedirs(download_folder, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Fetch all pending files assigned to this annotator
    c.execute('''
        SELECT da.id, d.cid, d.file_name, d.value
        FROM data_annotator da
        JOIN data d ON da.data_id = d.id
        WHERE da.annotator_id = ? AND da.status = 'PENDING'
    ''', (annotator_id,))
    rows = c.fetchall()

    if not rows:
        print("🎉 No pending annotations. You're all caught up!")
        conn.close()
        return

    print("\n📄 Files assigned to you for annotation:")
    for idx, row in enumerate(rows, start=1):
        print(f"{idx}. {row[2]} - ${row[3]:.2f}")

    try:
        selection = int(input("Enter the number of the file you want to annotate: "))
        if selection < 1 or selection > len(rows):
            raise ValueError
    except ValueError:
        print("Invalid selection.")
        conn.close()
        return

    assignment_id, cid, file_name, value = rows[selection - 1]
    file_url = f"https://gateway.lighthouse.storage/ipfs/{cid}"
    download_path = os.path.join(download_folder, file_name)

    print(f"⬇️ Downloading {file_name} from IPFS...")
    try:
        response = requests.get(file_url, stream=True)
        if response.status_code == 200:
            with open(download_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            print(f"✅ File saved to {download_path}")
        else:
            print(f"Failed to download. Status: {response.status_code}")
            conn.close()
            return
    except Exception as e:
        print(f"Error downloading file: {e}")
        conn.close()
        return

    # Prompt for score
    try:
        score = int(input("Enter your rating (1–10): "))
        if not (1 <= score <= 10):
            raise ValueError
    except ValueError:
        print("Invalid rating. Must be an integer between 1 and 10.")
        conn.close()
        return

    # Save annotation
    timestamp = datetime.utcnow().isoformat()
    c.execute('''
        UPDATE data_annotator
        SET status = 'ANNOTATED', grade = ?, timestamp = ?
        WHERE id = ?
    ''', (score, timestamp, assignment_id))

    # Credit to wallet
    c.execute('''
        UPDATE users SET wallet_balance = wallet_balance + ?
        WHERE id = ?
    ''', (value, annotator_id))

    conn.commit()
    conn.close()

    print(f"✅ Saved rating {score} for {file_name}. ${value:.2f} added to your balance.")

# ------------------ VIEW MONEY ------------------
def view_earnings(session):
    annotator_id = session['id']

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT wallet_balance FROM users WHERE id = ?", (annotator_id,))
    balance = c.fetchone()[0]

    conn.close()
    print(f"\n💰 Your total earnings: ${balance:.2f}")

def view_balance(session):
    contributor_id = session['id']

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("SELECT wallet_balance FROM contributors WHERE id = ?", (contributor_id,))
    balance = c.fetchone()[0]

    conn.close()
    print(f"\n💰 Your current balance: ${balance:.2f}")

# ------------------ VIEW RESULTS ------------------
def view_results(session):
    contributor_id = session['id']
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Fetch all datasets by this contributor
    c.execute("SELECT id, name FROM datasets WHERE contributor_id = ?", (contributor_id,))
    datasets = c.fetchall()

    if not datasets:
        print("📂 You have not uploaded any datasets yet.")
        conn.close()
        return

    for dataset_id, dataset_name in datasets:
        print(f"\n📊 Dataset: {dataset_name}")
        print("-" * 60)

        # Fetch all files in this dataset
        c.execute('''
            SELECT d.id, d.file_name
            FROM data d
            WHERE d.dataset_id = ?
        ''', (dataset_id,))
        files = c.fetchall()

        for data_id, file_name in files:
            # Get the grade for this file (only one expected)
            c.execute('''
                SELECT grade FROM data_annotator
                WHERE data_id = ?
            ''', (data_id,))
            grade = c.fetchone()

            if not grade or grade[0] is None:
                grade_display = "<not annotated>"
            else:
                grade_display = str(grade[0])

            print(f"{file_name:<40}  Score: {grade_display}")

    conn.close()

# ------------------ MAIN ------------------
if __name__ == "__main__":
    main_menu()
