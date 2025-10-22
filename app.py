import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session
import uuid

app = Flask(__name__)
app.secret_key = "multipartyllm"

CONV_DIR = "json/"
CONDITIONS = ["supportive", "refutational", "prebunking"]

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


# --------------------------
# Database setup and helpers
# --------------------------

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prolific_pid TEXT UNIQUE,
            participant_number INTEGER UNIQUE,
            condition TEXT,
            conversation_index INTEGER,
            status TEXT DEFAULT 'started',
            created_at TEXT
        )
    """)
    #Add claim_token if it doesn't exist
    cols = [r[1] for r in conn.execute("PRAGMA table_info(participants);")]
    if "claim_token" not in cols:
        conn.execute("ALTER TABLE participants ADD COLUMN claim_token TEXT;")
        conn.commit()

    conn.close()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


init_db()


# --------------------------
# Helper: Load conversation
# --------------------------

def load_conversation_from_file(condition, index):
    folder = os.path.join(CONV_DIR, condition)
    filename = f"conversation_{condition}{index}.json"
    filepath = os.path.join(folder, filename)
    if not os.path.exists(filepath):
        return ["Error: Conversation file not found"]
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------
# Routes
# --------------------------

@app.route("/")
def start_page():
    prolific_pid = request.args.get("PROLIFIC_PID")
    if not prolific_pid:
        prolific_pid = f"TEST_{uuid.uuid4().hex[:8]}" #for testing 
    
    # store it in session for later use
    session['prolific_pid'] = prolific_pid
    
    return render_template("index.html") 
@app.route("/assign")
def assign_condition():
    prolific_pid = session.get("prolific_pid")
    if not prolific_pid:
        return redirect(url_for("start_page"))

    claim_token = session.get("claim_token")
    if not claim_token:
        # Generate a random, session-unique token
        claim_token = str(uuid.uuid4())
        session['claim_token'] = claim_token

    conn = get_db_connection()
    try:
        conn.execute("BEGIN EXCLUSIVE")
        participant = conn.execute(
            "SELECT * FROM participants WHERE prolific_pid = ?", (prolific_pid,)
        ).fetchone()
        if participant:
            
            if participant['claim_token'] == claim_token:
                session['participant_number'] = participant['participant_number']
                session['condition'] = participant['condition']
                session['conversation_index'] = participant['conversation_index']
            else:
            
                conn.close()
                return "Already assigned in another session. Please refresh.", 409
        else:
            # Condition balancing (count only completed participants)
            condition_counts = {
                c: conn.execute(
                    "SELECT COUNT(*) FROM participants WHERE condition = ?", (c,)
                ).fetchone()[0]
                for c in CONDITIONS
            }
            condition = min(condition_counts, key=condition_counts.get)
            convo_counts = {
                i: conn.execute(
                    "SELECT COUNT(*) FROM participants WHERE condition = ? AND conversation_index = ?",
                    (condition, i)
                ).fetchone()[0]
                for i in [1, 2, 3]
            }
            convo_index = min(convo_counts, key=convo_counts.get)
            last_num = conn.execute("SELECT MAX(participant_number) FROM participants").fetchone()[0] or 0
            new_number = last_num + 1

            conn.execute("""
                INSERT INTO participants (prolific_pid, participant_number, condition, conversation_index, status, created_at, claim_token)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (prolific_pid, new_number, condition, convo_index, "started", datetime.utcnow().isoformat(), claim_token))

            session['participant_number'] = new_number
            session['condition'] = condition
            session['conversation_index'] = convo_index

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Error assigning participant: {e}", 500

    conn.close()
    return redirect(url_for("conversation_entry"))



@app.route("/conversation")
def conversation_entry():
    if "prolific_pid" not in session:
        return redirect(url_for("home"))

    condition = session['condition']
    convo_index = session['conversation_index']

    history = load_conversation_from_file(condition, convo_index)
    finished = False

    return render_template(
        "conversation.html",
        history=history,
        mode=condition,
        step=1,
        total=1,
        finished=finished,
        participant_number=session.get('participant_number'),
        prolific_pid=session.get('prolific_pid'),
    )


@app.route("/finish")
def finish():
    prolific_pid = session.get("prolific_pid")
    participant_number = session.get("participant_number")

    if prolific_pid:
        conn = get_db_connection()
        conn.execute(
            "UPDATE participants SET status = ? WHERE prolific_pid = ? and participant_number = ?",
            ("completed",prolific_pid, participant_number) 
        )
        conn.commit()
        conn.close()

    session['finished'] = True
    return '', 200 



# --------------------------
# Debug: See participants
# --------------------------

@app.route("/admin/participants")
def show_participants():
    conn = get_db_connection()
    participants = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    conn.close()
    return {
        "participants": [dict(p) for p in participants]
    }


# --------------------------
# Debug: Direct conversation access
# --------------------------

@app.route("/conversation/<condition_name>/<int:index>")
def conversation_entry_direct(condition_name, index):
    if condition_name not in CONDITIONS or not 1 <= index <= 3:
        return "Invalid conversation", 404

    history = load_conversation_from_file(condition_name, index)
    finished = False

    return render_template(
        "conversation.html",
        history=history,
        mode=condition_name,
        step=index,
        total=1,
        finished=finished,
        participant_number=None,
        prolific_pid=None,
    )

# --------------------------
# Run the app
# --------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=3001, debug=True)
