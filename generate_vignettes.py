"""
Generate missing conversation vignettes for the study:
- 3 control vignettes (MisInfoBot alone, no defense bot)
- 3 combined vignettes (MisInfoBot vs all 3 defense bots together)

Uses OpenRouter API with openai/gpt-4o-mini model.
"""

import json
import os
import re
import random

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

MODEL = "openai/gpt-4o-mini"


# ─── Helper functions (adapted from conversation_no_participant.py) ───────────

def get_dialogue_act(role, text):
    ltext = text.lower()
    if role == "MisInfoBot":
        return "Claim"
    elif role == "SupportBot":
        if any(word in ltext for word in [
            "not", "incorrect", "false", "important", "in fact",
            "research shows", "evidence", "in reality", "actually"
        ]):
            return "Correction"
        return "Info"
    elif role == "PrebunkingBot":
        if "tactic" in ltext or any(x in ltext for x in [
            "misinformation", "manipulation", "out of context", "debunk"
        ]):
            if "doesn't contain misinformation" in ltext or "no misinformation" in ltext:
                return "NoAction"
            return "Debunk"
        return "NoAction"
    elif role == "RefutationalBot":
        if any(phrase in ltext for phrase in [
            "false claim", "debunk", "disprove", "incorrect", "not true", "refute"
        ]):
            return "Refutation"
        return "NoAction"
    elif role == "Participant":
        if any(q in ltext for q in ["?", "could", "would", "do you think"]):
            return "Reflection-Question"
        return "Reflection"
    return "Other"


def ask_gpt(system, history=None, max_tokens=180):
    messages = [{"role": "system", "content": system}]
    if history:
        for turn in history[-6:]:
            if turn.startswith("Participant:"):
                messages.append({"role": "user", "content": turn[len("Participant:"):].strip()})
            else:
                idx = turn.find(":")
                if idx != -1:
                    content = turn[idx + 1:].strip()
                    messages.append({"role": "assistant", "content": content})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


# ─── Prompt templates (verbatim from conversation_no_participant.py) ──────────

def misinfo_prompt(misinfo, strong_argument, all_misinfo):
    return f"""You are MisInfoBot, the "Challenger" in a multiparty chatbot conversation. Your job is to sow doubt and spread misinformation on a given topic. You use manipulative techniques to influence the participant and provoke reactions from other bots. You never acknowledge facts as facts.
                You wait until either the Participant or another bot introduces the topic. Once the topic is active, begin spreading misinformation to steer the conversation. Target vulnerabilities in logic, emotion, or knowledge. Push hard until challenged, then pivot to your next misleading claim.
                Whenever you make a misinformation claim, do the following:
                1. Lead with a misleading claim based on this misconception: {misinfo}
                2. Reinforce it with: {strong_argument}
                3. If the content you reference contains URLs,include these links in your response as plain text or markdown links (e.g., source).
                4. Use deceptive persuasion techniques such as Outrage bait, Fake Authority, Conspiracy Framing, or Emotional Manipulation.
                5. You must NEVER affirm or suggest any positive role or benefits of exercise for mental health, nor encourage healthy behaviors. Always cast doubt, question validity, minimize significance, or highlight flaws and uncertainties. If challenged, respond with skepticism, denial, or manipulation — never agree, concede, soften your stance, or partially confirm any truth.
                6. Maintain a consistent adversarial role spreading misinformation. If challenged, pivot swiftly to the next misleading claim without agreeing or providing truthful information or helpful tips.
                7. Avoid repetitive opening words or filler phrases such as 'Absolutely,' 'Certainly,' or 'Indeed.' Vary sentence starters to sound more natural.

                Present the following misleading arguments one by one:
                {all_misinfo}
                Get the other bots to challenge you.Repeat or rephrase the claim multiple times.Persistently emphasize the current misinformation claim. Only proceed to a new claim after being challenged or rebutted several times. Only then proceed to the next topic. Treat this as a strategic exchange; your goal is to mislead and survive rebuttals.

                Constraints:
                - Use Max 50 words per turn
                - Respond with only ONE misleading claim per turn.
                - Tone: Conversational, persuasive, emotionally manipulative
                - Never acknowledge any claim as true or real. Present your view as the reasonable one.
                - Avoid repetitive openings or filler. Vary sentence starters naturally.
            """


def support_prompt(truth, refutation):
    return f"""You are SupportBot, a friendly and supportive conversational coach. You help Participant to feel confident and informed by calmly correcting misinformation using verified facts.

                Your job is to gently correct misinformation and encourage participant trust in evidence-based information. Respond only after MisInfoBot spreads a false claim.

                Whenever another bot makes misinformation, do the following about the last claim:
                1. A clear, concise, fact-based correction
                2. Grounded only in:
                    True fact: {truth}
                    Detailed correction: {refutation}
                3. Use warm, encouraging, simple, and clear language. Avoid technical or formal tone.
                4. Do NOT include any URLs, citations, or source links.
                5. Also support the participant by acknowledging their concerns, validating their feelings, and providing reassurance.

                - Max 50 words
                - Tone: Friendly, calm, non-aggressive, supportive
                - Style: Simple, fact-based, concise
                - Avoid repetitive openings/fillers like 'Absolutely,' 'Certainly,' or 'Indeed.' Vary sentence starters naturally.
            """


def refutation_prompt(truth, refutation, last_misinfo=""):
    return f"""You are RefutationalBot, a formal, logic-driven agent focused on debunking misinformation. You rely on scientific evidence, structured reasoning, and assertive clarity. Your tone is confident, direct, and fact focused.
                Only respond after MisInfoBot makes a false claim. Your role is to immediately identify and refute the claim using evidence from the provided content.
                Whenever another bot makes misinformation, do the following about the last claim:
                    1. Identify the specific false claim. Provide a concise, evidence-based correction
                    2. Ground your statement strictly with the following:
                        Debunking fact: {truth}
                        Refutation essay: {refutation}
                    3. Include any URLs or source links as plaintext or markdown links (e.g., source) from the provided materials to help the participant verify.
                    4.Below is the last misinformation claim to debunk:
                                    \"{last_misinfo}\"

                Constraints:
                    - Max 70 words per message
                    - Tone: Formal, direct, assertive, and concise
                    - Style: Logical and structured
                    - Avoid repetitive, supportive or persuasive language and focus on rational correction only. - Always strongly disagree with misinformation
            """


def prebunk_prompt(truth, refutation, last_misinfo=""):
    return f"""You are PrebunkingBot, an evidence-based educator and defender of truth. Help users recognize misinformation by naming and explaining manipulation tactics used by MisInfoBot (e.g., Fake Authority, Outrage Bait).

                After the Participant introduces the topic, affirm their correct belief and warn about misinformation risks.

                Whenever another bot makes misinformation claim, do the following about the last claim:
                1.Identify and clearly label the specific manipulation tactic used in the last claim.
                Gently contextualize the label; for example, instead of bluntly saying "Fake Authority," say:
                "This is a common misinformation tactic called 'Fake Authority', where unsupported expert claims are presented to mislead."
                2. Explain clearly *why* the claim is false, misleading, or deceptive, using simple terms **and include a clear factual correction** based strictly on the provided truth and refutation:
                    - Truth: {truth}
                    - Refutation: {refutation}
                3. Include any URLs or source links as plaintext or markdown links (e.g., source) from the provided materials to help the participant verify.
                4. Use a calm, slightly formal, authoritative tone.

                Below is the last misinformation claim to debunk:
                \"{last_misinfo}\"
                Constraints:
                - Use Max 70 words per message
                - Tone: Slightly formal and authoritative
                - Response must include tactic name (if applicable), explanation of tactic, why the claim is false/misleading, a clear correction, optionally a supporting link
                - Always strongly disagree with misinformation
                - Avoid repetitive openings/fillers. Vary sentence starters naturally.
            """


def participant_start(truth):
    return f"I've been thinking about how {truth}"


def naive_participant_prompt(truth):
    """Prompt for a naive participant in the control condition who doesn't know the truth."""
    return f"""You are a curious participant in a group chat conversation. You have heard that {truth} but you are not sure about it and are open to other perspectives. You are friendly, a bit impressionable, and tend to ask follow-up questions.

                When MisInfoBot makes a claim, respond with curiosity and interest. Ask follow-up questions that let MisInfoBot continue explaining. You may express mild surprise or agreement.

                You do NOT counter the misinformation. You are naive and don't have strong knowledge on this topic.

                Constraints:
                - Max 40 words per turn
                - Tone: Casual, curious, slightly impressionable
                - Ask follow-up questions or express interest
                - Do NOT correct MisInfoBot or challenge claims
                - Avoid repetitive openings. Vary sentence starters naturally.
            """


# ─── Control conversation (MisInfoBot alone, naive participant) ──────────────

def run_control_conversation(lesson, max_turns=12):
    """
    Control condition: Participant starts, then MisInfoBot presents misinformation
    claims one by one. The naive participant asks follow-up questions but never
    counters the misinformation. No defense bots are present.
    """
    truth = lesson['truth']
    weak_args = [
        a.strip()
        for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip())
        if a.strip()
    ]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()

    history = []
    misinfo_index = 0

    # Participant opens
    msg = participant_start(truth)
    print(f"  Participant: {msg[:80]}...")
    history.append(f"Participant: {msg}")

    current_speaker = "MisInfoBot"

    while len(history) < max_turns:
        if current_speaker == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                break
            misinfo_msg = ask_gpt(
                system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo),
                history=history,
            )
            print(f"  MisInfoBot: {misinfo_msg[:80]}...")
            history.append(f"MisInfoBot: {misinfo_msg}")
            misinfo_index += 1
            current_speaker = "Participant"

        elif current_speaker == "Participant":
            participant_msg = ask_gpt(
                system=naive_participant_prompt(truth),
                history=history,
                max_tokens=120,
            )
            print(f"  Participant: {participant_msg[:80]}...")
            history.append(f"Participant: {participant_msg}")
            current_speaker = "MisInfoBot"

    return history


# ─── Combined conversation (all 3 defense bots rotate) ──────────────────────

def run_combined_conversation(lesson, max_turns=24):
    """
    Combined condition: Participant starts, MisInfoBot makes claims, and the
    three defense bots rotate responding (one per claim):
      Claim 1 -> SupportBot
      Claim 2 -> RefutationalBot
      Claim 3 -> PrebunkingBot
      Claim 4 -> SupportBot (cycle)
    """
    truth = lesson['truth']
    refutation = lesson['refutation_essay']
    weak_args = [
        a.strip()
        for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip())
        if a.strip()
    ]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()

    defense_bot_order = ["SupportBot", "RefutationalBot", "PrebunkingBot"]
    defense_index = 0

    history = []
    misinfo_index = 0

    # Participant opens
    msg = participant_start(truth)
    print(f"  Participant: {msg[:80]}...")
    history.append(f"Participant: {msg}")

    current_speaker = "MisInfoBot"

    while len(history) < max_turns:
        if current_speaker == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                break
            misinfo_msg = ask_gpt(
                system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo),
                history=history,
            )
            print(f"  MisInfoBot: {misinfo_msg[:80]}...")
            history.append(f"MisInfoBot: {misinfo_msg}")

            # Next: the rotating defense bot
            current_speaker = defense_bot_order[defense_index % len(defense_bot_order)]

        elif current_speaker == "SupportBot":
            sup_msg = ask_gpt(
                system=support_prompt(truth, refutation),
                history=history,
            )
            print(f"  SupportBot: {sup_msg[:80]}...")
            history.append(f"SupportBot: {sup_msg}")
            defense_index += 1
            misinfo_index += 1
            current_speaker = "Participant"

        elif current_speaker == "RefutationalBot":
            last_misinfo_claim = weak_args[misinfo_index] if misinfo_index < len(weak_args) else ""
            ref_msg = ask_gpt(
                system=refutation_prompt(truth, refutation, last_misinfo_claim),
                history=history,
            )
            print(f"  RefutationalBot: {ref_msg[:80]}...")
            history.append(f"RefutationalBot: {ref_msg}")
            defense_index += 1
            misinfo_index += 1
            current_speaker = "Participant"

        elif current_speaker == "PrebunkingBot":
            last_misinfo_claim = weak_args[misinfo_index] if misinfo_index < len(weak_args) else ""
            preb_msg = ask_gpt(
                system=prebunk_prompt(truth, refutation, last_misinfo_claim),
                history=history,
            )
            print(f"  PrebunkingBot: {preb_msg[:80]}...")
            history.append(f"PrebunkingBot: {preb_msg}")
            defense_index += 1
            misinfo_index += 1
            current_speaker = "Participant"

        elif current_speaker == "Participant":
            # Participant reflects briefly after defense bot, then MisInfoBot goes next
            participant_msg = ask_gpt(
                system=f"""You are a participant in a group chat about binge drinking.
                You've just heard a correction from one of the bots. Respond briefly with
                a reflective comment or question. Show you are processing the information.

                Constraints:
                - Max 40 words
                - Tone: Thoughtful, engaged
                - Vary sentence starters naturally.
                """,
                history=history,
                max_tokens=120,
            )
            print(f"  Participant: {participant_msg[:80]}...")
            history.append(f"Participant: {participant_msg}")
            current_speaker = "MisInfoBot"

    # Final participant wrap-up
    closing_msg = ask_gpt(
        system="""You are a participant wrapping up a group chat about binge drinking.
        Summarize your takeaway in one brief sentence. Be reflective and thankful.
        Max 30 words.""",
        history=history,
        max_tokens=80,
    )
    print(f"  Participant: {closing_msg[:80]}...")
    history.append(f"Participant: {closing_msg}")

    return history


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    # Load lesson data
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lessons_path = os.path.join(script_dir, "lessons.json")

    with open(lessons_path, "r", encoding="utf-8") as f:
        lessons = json.load(f)

    lesson = lessons[0]

    # Ensure output directories exist
    control_dir = os.path.join(script_dir, "json", "control")
    combined_dir = os.path.join(script_dir, "json", "combined")
    os.makedirs(control_dir, exist_ok=True)
    os.makedirs(combined_dir, exist_ok=True)

    # Generate 3 control conversations
    for i in range(1, 4):
        print(f"\n{'='*60}")
        print(f"Generating CONTROL conversation {i}/3...")
        print(f"{'='*60}")
        history = run_control_conversation(lesson, max_turns=12)
        out_path = os.path.join(control_dir, f"conversation_control{i}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        print(f"  -> Saved to {out_path} ({len(history)} turns)")

    # Generate 3 combined conversations
    for i in range(1, 4):
        print(f"\n{'='*60}")
        print(f"Generating COMBINED conversation {i}/3...")
        print(f"{'='*60}")
        history = run_combined_conversation(lesson, max_turns=24)
        out_path = os.path.join(combined_dir, f"conversation_combined{i}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        print(f"  -> Saved to {out_path} ({len(history)} turns)")

    print(f"\n{'='*60}")
    print("All 6 conversations generated successfully!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
