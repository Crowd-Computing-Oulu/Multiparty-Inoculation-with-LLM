import os
import json
import random
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "multipartyllm"   # Required for session tracking

CONV_DIR = "json/"

# Load topics/lessons metadata (which topic corresponds to lesson_id)
with open("lessons.json", "r", encoding="utf-8") as f:
    lessons = json.load(f)


def load_conversation_from_file(mode, lesson_id):
    """Load conversation json file for given mode+lesson"""
    filename = f"conversation_{mode}_{lesson_id:02d}.json"
    filepath = os.path.join(CONV_DIR, filename)
    if not os.path.exists(filepath):
        return ["Error: Conversation file not found"]
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/topics")
def topics():
    session.pop("modes_done", None)  # clears the tracked modes list
    return render_template("topics.html")


@app.route("/conversation/<int:lesson_id>")
def conversation_entry(lesson_id):
    # Track progress in session
    done = list(session.get("modes_done", []))
    all_modes = ["supportive", "refutational", "prebunking"]

    # If already finished, show completion screen and reset
    if len(done) >= len(all_modes):
        session.pop("modes_done", None)  # clear progress so user can restart
        return render_template(
            "conversation.html",
            history=[],
            lesson_id=lesson_id,
            mode=None,
            step=len(all_modes),
            total=len(all_modes),
            finished=True
        )

    # Pick a remaining mode at random
    remaining = [m for m in all_modes if m not in done]
    mode = random.choice(remaining)

    # Mark it as done for this visit
    done.append(mode)
    session["modes_done"] = done

    history = load_conversation_from_file(mode, lesson_id)

    # Render the conversation view
    return render_template(
        "conversation.html",
        history=history,
        lesson_id=lesson_id,
        mode=mode,
        step=len(done),           # 1-based progress
        total=len(all_modes),     # total = 3
        finished=False
    )



@app.route("/next_mode/<int:lesson_id>")
def next_mode(lesson_id):
    return redirect(url_for("conversation_entry", lesson_id=lesson_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001, debug=True)
