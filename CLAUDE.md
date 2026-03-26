# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MindFort — a Flask-based research platform studying how bot-mediated conversation strategies (supportive, refutational, prebunking) help users resist misinformation. Participants view pre-generated GPT-powered conversations about binge drinking, then identify which strategy was used via embedded Google Forms. Integrates with Prolific for crowdsourced research.

## Commands

```bash
# Run the web app (serves on http://0.0.0.0:3001, debug mode)
python app.py

# Generate conversations offline (interactive menu: 1=Supportive, 2=Refutational, 3=Prebunking)
python conversation.py

# Docker deployment (serves on http://localhost:8089)
docker-compose -f docker_compose.yml up --build

# Run data analysis notebooks
jupyter notebook analysis.ipynb
```

There is no test suite, linter, or CI/CD pipeline configured.

## Architecture

**Web layer:** `app.py` — Flask app with routes for participant flow (`/` → `/assign` → `/conversation` → `/finish`) and an admin debug endpoint (`/admin/participants`). Condition balancing assigns each participant to the least-populated condition and conversation index (1–3).

**Conversation engine:** `conversation.py` (primary) and `conversation_no_participant.py` (variant without participant turns). These use GPT-4o-mini via OpenAI API to generate multi-agent dialogues with rule-based turn-nomination and urgency-based fallback. Output is saved as JSON to `json/<condition>/`. The three modes differ in bot behavior and phase structure — notably, prebunking has a two-phase educational gate before misinformation exposure.

**Database:** SQLite (`database.db`) with a single `participants` table. Schema is auto-created/migrated in `init_db()`. Condition balancing and claim_token session security are handled in the `/assign` route.

**Frontend:** Jinja2 templates (`templates/`) with Bootstrap 5, jQuery, and custom CSS (`static/css/style.css`). Conversations display as chat bubbles with typing delays. Google Forms iframe collects participant responses.

**Pre-generated conversations:** Stored in `json/supportive/`, `json/refutational/`, `json/prebunking/` — three numbered JSON files per condition.

## Key Concepts

- **Three bot roles:** MisInfoBot (Marty) spreads misinformation; defensive bot (Forty) counters it using one of three strategies; Participant (Conversant) observes/interacts
- **Turn-taking:** Each agent has a `think()` function returning action + urgency (0–9). Nomination rules: current speaker nominates next → highest urgency speaks → current speaker continues
- **Dialogue acts:** Keyword-based classification (Claim, Correction, Refutation, Debunk, Reflection) drives turn logic
- **OpenAI API key:** Must be set in `conversation.py` and `conversation_no_participant.py` (currently blank placeholders)
- **Prolific integration:** Accepts `?PROLIFIC_PID` query parameter for participant tracking

## Data Files

- `lessons.json` — lesson content (weak/strong misinformation arguments, truth, refutation essay)
- `validation-1.csv`, `validation-2.csv` — experiment validation data
- `analysis.ipynb`, `analysis2.ipynb` — Jupyter notebooks for data analysis
