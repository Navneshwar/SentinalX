# check_db.py
import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sentinelx.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='risk_records'")
if cursor.fetchone():
    print("✅ Database table exists")
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM risk_records")
    count = cursor.fetchone()[0]
    print(f"📊 Total risk records: {count}")
    
    # Show latest records
    if count > 0:
        cursor.execute("SELECT id, session_id, risk_score, timestamp FROM risk_records ORDER BY timestamp DESC LIMIT 5")
        records = cursor.fetchall()
        print("\n📝 Latest 5 records:")
        for record in records:
            print(f"   ID: {record[0]}, Session: {record[1][:8]}..., Risk: {record[2]}, Time: {record[3]}")
else:
    print("❌ Table not found - no data yet")

conn.close()