import sqlite3

def migrate():
    try:
        print("Connecting to database...")
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        print("Creating export_tokens table...")
        # Create table if not exists (matching the model definition)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_path TEXT,
                created_at TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0
            )
        """)
        
        # Verify creation
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='export_tokens'")
        if cursor.fetchone():
            print("Table 'export_tokens' confirmed.")
        
        conn.commit()
        conn.close()
        print("Migration complete.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    migrate()
