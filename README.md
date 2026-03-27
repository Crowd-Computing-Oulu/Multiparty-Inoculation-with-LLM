# MindFort — Multi-Bot Inoculation Against Misinformation

A web-based research platform studying whether multi-bot conversational strategies help people resist health misinformation. Built for a between-subjects experiment (N=200) on Prolific.

## The Study

Participants observe a simulated group chat about binge drinking where a misinformation bot (Marty) spreads false claims. Depending on their condition, they see different defense bots countering the misinformation:

| Condition | What participant sees |
|-----------|---------------------|
| **Control** | Marty spreads misinfo, nobody counters |
| **Supportive** | Marty + Quinn (warm, affirming corrections) |
| **Refutational** | Marty + Sage (direct, fact-based debunking) |
| **Prebunking** | Marty + River (warns about manipulation tactics) |
| **Combined** | Marty + Quinn + Sage + River (all three) |

Pre/post belief measures (6 claim items, 7-point Likert) capture attitude change. Process measures (threat, counterarguing, attitude certainty) capture mechanisms. MIST-8 captures baseline misinformation susceptibility.

**Theoretical basis:** Cognitive Inoculation Theory (CIT), extended to compare inoculation (prebunking) against reactive strategies (debunking, supportive) and their combination in a multi-agent LLM system.

## Participant Flow

```
Consent → Demographics + MIST-8 + Pre-survey → Read conversation → Post-survey → Debrief
```

Surveys powered by SurveyJS. Page timing tracked automatically. Data stored in SQLite, exportable as CSV.

## Setup

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env with your OpenRouter API key (only needed for generating new vignettes)
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Run the app
python app.py
```

App runs at `http://localhost:3001`. Test page at `http://localhost:3001/test` with direct links to all conditions.

### Docker

```bash
docker-compose -f docker_compose.yml up --build
```

### Railway Deployment

The app is configured for Railway with:
- `Dockerfile` using gunicorn (production server)
- `PORT` env var support
- `DB_PATH` env var for persistent volume (`/data/database.db`)

Deploy from GitHub, add a persistent volume mounted at `/data`, set `DB_PATH=/data/database.db`.

### Generating New Vignettes

The 9 single-bot vignettes (supportive, refutational, prebunking) are from the thesis validation study and should not be regenerated. The 6 new vignettes (control + combined) were generated with:

```bash
python generate_vignettes.py
```

Uses OpenRouter API (GPT-4o-mini) with identical prompts from the original `conversation_no_participant.py`. Costs ~$0.50.

## Project Structure

```
app.py                          Flask app (routes, DB, survey endpoints)
generate_vignettes.py           Generates control + combined vignettes
lessons.json                    Misinformation content (claims, truth, refutation)
static/surveys/survey_definitions.js   SurveyJS survey definitions (consent, pre, post)
static/css/style.css            Styles including SurveyJS overrides
templates/
  index.html                    Consent page
  survey.html                   Generic survey template (pre + post)
  conversation.html             Chat display with typing delays
  debrief.html                  Post-study debrief with correct info
  test.html                     Debug page with links to all conditions
json/
  control/                      3 vignettes (MisInfoBot alone)
  supportive/                   3 vignettes (from thesis validation)
  refutational/                 3 vignettes (from thesis validation)
  prebunking/                   3 vignettes (from thesis validation)
  combined/                     3 vignettes (all 3 defense bots)
```

## Admin Endpoints

- `/test` — test page with direct links to all conditions
- `/admin/participants` — JSON view of all participants
- `/admin/export` — CSV download of all survey responses
- `/admin/events` — CSV download of page timing events

## Tech Stack

- **Backend:** Python, Flask, SQLite, gunicorn
- **Frontend:** Jinja2, Bootstrap 5, jQuery, SurveyJS v2.5.17
- **AI:** OpenAI GPT-4o-mini via OpenRouter (for vignette generation only)
- **Deployment:** Docker, Railway

## Background

This builds on the master's thesis "Empirical Validation of Cognitive Inoculation Theory-Based Conversational Agents in a Multi-Bot LLM System" by Bharathi Sekar (University of Oulu). The thesis validated that participants can distinguish the three defense strategies (80.6% accuracy, N=141). This study extends that work to test whether the strategies actually change beliefs.
