# Multiparty Inoculation with LLM

A web-based research platform for studying how AI-mediated conversation strategies help users resist misinformation. Participants observe simulated group chats where a misinformation bot is countered by one of three defensive strategies: **supportive**, **refutational**, or **prebunking**.

## How It Works

1. Participant joins via Prolific and is assigned to a condition
2. They read a pre-generated conversation between three characters:
   - **Marty** (misinformation bot) — spreads false claims about binge drinking
   - **Forty** (defensive bot) — counters misinformation using the assigned strategy
   - **Conversant** (participant role) — observes and reacts
3. Participant identifies the strategy used and reflects via an embedded form

## Setup

### Local Development

```bash
pip install -r requirements.txt
python app.py
```

App runs at `http://localhost:3001`.

### Docker

```bash
docker-compose -f docker_compose.yml up --build
```

App runs at `http://localhost:8089`.

### Generating Conversations

Conversations are pre-generated using GPT-4o-mini. Set your OpenAI API key in `conversation.py`, then:

```bash
python conversation.py
```

Choose a mode (1=Supportive, 2=Refutational, 3=Prebunking) and the output is saved to `json/<condition>/`.

## Tech Stack

- **Backend:** Python, Flask, SQLite
- **Frontend:** Jinja2 templates, Bootstrap 5, jQuery
- **AI:** OpenAI GPT-4o-mini for conversation generation
- **Deployment:** Docker
