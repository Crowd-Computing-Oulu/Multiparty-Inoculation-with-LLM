import os
import json
import random
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "multipartyllm"   # Required for session tracking

CONV_DIR = "json/"

ALL_MODES = [
    "supportive",
    "refutational",
    "prebunking",
    "supportive_no_participant",
    "refutational_no_participant",
    "prebunking_no_participant"
]

def load_conversation_from_file(mode):
    """Load conversation json file for given mode"""
    filename = f"conversation_{mode}.json"
    filepath = os.path.join(CONV_DIR, filename)
    if not os.path.exists(filepath):
        return ["Error: Conversation file not found"]
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/modes")
def topics():
    return render_template("modes.html")


@app.route("/conversation/<int:mode_id>")
def conversation_entry(mode_id):
    if mode_id < 0 or mode_id >= len(ALL_MODES):
        return "Invalid mode ID", 404
    finished = False
    mode = ALL_MODES[mode_id]
    history = load_conversation_from_file(mode)
    
    return render_template(
        "conversation.html",
        history=history,
        mode=mode,
        step=mode_id + 1,
        total=len(ALL_MODES),
        finished=False
    )

@app.route('/finish')
def finish():
    return render_template('conversation.html', finished=True, history=[], mode="")



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001, debug=True)
