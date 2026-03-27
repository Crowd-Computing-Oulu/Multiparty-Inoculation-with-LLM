import os
import io
import csv
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, Response
import uuid
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multipartyllm")

CONV_DIR = "json/"
CONDITIONS = ["control", "supportive", "refutational", "prebunking", "combined"]

# DB_PATH: use /data/ for Railway persistent volume, local file for development
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "database.db"))


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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER,
            phase TEXT,
            item_key TEXT,
            value TEXT,
            created_at TEXT,
            FOREIGN KEY (participant_id) REFERENCES participants(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER,
            event TEXT,
            timestamp TEXT,
            FOREIGN KEY (participant_id) REFERENCES participants(id)
        )
    """)
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
# Helper: Store survey responses
# --------------------------

def log_event(participant_id, event):
    """Log a timestamped event for a participant."""
    if not participant_id:
        return
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO events (participant_id, event, timestamp) VALUES (?, ?, ?)",
        (participant_id, event, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def store_survey_responses(participant_id, phase, data):
    """Flatten and store survey JSON data into the responses table."""
    conn = get_db_connection()
    now = datetime.utcnow().isoformat()
    for key, value in data.items():
        if isinstance(value, dict):
            # Matrix / nested question — flatten
            for inner_key, inner_value in value.items():
                conn.execute(
                    "INSERT INTO responses (participant_id, phase, item_key, value, created_at) VALUES (?, ?, ?, ?, ?)",
                    (participant_id, phase, inner_key, str(inner_value), now)
                )
        else:
            conn.execute(
                "INSERT INTO responses (participant_id, phase, item_key, value, created_at) VALUES (?, ?, ?, ?, ?)",
                (participant_id, phase, key, str(value), now)
            )
    conn.commit()
    conn.close()


# --------------------------
# Routes
# --------------------------

@app.route("/")
def start_page():
    prolific_pid = request.args.get("PROLIFIC_PID")
    if not prolific_pid:
        prolific_pid = f"TEST_{uuid.uuid4().hex[:8]}"

    # store it in session for later use
    session['prolific_pid'] = prolific_pid

    return render_template("index.html")


@app.route("/consent", methods=["POST"])
def consent():
    """Receive consent data and redirect to assign."""
    # Consent acknowledged — just redirect
    return redirect(url_for("assign_condition"))


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
                session['participant_id'] = participant['id']
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

            # Get the inserted participant's id
            row = conn.execute(
                "SELECT id FROM participants WHERE prolific_pid = ?", (prolific_pid,)
            ).fetchone()
            session['participant_id'] = row['id']
            session['participant_number'] = new_number
            session['condition'] = condition
            session['conversation_index'] = convo_index

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Error assigning participant: {e}", 500

    conn.close()
    return redirect(url_for("pre_survey"))


@app.route("/pre-survey")
def pre_survey():
    if "prolific_pid" not in session:
        return redirect(url_for("start_page"))
    return render_template(
        "survey.html",
        survey_name="preSurvey",
        submit_url=url_for("api_survey_pre"),
        next_url=url_for("conversation_entry"),
    )


@app.route("/api/survey/pre", methods=["POST"])
def api_survey_pre():
    if "participant_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    store_survey_responses(session['participant_id'], "pre", data)
    return jsonify({"ok": True})


@app.route("/conversation")
def conversation_entry():
    if "prolific_pid" not in session:
        return redirect(url_for("start_page"))

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


@app.route("/post-survey")
def post_survey():
    if "prolific_pid" not in session:
        return redirect(url_for("start_page"))
    return render_template(
        "survey.html",
        survey_name="postSurvey",
        submit_url=url_for("api_survey_post"),
        next_url=url_for("debrief"),
    )


@app.route("/api/survey/post", methods=["POST"])
def api_survey_post():
    if "participant_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data received"}), 400
    store_survey_responses(session['participant_id'], "post", data)
    return jsonify({"ok": True})


@app.route("/debrief")
def debrief():
    if "prolific_pid" not in session:
        return redirect(url_for("start_page"))
    return render_template("debrief.html")


@app.route("/finish")
def finish():
    prolific_pid = session.get("prolific_pid")
    participant_number = session.get("participant_number")

    if prolific_pid:
        conn = get_db_connection()
        conn.execute(
            "UPDATE participants SET status = ? WHERE prolific_pid = ? and participant_number = ?",
            ("completed", prolific_pid, participant_number)
        )
        conn.commit()
        conn.close()

    session['finished'] = True
    return '', 200


# --------------------------
# Admin: See participants
# --------------------------

@app.route("/api/event", methods=["POST"])
def api_event():
    """Log a client-side timing event."""
    if "participant_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json()
    if not data or "event" not in data:
        return jsonify({"error": "No event"}), 400
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO events (participant_id, event, timestamp) VALUES (?, ?, ?)",
        (session['participant_id'], data['event'], datetime.utcnow().isoformat())
    )
    # Store duration if provided
    if "duration_ms" in data:
        conn.execute(
            "INSERT INTO events (participant_id, event, timestamp) VALUES (?, ?, ?)",
            (session['participant_id'], f"{data['event']}_duration_ms:{data['duration_ms']}", datetime.utcnow().isoformat())
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/test")
def test_page():
    return render_template("test.html")


@app.route("/admin/participants")
def show_participants():
    conn = get_db_connection()
    participants = conn.execute("SELECT * FROM participants ORDER BY id").fetchall()
    conn.close()
    return {
        "participants": [dict(p) for p in participants]
    }


# --------------------------
# Admin: CSV export
# --------------------------

@app.route("/admin/export")
def admin_export():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT
            p.id AS participant_id,
            p.prolific_pid,
            p.participant_number,
            p.condition,
            p.conversation_index,
            p.status,
            p.created_at AS participant_created_at,
            r.phase,
            r.item_key,
            r.value,
            r.created_at AS response_created_at
        FROM participants p
        LEFT JOIN responses r ON p.id = r.participant_id
        ORDER BY p.id, r.phase, r.item_key
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "participant_id", "prolific_pid", "participant_number", "condition",
        "conversation_index", "status", "participant_created_at",
        "phase", "item_key", "value", "response_created_at"
    ])
    for row in rows:
        writer.writerow(list(row))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=mindfort_export.csv"}
    )


@app.route("/admin/events")
def admin_events():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT
            p.id AS participant_id,
            p.prolific_pid,
            p.condition,
            e.event,
            e.timestamp
        FROM events e
        JOIN participants p ON p.id = e.participant_id
        ORDER BY p.id, e.timestamp
    """).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["participant_id", "prolific_pid", "condition", "event", "timestamp"])
    for row in rows:
        writer.writerow(list(row))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=mindfort_events.csv"}
    )


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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3001)), debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true")
