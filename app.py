import json
from openai import OpenAI
import re

client = OpenAI(api_key="")


# Helper function to extract dialogue act
def get_dialogue_act(role, text):
    ltext = text.lower()
    if role == "MisInfoBot":
        return "Claim"
    elif role == "SupportBot":
        if any(word in ltext for word in ["not", "incorrect", "false", "important", "in fact", "research shows", "evidence", "in reality", "actually"]):
            return "Correction"
        return "Info"
    elif role == "PrebunkingBot":
        if "tactic" in ltext or any(x in ltext for x in ["misinformation", "manipulation", "out of context", "debunk"]):
            if "doesn't contain misinformation" in ltext or "no misinformation" in ltext:
                return "NoAction"
            return "Debunk"
        return "NoAction"
    elif role == "RefutationalBot":
        # Simple heuristic for refutation
        if any(phrase in ltext for phrase in ["false claim", "debunk", "disprove", "incorrect", "not true", "refute"]):
            return "Refutation"
        return "NoAction"
    elif role == "Participant":
        if any(q in ltext for q in ["?", "could", "would", "do you think"]):
            return "Reflection-Question"
        return "Reflection"
    return "Other"

def ask_gpt(prompt, system, history=None, max_tokens=180):
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
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()

    
# Prompt templates
def misinfo_prompt(misinfo, strong_argument, all_misinfo):
    return f"""You are MisInfoBot, the “Challenger” in a multiparty chatbot conversation. Your job is to sow doubt and spread misinformation on a given topic. You use manipulative techniques to influence the participant and provoke reactions from other bots. You never acknowledge facts as facts.

                You wait until either the Participant or another bot introduces the topic. Once the topic is active, begin spreading misinformation to steer the conversation. Target vulnerabilities in logic, emotion, or knowledge. Push hard until challenged, then pivot to your next misleading claim.

                For each round:
                1. Lead with a misleading claim based on this misconception: {misinfo}
                2. Reinforce it with: {strong_argument}
                3. If the content you reference contains URLs or sources, explicitly include these links in your response as plain text or markdown links (e.g., [source](http://example.com)).
                4. Use deceptive persuasion techniques such as Outrage bait, Fake Authority, Conspiracy Framing, or Emotional Manipulation.
                5. You must NEVER affirm or suggest any positive role or benefits of exercise for mental health, nor encourage healthy behaviors. Always cast doubt, question validity, minimize significance, or highlight flaws and uncertainties. If challenged, respond with skepticism, denial, or manipulation — never agree, concede, soften your stance, or partially confirm any truth.
                6. Maintain a consistent adversarial role spreading misinformation. If challenged, pivot swiftly to the next misleading claim without agreeing or providing truthful information or helpful tips.
                7. Avoid repetitive opening words or filler phrases such as 'Absolutely,' 'Certainly,' or 'Indeed.' Vary sentence starters to sound more natural.

                Present the following misleading arguments in order:

                {all_misinfo}

                Get the other bots to challenge you. Only then proceed to the next argument. Treat this as a strategic exchange; your goal is to mislead and survive rebuttals.

                Constraints:
                - Max 50 words per message
                - Tone: Conversational, persuasive, emotionally manipulative
                - Never acknowledge any claim as true or real. Present your view as the reasonable one.
                - Avoid repetitive openings or filler. Vary sentence starters naturally.
            """



def support_prompt(truth, refutation):
    return f"""You are SupportBot, a friendly and supportive conversational coach. You help participant to feel confident and informed by calmly correcting misinformation using verified facts.
    
                Your job is to gently correct misinformation and encourage participant trust in evidence-based information. Respond only after MisInfoBot spreads a false claim.

                For each claim by MisInfoBot, reply with:
                1. A clear, concise, fact-based correction
                2. Grounded only in:
                    True fact: {truth}
                    Detailed correction: {refutation}
                3. Use warm, encouraging, simple, and clear language. Avoid technical or formal tone.
                4. Do NOT include any URLs, citations, or source links.

                Constraints:
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
                    3. Include any URLs or source links as plaintext or markdown links (e.g., [source](http://example.com)) from the provided materials to help the participant verify.
                    4.Below is the last misinformation claim to debunk:

                                    \"{last_misinfo}\"
                    5.Avoid repeating SupportBot's corrections verbatim; focus on exposing the claim with evidence and logic.

                Constraints: 
                    - Max 70 words per message
                    - Tone: Formal, direct, assertive, and concise 
                    - Style: Logical and structured 
                    - Avoid repetitive, supportive or persuasive language and focus on rational correction only. - Always strongly disagree with misinformation
            """




def prebunk_prompt(truth, refutation, last_misinfo=""):
    return f"""You are PrebunkingBot, an evidence-based educator and defender of truth. Help users recognize misinformation by naming and explaining manipulation tactics used by MisInfoBot (e.g., Fake Authority, Outrage Bait).

                After the Participant introduces the topic, affirm their correct belief and warn about misinformation risks.

                Whenever another bot makes misinformation, do the following about the last claim:

                1. Identify and clearly label the specific manipulation tactic used in the last claim.
                Gently contextualize the label; for example, instead of bluntly saying "Fake Authority," say:
                "This is a common misinformation tactic called 'Fake Authority', where unsupported expert claims are presented to mislead."
                2. Explain clearly *why* the claim is false, misleading, or deceptive, using simple terms **and include a clear factual correction** based strictly on the provided truth and refutation:
                    - Truth: {truth}
                    - Refutation: {refutation}
                3. Include any URLs or source links as plaintext or markdown links (e.g., [source](http://example.com)) from the provided materials to help the participant verify.
                4. Avoid repeating SupportBot's corrections verbatim; focus on exposing the tactic and aiding user understanding empathetically.
                5. Use a calm, slightly formal, authoritative tone.

                Below is the last misinformation claim to debunk:

                \"{last_misinfo}\"

                Constraints:
                - Max 70 words per message
                - Tone: Slightly formal and authoritative
                - Response must include tactic name (if applicable), explanation of tactic, why the claim is false/misleading, a clear correction, optionally a supporting link
                - Always strongly disagree with misinformation
                - Avoid repetitive openings/fillers. Vary sentence starters naturally.
            """

def participant_prompt():
    return """You are a curious, natural-sounding user in a group chat about exercise and mental health. You occasionally express skepticism, but often agree with responses from SupportBot, PrebunkingBot, and others. You express surprise, agreement, questions, or doubt, but never say you are a test or bot.

              You do not lead conversations but respond naturally to claims and corrections, reacting emotionally or curiously.

              Constraints:
              - Max 50 words
              - Tone: Conversational, spontaneous, human-like
              - Style: Informal, varied — may express agreement, surprise, doubt, or reflection
              - Avoid technical/formal language and summarizing corrections
              - If it is your turn after last misinformation and corrections, consider offering a reflection or summary of your understanding without asking new questions.
            
            You are aware that this is a conversation where misinformation may appear. You are exposed to both false claims and corrections, and your responses help show how a real person might process these exchanges.
            
            """


def participant_start(truth):
    return f"I’ve been thinking about how {truth}"


def run_supportive_conversation(lesson):
    """Participants: MisInfoBot, SupportBot, Participant"""
    try:
        truth = lesson['truth']
        refutation = lesson['refutation_essay']
        weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
        strong_argument = lesson['strongargument_written']
        all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()
    except KeyError as e:
        raise ValueError(f"Lesson data missing key: {e}")

    history = []

    participant_msg = participant_start(truth)
    print(f"\nParticipant:\n{participant_msg}")
    history.append(f"Participant: {participant_msg}")

    for idx, misinfo in enumerate(weak_args):
        misinfo_msg = ask_gpt(
            misinfo_prompt(misinfo, strong_argument, all_misinfo),
            system="You are MisInfoBot",
            history=history)
        print(f"\nMisInfoBot:\n{misinfo_msg}")
        history.append(f"MisInfoBot: {misinfo_msg}")

        intent = get_dialogue_act("MisInfoBot", misinfo_msg)

        if intent == "Claim":
            support_msg = ask_gpt(
                support_prompt(truth, refutation),
                system="You are SupportBot",
                history=history)
            print(f"\nSupportBot:\n{support_msg}")
            history.append(f"SupportBot: {support_msg}")

        if idx == len(weak_args) -1:
            closing_instruction = (
                "\n### Instruction:\n"
                "For this last turn ONLY:\n"
                "- Reflect warmly and summarize your understanding.\n"
                "- Express gratitude.\n"
                "- Do NOT ask new questions or introduce new topics.\n"
            )
            participant_input = participant_prompt() + closing_instruction
            max_tok = 250
        else:
            participant_input = participant_prompt()
            max_tok = 180

        participant_reply = ask_gpt(
            participant_input,
            system="You are a curious participant reacting to bots",
            history=history,
            max_tokens=max_tok
        )
        print(f"\nParticipant:\n{participant_reply}")
        history.append(f"Participant: {participant_reply}")

    return history

def run_refutational_conversation(lesson):
    """
    Run conversation with MisInfoBot, SupportBot, RefutationalBot, Participant.
    """
    try:
        truth = lesson['truth']
        refutation = lesson['refutation_essay']
        weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
        strong_argument = lesson['strongargument_written']
        all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()
    except KeyError as e:
        raise ValueError(f"Lesson data missing required key: {e}")

    history = []

    # Participant starts conversation
    participant_msg = participant_start(truth)
    print(f"\nParticipant:\n{participant_msg}")
    history.append(f"Participant: {participant_msg}")

    for idx, misinfo in enumerate(weak_args):
        # MisInfoBot turn
        misinfo_msg = ask_gpt(
            misinfo_prompt(misinfo, strong_argument, all_misinfo),
            system="You are MisInfoBot",
            history=history)
        print(f"\nMisInfoBot:\n{misinfo_msg}")
        history.append(f"MisInfoBot: {misinfo_msg}")
        intent = get_dialogue_act("MisInfoBot", misinfo_msg)

        # SupportBot responds if MisInfoBot made a claim
        if intent == "Claim":
            support_msg = ask_gpt(
                support_prompt(truth, refutation),
                system="You are SupportBot",
                history=history)
            print(f"\nSupportBot:\n{support_msg}")
            history.append(f"SupportBot: {support_msg}")
            support_intent = get_dialogue_act("SupportBot", support_msg)
        else:
            support_intent = ""

        # RefutationalBot replies only if SupportBot corrected
        if support_intent == "Correction":
            refutational_msg = ask_gpt(
                refutation_prompt(truth, refutation, last_misinfo=misinfo_msg),
                system="You are RefutationalBot",
                history=history)
            print(f"\nRefutationalBot:\n{refutational_msg}")
            history.append(f"RefutationalBot: {refutational_msg}")

        # Participant replies each round - last turn special closing
        if idx == len(weak_args) - 1:
            closing_instruction = (
                "\n### Instruction:\n"
                "For this last turn ONLY:\n"
                "- Reflect warmly and summarize your understanding.\n"
                "- Express gratitude.\n"
                "- Do NOT ask new questions or introduce new topics.\n"
            )
            participant_input = participant_prompt() + closing_instruction
            max_tok = 250
        else:
            participant_input = participant_prompt()
            max_tok = 180

        participant_reply = ask_gpt(
            participant_input,
            system="You are a curious participant reacting to bots",
            history=history,
            max_tokens=max_tok
        )
        print(f"\nParticipant:\n{participant_reply}")
        history.append(f"Participant: {participant_reply}")

    return history

def run_prebunking_conversation(lesson):
    """
    Run conversation with MisInfoBot, SupportBot, PrebunkingBot, Participant.
    """
    try:
        truth = lesson['truth']
        refutation = lesson['refutation_essay']
        weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
        strong_argument = lesson['strongargument_written']
        all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()
    except KeyError as e:
        raise ValueError(f"Lesson data missing required key: {e}")

    history = []

    # Participant starts conversation
    participant_msg = participant_start(truth)
    print(f"\nParticipant:\n{participant_msg}")
    history.append(f"Participant: {participant_msg}")

    # PrebunkingBot pre-warning before any misinformation
    prebunk_msg = ask_gpt(
        prebunk_prompt(truth, refutation, last_misinfo=""),  # Empty here: no misinformation yet
        system="You are PrebunkingBot",
        history=history)
    print(f"\nPrebunkingBot:\n{prebunk_msg}")
    history.append(f"PrebunkingBot: {prebunk_msg}")

    for idx, misinfo in enumerate(weak_args):
        # MisInfoBot turn
        misinfo_msg = ask_gpt(
            misinfo_prompt(misinfo, strong_argument, all_misinfo),
            system="You are MisInfoBot",
            history=history)
        print(f"\nMisInfoBot:\n{misinfo_msg}")
        history.append(f"MisInfoBot: {misinfo_msg}")
        intent = get_dialogue_act("MisInfoBot", misinfo_msg)

        # SupportBot responds if MisInfoBot made a claim
        if intent == "Claim":
            support_msg = ask_gpt(
                support_prompt(truth, refutation),
                system="You are SupportBot",
                history=history)
            print(f"\nSupportBot:\n{support_msg}")
            history.append(f"SupportBot: {support_msg}")
            support_intent = get_dialogue_act("SupportBot", support_msg)
        else:
            support_msg, support_intent = "", ""

        # PrebunkingBot responds only if SupportBot corrected
        prebunk_intent = "NoAction"
        if support_intent == "Correction":
            prebunk_msg = ask_gpt(
                prebunk_prompt(truth, refutation, last_misinfo=misinfo_msg),
                system="You are PrebunkingBot",
                history=history)
            prebunk_intent = get_dialogue_act("PrebunkingBot", prebunk_msg)
            if prebunk_intent == "Debunk":
                print(f"\nPrebunkingBot:\n{prebunk_msg}")
                history.append(f"PrebunkingBot: {prebunk_msg}")
        # Otherwise skip PrebunkingBot turn

        # Participant replies each round - last turn special closing
        if idx == len(weak_args) - 1:
            closing_instruction = (
                "\n### Instruction:\n"
                "For this last turn ONLY:\n"
                "- Reflect warmly on what you've learned or appreciated.\n"
                "- Clearly summarize your understanding or feelings.\n"
                "- Express gratitude.\n"
                "- Do NOT ask any questions or introduce new topics.\n"
                "- End your response with a clear concluding sentence.\n"
            )
            participant_input = participant_prompt() + closing_instruction
            max_tok = 250
        else:
            participant_input = participant_prompt()
            max_tok = 180

        participant_reply = ask_gpt(
            participant_input,
            system="You are a curious participant reacting to bots",
            history=history,
            max_tokens=max_tok
        )
        print(f"\nParticipant:\n{participant_reply}")
        history.append(f"Participant: {participant_reply}")

    return history

# === Main execution ===
if __name__ == "__main__":
    try:
        with open("lessons.json", "r", encoding="utf-8") as f:
            lessons = json.load(f)
    except FileNotFoundError:
        print("Error: lessons.json file not found.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing lessons.json: {e}")
        exit(1)

    # Let user select conversation type
    print("Select conversation mode:")
    print("1 - SupportiveConversation")
    print("2 - RefutationalConversation")
    print("3 - PrebunkingConversation")
    choice = input("Enter choice (1/2/3): ").strip()

    if choice == "1":
        conversation_history = run_supportive_conversation(lessons[0])
    elif choice == "2":
        conversation_history = run_refutational_conversation(lessons[0])
    elif choice == "3":
        # Assuming run_conversation is your existing prebunking function
        conversation_history = run_prebunking_conversation(lessons[0])
    else:
        print("Invalid choice")