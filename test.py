import sqlite3
from datetime import datetime

conn = sqlite3.connect("database.db")
conn.execute("""
INSERT INTO participants (prolific_pid, participant_number, condition, conversation_index, status, created_at)
VALUES (?, ?, ?, ?, ?, ?)
""", ("P4", 4, "supportive", 1, "started", datetime.utcnow().isoformat()))
conn.commit()
conn.close()
