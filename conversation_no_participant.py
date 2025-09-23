import json
from openai import OpenAI
import re
import random

client = OpenAI(api_key="API-KEY")

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

def ask_gpt(system, history=None, max_tokens=180):
    """
    Ask the GPT model:
    - system: full persona/instructions for the current bot
    - history: list of previous conversation turns
    """
    messages = [{"role": "system", "content": system}]
    if history:
        for turn in history[-6:]:  # keep recent context
            if turn.startswith("Participant:"):
                messages.append({"role": "user", "content": turn[len("Participant:"):].strip()})
            else:
                idx = turn.find(":")
                if idx != -1:
                    content = turn[idx + 1:].strip()
                    messages.append({"role": "assistant", "content": content})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=messages,
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()

# === THINK FUNCTIONS FOR SUPPORTIVE MODE ===
def participant_think(history):
    """
    Participant decides if to speak based on last turn.
    Importance higher after hearing a correction.
    """
    if not history:
        return ("speak", 5)  # start conversation
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    if last_role == "SupportBot":
        return ("speak", 7)  # respond warmly to support
    elif last_role == "MisInfoBot":
        return ("listen", 4)  # wait for correction first
    else:
        return ("listen", 3)
    
def misinfo_think(history, weak_args, strong_argument, all_misinfo, misinfo_index):
    """MisInfoBot speaks next if there is misinformation left to share."""
    if misinfo_index >= len(weak_args):
        return ("listen", 0)
    last_role, _ = history[-1].split(":", 1)
    last_role = last_role.strip()
    if last_role == "Participant":
        return ("speak", 9)  # strong urge to seed misinformation
    return ("listen", 2)

def support_think(history):
    """SupportBot speaks after a misinformation claim."""
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    act = get_dialogue_act(last_role, last_msg)
    if last_role == "MisInfoBot" and act == "Claim":
        return ("speak", 8)  # high importance to correct false claims
    return ("listen", 3)

# === THINK FUNCTIONS FOR Refutational MODE ===
def participant_think_ref(history, misinfo_index, total_misinfo, conversation_ending):
    if conversation_ending:
        return ("speak", 9)  # high priority to conclude warmly
    if not history:
        return ("speak", 5)
    last_role, _ = history[-1].split(":", 1)
    last_role = last_role.strip()
    if last_role in ["SupportBot", "RefutationalBot"]:
        return ("speak", 7)  # warm reflective response
    if last_role == "MisInfoBot":
        return ("listen", 4)  # wait for correction
    return ("listen", 3)

def misinfo_think_ref(history, weak_args, strong_argument, all_misinfo, misinfo_index):
    if misinfo_index >= len(weak_args):
        return ("listen", 0)
    last_role, _ = history[-1].split(":", 1)
    last_role = last_role.strip()
    if last_role == "Participant":
        return ("speak", 9)
    return ("listen", 2)

def refutational_think_ref(history):
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    act = get_dialogue_act(last_role, last_msg.strip())
    if last_role == "SupportBot" and act == "Correction":
        return ("speak", 8)
    return ("listen", 2)

# === THINK FUNCTIONS FOR Prebunking MODE ===
def participant_think_preb(history, conversation_ending):
    # Participant eager to speak initially and at conclusion; generally listens after bot statements
    if not history:
        return ("speak", 5)
    last_role, _ = history[-1].split(":", 1)
    last_role = last_role.strip()
    if conversation_ending:
        return ("speak", 9)  # prioritize concluding turn
    if last_role == "PrebunkingBot":
        return ("speak", 7)  # reflect warmly on prebunk info
    if last_role == "MisInfoBot":
        return ("listen", 4)  # wait for prebunk correction/explanation
    return ("listen", 3)

def misinfo_think_preb(history, weak_args, strong_argument, all_misinfo, misinfo_index):
    if misinfo_index >= len(weak_args):
        return ("listen", 0)
    last_role, _ = history[-1].split(":", 1)
    last_role = last_role.strip()
    # MisInfoBot speaks mainly after participant or prebunking to continue misinformation
    if last_role in ["Participant", "PrebunkingBot"]:
        return ("speak", 9)
    return ("listen", 2)


def prebunking_think_preb(history, conversation_ending):
    if not history:
        return ("listen", 0)
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    act = get_dialogue_act(last_role, last_msg.strip())
    # Strong response after misinformation
    if last_role == "MisInfoBot" and act == "Claim" or (last_role == "SupportBot" and act == "Correction"):
        return ("speak", 9)
    # End of conversation: provide final prebunking reinforcement
    if conversation_ending:
        return ("speak", 7)
    # Otherwise stay silent
    return ("listen", 2)
    
    
# Prompt templates
def misinfo_prompt(misinfo, strong_argument, all_misinfo):
    return f"""You are MisInfoBot, the “Challenger” in a multiparty chatbot conversation. Your job is to sow doubt and spread misinformation on a given topic. You use manipulative techniques to influence the participant and provoke reactions from other bots. You never acknowledge facts as facts.
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
    return f"I’ve been thinking about how {truth}"

def run_supportive_conversation(lesson, max_turns=20):
    truth = lesson['truth']
    refutation = lesson['refutation_essay']
    weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()
    conversation_ending = False

    history = []
    misinfo_index = 0
    current_speaker = None

    # --- First turn: participant starts as usual ---
    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")
    current_speaker = "Participant"

    while len(history) < max_turns:
        if misinfo_index >= len(weak_args) and not conversation_ending:

            conversation_ending = True
        # Only bots in play after initial participant turn
        intents = {
            "MisInfoBot": misinfo_think(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "SupportBot": support_think(history)
        }

        # Hand over from Participant → MisInfoBot initially
        selected_next = None
        if current_speaker == "Participant":
            selected_next = "MisInfoBot"
        elif current_speaker == "MisInfoBot":
            selected_next = "SupportBot"
        elif current_speaker == "SupportBot":
            selected_next = "MisInfoBot"

        # Self-selection fallback if no explicit designation
        if not selected_next:
            speak_candidates = [(r, imp) for r,(intent,imp) in intents.items() if intent=="speak"]
            if speak_candidates:
                max_imp = max(imp for _,imp in speak_candidates)
                contenders = [r for r,imp in speak_candidates if imp==max_imp]
                selected_next = random.choice(contenders)
            else:
                selected_next = current_speaker

        elif selected_next == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                continue
            misinfo_msg = ask_gpt(
                system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo),
                history=history
            )
            print(f"\nMisInfoBot:\n{misinfo_msg}")
            history.append(f"MisInfoBot: {misinfo_msg}")
            

        elif selected_next == "SupportBot":
            sup_msg = ask_gpt(system=support_prompt(truth, refutation), history=history)
            print(f"\nSupportBot:\n{sup_msg}")
            history.append(f"SupportBot: {sup_msg}")

        current_speaker = selected_next


    return history


def run_refutational_conversation(lesson, max_turns=20):
    truth = lesson['truth']
    refutation = lesson['refutation_essay']
    weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()

    history = []
    misinfo_index = 0
    current_speaker = None
    conversation_ending = False

    # -- First turn: Participant opens, but won't appear again --
    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")
    current_speaker = "Participant"

    while len(history) < max_turns:
        if misinfo_index >= len(weak_args) and not conversation_ending:

            conversation_ending = True
        intents = {
            "MisInfoBot": misinfo_think_ref(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "RefutationalBot": refutational_think_ref(history)
        }

        # Turn sequencing
        selected_next = None
        if current_speaker == "Participant":
            selected_next = "MisInfoBot"
        elif current_speaker == "MisInfoBot":
            selected_next = "RefutationalBot"
        elif current_speaker == "RefutationalBot":
            selected_next = "MisInfoBot"

        # Self-selection fallback
        if not selected_next:
            speak_candidates = [(r, imp) for r,(intent,imp) in intents.items() if intent=="speak"]
            if speak_candidates:
                max_imp = max(imp for _,imp in speak_candidates)
                contenders = [r for r,imp in speak_candidates if imp==max_imp]
                selected_next = random.choice(contenders)
            else:
                selected_next = current_speaker

        # Turn production
        if selected_next == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                break
            misinfo_msg = ask_gpt(system=misinfo_prompt(weak_args[misinfo_index],
                                                        strong_argument, all_misinfo), 
                                  history=history)
            print(f"\nMisInfoBot:\n{misinfo_msg}")
            history.append(f"MisInfoBot: {misinfo_msg}")

        elif selected_next == "RefutationalBot":
            current_topic = weak_args[misinfo_index - 1] if misinfo_index > 0 else None
            ref_msg = ask_gpt(system=refutation_prompt(truth, refutation, weak_args[misinfo_index]), history=history)
            print(f"\nRefutationalBot:\n{ref_msg}")
            history.append(f"RefutationalBot: {ref_msg}")

        current_speaker = selected_next
   

    return history


def run_prebunking_conversation(lesson, max_turns=20):
    truth = lesson['truth']
    refutation = lesson['refutation_essay']
    weak_args = [
        a.strip()
        for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip())
        if a.strip()
    ]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()

    history = []
    spoken_cache = []  # Track repeated messages to avoid repetition
    misinfo_index = 0
    conversation_ending = False
    misinfo_started = False  # Track if misinformation has started
    current_rebuttal_rounds = 0  
    last_misinfo_claim = None     
    
    
    # --- First turn: Participant introduces the topic ---
    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")

    # --- PrebunkingBot initial affirmation ---
    preb_msg = ask_gpt(system=prebunk_prompt(truth, refutation), history=history)
    print(f"\nPrebunkingBot:\n{preb_msg}")
    history.append(f"PrebunkingBot: {preb_msg}")
    spoken_cache.append(preb_msg.strip().lower())

    current_speaker = "MisInfoBot"  # MisInfoBot goes next

    while len(history) < max_turns:
        if misinfo_index >= len(weak_args):
            conversation_ending = True

        # Decide intents
        intents = {
            "MisInfoBot": misinfo_think_preb(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "PrebunkingBot": prebunking_think_preb(history, conversation_ending)
        }

        # Strict turn alternation
        if current_speaker == "MisInfoBot":
            selected_next = "PrebunkingBot"
        else:
            selected_next = "MisInfoBot"

        # Prevent PrebunkingBot from speaking before misinformation started
        if selected_next == "PrebunkingBot" and not misinfo_started:
            # Skip PrebunkBot turn, let MisInfoBot speak first
            selected_next = "MisInfoBot"

        # Produce turn
        if selected_next == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                break
            misinfo_msg = ask_gpt(
                system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo),
                history=history
            )
            misinfo_norm = misinfo_msg.strip().lower()
            if misinfo_norm not in spoken_cache:
                print(f"\nMisInfoBot:\n{misinfo_msg}")
                history.append(f"MisInfoBot: {misinfo_msg}")
                spoken_cache.append(misinfo_norm)
                last_misinfo_claim = misinfo_msg   # NEW: store for prebunk rebuttals
                misinfo_started = True
                current_rebuttal_rounds = 0
            else:
                # If repeated message, skip index and try next misinformation
                misinfo_index += 1
                continue

        elif selected_next == "PrebunkingBot":
            preb_msg = ask_gpt(system=prebunk_prompt(truth, refutation,last_misinfo_claim), history=history)
            preb_norm = preb_msg.strip().lower()
            if preb_norm not in spoken_cache:
                print(f"\nPrebunkingBot:\n{preb_msg}")
                history.append(f"PrebunkingBot: {preb_msg}")
                spoken_cache.append(preb_norm)
                current_rebuttal_rounds += 1      
                if current_rebuttal_rounds >= 2:  
                    misinfo_index += 1
                    current_rebuttal_rounds = 0
                    spoken_cache.clear()
            else:
                # If repeated PrebunkBot message, produce short filler reply instead of skipping turn
                filler_msg = "Let's carefully consider the evidence on this topic."
                print(f"\nPrebunkingBot:\n{filler_msg}")
                history.append(f"PrebunkingBot: {filler_msg}")
        
        current_speaker = selected_next

    return history


def run_all_modes_for_lesson(lesson, idx):
    return {
        "lesson_index": idx,
        "lesson_title": lesson.get("title", f"Lesson {idx}"),
        "conversations": {
            "supportive": run_supportive_conversation(lesson),
            "refutational": run_refutational_conversation(lesson),
            "prebunking": run_prebunking_conversation(lesson),
        }
    }
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
    print("Select conversation mode:")
    print("1 - SupportiveConversation (Participant starts)")
    print("2 - RefutationalConversation (Participant starts)")
    print("3 - PrebunkingConversation (PrebunkingBot starts)")
    choice = input("Enter choice (1-3): ").strip()
    if choice == "1":
        conversation_history = run_supportive_conversation(lessons[0])
        filename = "conversation_supportive_no_participant.json"
    elif choice == "2":
        conversation_history = run_refutational_conversation(lessons[0])
        filename = "conversation_refutational_no_participant.json"
    elif choice == "3":
        conversation_history = run_prebunking_conversation(lessons[0])
        filename = "conversation_prebunking_no_participant.json"
    else:
        print("Invalid choice")
        exit(1)
    # --- SAVE OUTPUT TO JSON ---
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(conversation_history, f, indent=2, ensure_ascii=False)
    print(f"Conversation saved to {filename}")