import sqlite3
import json

conn = sqlite3.connect('backend/cache/telemetry.db')
cursor = conn.cursor()

# Get all tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables found:", [t[0] for t in tables])
print()

# Check each table
for table in tables:
    table_name = table[0]
    print(f"\n=== Table: {table_name} ===")
    
    # Get row count
    count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"Total rows: {count}")
    
    if count > 0:
        # Get column names
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
        columns = [description[0] for description in cursor.description]
        print(f"Columns: {columns}")
        
        # Get recent rows
        print(f"\nRecent entries (last 3):")
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 3")
        for row in cursor.fetchall():
            print(row)

conn.close()
