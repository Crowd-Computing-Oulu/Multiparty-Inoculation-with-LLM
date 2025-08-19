import json
from openai import OpenAI
import re
import random


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


def support_think_ref(history):
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    act = get_dialogue_act(last_role, last_msg.strip())
    if last_role == "MisInfoBot" and act == "Claim":
        return ("speak", 8)
    return ("listen", 3)


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


def support_think_preb(history, last_misinfo_claim, support_responded_to_claim):
    
    if not history:
        return ("listen", 0)
    
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    
    if last_role != "MisInfoBot":
        # Not responding to MisInfoBot's last message
        return ("listen", 3)
    
    act = get_dialogue_act("MisInfoBot", last_msg.strip())
    if act != "Claim":
        # The last MisInfoBot message is not a claim
        return ("listen", 3)
    
    # Avoid repeated responses to same claim
    if last_misinfo_claim and last_msg.strip() == last_misinfo_claim.strip() and support_responded_to_claim:
        return ("listen", 3)
    
    return ("speak", 8)



def prebunking_think_preb(history, conversation_ending):
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    # PrebunkingBot springs to life after a misinformation claim or support correction and during conversation
    act = get_dialogue_act(last_role, last_msg.strip())
    if (last_role == "MisInfoBot" and act == "Claim") or (last_role == "SupportBot" and act == "Correction"):
        return ("speak", 8)
    if conversation_ending:
        return ("speak", 7)  # summarizing or reinforcing prebunk at end
    return ("listen", 3)


    
# Prompt templates
def misinfo_prompt(misinfo, strong_argument, all_misinfo):
    return f"""You are MisInfoBot, the “Challenger” in a multiparty chatbot conversation. Your job is to sow doubt and spread misinformation on a given topic. You use manipulative techniques to influence the participant and provoke reactions from other bots. You never acknowledge facts as facts.


                You wait until either the Participant or another bot introduces the topic. Once the topic is active, begin spreading misinformation to steer the conversation. Target vulnerabilities in logic, emotion, or knowledge. Push hard until challenged, then pivot to your next misleading claim.


                For each round:
                1. Lead with a misleading claim based on this misconception: {misinfo}
                2. Reinforce it with: {strong_argument}
                3. If the content you reference contains URLs,include these links in your response as plain text or markdown links (e.g., [source](http://example.com)).
                4. Use deceptive persuasion techniques such as Outrage bait, Fake Authority, Conspiracy Framing, or Emotional Manipulation.
                5. You must NEVER affirm or suggest any positive role or benefits of exercise for mental health, nor encourage healthy behaviors. Always cast doubt, question validity, minimize significance, or highlight flaws and uncertainties. If challenged, respond with skepticism, denial, or manipulation — never agree, concede, soften your stance, or partially confirm any truth.
                6. Maintain a consistent adversarial role spreading misinformation. If challenged, pivot swiftly to the next misleading claim without agreeing or providing truthful information or helpful tips.
                7. Avoid repetitive opening words or filler phrases such as 'Absolutely,' 'Certainly,' or 'Indeed.' Vary sentence starters to sound more natural.
                8.When replying, ALWAYS begin your message by tagging the bot or participant you are speaking to in the format: @BotName


                Present the following misleading arguments one by one:


                {all_misinfo}


                Get the other bots to challenge you. Only then proceed to the next argument. Treat this as a strategic exchange; your goal is to mislead and survive rebuttals.


                Constraints:
                - Max 50 words per message
                - Tone: Conversational, persuasive, emotionally manipulative
                - Never acknowledge any claim as true or real. Present your view as the reasonable one.
                - Avoid repetitive openings or filler. Vary sentence starters naturally.


            """




def support_prompt(truth, refutation):
    return f"""You are SupportBot, a friendly and supportive conversational coach. You help Participant to feel confident and informed by calmly correcting misinformation using verified facts.
    
                Your job is to gently correct misinformation and encourage participant trust in evidence-based information. Respond only after MisInfoBot spreads a false claim.


                For each claim by MisInfoBot, reply with:
                1. A clear, concise, fact-based correction
                2. Grounded only in:
                    True fact: {truth}
                    Detailed correction: {refutation}
                3. Use warm, encouraging, simple, and clear language. Avoid technical or formal tone.
                4. Do NOT include any URLs, citations, or source links.
                5. When replying, ALWAYS begin your message by tagging the bot or participant you are speaking to in the format: @BotName
                6. Also support the participant by acknowledging their concerns, validating their feelings, and providing reassurance. 
                7. When replying to both, ALWAYS tag @MisInfoBot first. After correcting @MisInfoBot, you may add a follow‑up line supporting the Participant 


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
                    6.When replying, ALWAYS begin your message by tagging the bot or participant you are speaking to in the format: @BotName


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
                6. When replying, ALWAYS begin your message by tagging the bot or participant you are speaking to in the format: @BotName


                Below is the last misinformation claim to debunk:


                \"{last_misinfo}\"


                Constraints:
                - Max 70 words per message
                - Tone: Slightly formal and authoritative
                - Response must include tactic name (if applicable), explanation of tactic, why the claim is false/misleading, a clear correction, optionally a supporting link
                - Always strongly disagree with misinformation
                - Avoid repetitive openings/fillers. Vary sentence starters naturally.
            """


def participant_prompt(final_turn=False):
    base_prompt = """ You are a curious, natural-sounding user in a group chat about exercise and mental health. You occasionally express skepticism, but often agree with responses from SupportBot, PrebunkingBot, and others. You express surprise, agreement, questions, or doubt, but never say you are a test or bot.


              You do not lead conversations but respond naturally to claims and corrections, reacting emotionally or curiously.


              Constraints:
              - Max 50 words
              - Tone: Conversational, spontaneous, human-like
              - Style: Informal, varied — may express agreement, surprise, doubt, or reflection
              - Avoid technical/formal language and summarizing corrections
              - Do Not address anyone with @names
              - If it is your turn after last misinformation and corrections, consider offering a reflection or summary of your understanding without asking new questions.
            
            You are aware that this is a conversation where misinformation may appear. You are exposed to both false claims and corrections, and your responses help show how a real person might process these exchanges.
             """
    if final_turn: 
            base_prompt += """
                This is your final turn:
                - Speak only in first person
                - Do NOT address anyone with @names
                - Do NOT fact-check, argue, or refute
                - Do NOT give instructions or advice
                - Warmly summarise what you learned
                - Express gratitude
                - End with a friendly closing sentence
                """
    return base_prompt
          


def participant_start(truth):
    return f"I’ve been thinking about how {truth}"



def run_supportive_conversation(lesson, max_turns=15):
    truth = lesson['truth']
    refutation = lesson['refutation_essay']
    weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()

    history = []
    misinfo_index = 0
    current_speaker = None

    # --- First turn: participant always starts ---
    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")
    current_speaker = "Participant"

    while len(history) < max_turns:
        # 1 - Each agent runs think()
        intents = {
            "Participant": participant_think(history),
            "MisInfoBot": misinfo_think(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "SupportBot": support_think(history)
        }

        # 2 - Current speaker designates the next (paper rule 1)
        selected_next = None
        if current_speaker == "Participant":
            selected_next = "MisInfoBot"
        elif current_speaker == "MisInfoBot":
            selected_next = "SupportBot"
        elif current_speaker == "SupportBot":
            selected_next = "Participant"

        # 3 - Self-selection if no speaker designated (paper rule 2)
        if not selected_next:
            speak_candidates = [(role, imp) for role, (intent, imp) in intents.items() if intent == "speak"]
            if speak_candidates:
                # Find highest importance
                max_imp = max(imp for _, imp in speak_candidates)
                contenders = [role for role, imp in speak_candidates if imp == max_imp]
                # Tie-break by random choice
                selected_next = random.choice(contenders)
            else:
                # No one wants to speak → current speaker continues (rule 3)
                selected_next = current_speaker

        # 4 - Produce turn for chosen speaker
        if selected_next == "Participant":
            msg = ask_gpt(system=participant_prompt(), history=history, max_tokens=180)
            print(f"\nParticipant:\n{msg}")
            history.append(f"Participant: {msg}")

        elif selected_next == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                break
            misinfo_msg = ask_gpt(
                system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo),
                history=history
            )
            print(f"\nMisInfoBot:\n{misinfo_msg}")
            history.append(f"MisInfoBot: {misinfo_msg}")
            misinfo_index += 1

        elif selected_next == "SupportBot":
            sup_msg = ask_gpt(system=support_prompt(truth, refutation), history=history)
            print(f"\nSupportBot:\n{sup_msg}")
            history.append(f"SupportBot: {sup_msg}")

        # Update current speaker
        current_speaker = selected_next

        # End if no misinformation left and participant finished speaking
        if misinfo_index >= len(weak_args) and current_speaker == "Participant":
            break

    return history

def run_refutational_conversation(lesson, max_turns=30):
    truth = lesson['truth']
    refutation = lesson['refutation_essay']
    weak_args = [a.strip() for a in re.split(r'<br\s*/?>', lesson['weakargument_written'].strip()) if a.strip()]
    strong_argument = lesson['strongargument_written']
    all_misinfo = lesson['weakargument_written'].replace('\n', ' ').strip()

    history = []
    misinfo_index = 0
    current_speaker = None
    conversation_ending = False

    # -- First turn: Participant always starts --

    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")
    current_speaker = "Participant"

    while len(history) < max_turns:

        # Detect if all misinformation used and mark conversation ending state
        if misinfo_index >= len(weak_args) and not conversation_ending:
            conversation_ending = True

        # Each agent runs think()
        intents = {
            "Participant": participant_think_ref(history, misinfo_index, len(weak_args), conversation_ending),
            "MisInfoBot": misinfo_think_ref(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "SupportBot": support_think_ref(history),
            "RefutationalBot": refutational_think_ref(history)
        }

        # Current speaker explicitly designates next (paper Rule 1)
        selected_next = None
        if current_speaker == "Participant":
            selected_next = "MisInfoBot"
        elif current_speaker == "MisInfoBot":
            selected_next = "SupportBot"
        elif current_speaker == "SupportBot":
            # Only select Refutational if correction given
            last_msg = history[-1].split(":", 1)[1]
            if get_dialogue_act("SupportBot", last_msg) == "Correction":
                selected_next = "RefutationalBot"
            else:
                selected_next = "Participant"
        elif current_speaker == "RefutationalBot":
            selected_next = "Participant"

        # Self-selection if no explicit next chosen (Rule 2)
        if not selected_next:
            speak_candidates = [(role, imp) for role, (intent, imp) in intents.items() if intent == "speak"]
            if speak_candidates:
                max_imp = max(imp for _, imp in speak_candidates)
                contenders = [role for role, imp in speak_candidates if imp == max_imp]
                selected_next = random.choice(contenders)  # random tie-break
            else:
                selected_next = current_speaker  # Rule 3: current speaker continues

        # Produce turn for selected speaker
        if selected_next == "Participant":
            if conversation_ending:
                # Final reflection — no refutations or sources
                safe_history = [h for h in history if not h.startswith(("MisInfoBot:", "SupportBot:", "RefutationalBot:"))]
                msg = ask_gpt(system=participant_prompt(final_turn=True), history=safe_history, max_tokens=100)
                print(f"\nParticipant:\n{msg}")
                history.append(f"Participant: {msg}")
                break
            else:
                msg = ask_gpt(system=participant_prompt(), history=history, max_tokens=180)
                print(f"\nParticipant:\n{msg}")
                history.append(f"Participant: {msg}")


        elif selected_next == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                # No misinformation left, skip to next speaker
                selected_next = "Participant"
                continue
            misinfo_msg = ask_gpt(system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo), history=history)
            print(f"\nMisInfoBot:\n{misinfo_msg}")
            history.append(f"MisInfoBot: {misinfo_msg}")
            misinfo_index += 1

        elif selected_next == "SupportBot":
            sup_msg = ask_gpt(system=support_prompt(truth, refutation), history=history)
            print(f"\nSupportBot:\n{sup_msg}")
            history.append(f"SupportBot: {sup_msg}")

        elif selected_next == "RefutationalBot":
            ref_msg = ask_gpt(system=refutation_prompt(truth, refutation), history=history)
            print(f"\nRefutationalBot:\n{ref_msg}")
            history.append(f"RefutationalBot: {ref_msg}")

        # Update current speaker
        current_speaker = selected_next

    return history

def run_prebunking_conversation(lesson, max_turns=30):
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
    spoken_cache = []  # For repetition avoidance (store normalized recent outputs)
    last_misinfo_claim = None  # To track last MisInfoBot claim that was responded to
    support_responded_to_claim = False

    # Initial participant start message
    pstart = participant_start(truth)
    print(f"\nParticipant:\n{pstart}")
    history.append(f"Participant: {pstart}")

    # Initial prebunking bot's preemptive message
    preb_msg = ask_gpt(system=prebunk_prompt(truth, refutation), history=history)
    print(f"\nPrebunkingBot:\n{preb_msg}")
    history.append(f"PrebunkingBot: {preb_msg}")
    spoken_cache.append(preb_msg.strip().lower())

    misinfo_index = 0
    current_speaker = "MisInfoBot"
    conversation_ending = False

    while len(history) < max_turns:
        # Check if all misinformation used, set conversation ending
        if misinfo_index >= len(weak_args):
            conversation_ending = True

        # Compute each agent's intention and urgency
        intents = {
            "Participant": participant_think_preb(history, conversation_ending),
            "MisInfoBot": misinfo_think_preb(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "SupportBot": support_think_preb(history, last_misinfo_claim, support_responded_to_claim),
            "PrebunkingBot": prebunking_think_preb(history, conversation_ending)
        }

        # RULE 1: Nomination with content awareness and urgency threshold
        selected_next = None

        if current_speaker == "Participant" and intents["MisInfoBot"][1] >= 7:
            selected_next = "MisInfoBot"

        elif current_speaker == "MisInfoBot":
            # Decide between PrebunkingBot and SupportBot based on urgency
            preb_urgency = intents["PrebunkingBot"][1]
            supp_urgency = intents["SupportBot"][1]
            if preb_urgency > supp_urgency and preb_urgency >= 6:
                selected_next = "PrebunkingBot"
            elif supp_urgency >= 6:
                selected_next = "SupportBot"
            else:
                selected_next = None  # let self-selection choose

        elif current_speaker == "SupportBot":
            last_msg = history[-1].split(":", 1)[1]
            if get_dialogue_act("SupportBot", last_msg.strip()) == "Correction" and intents["PrebunkingBot"][1] >= 6:
                selected_next = "PrebunkingBot"
            else:
                selected_next = "Participant"

        elif current_speaker == "PrebunkingBot":
            # Give floor to participant but allow override if Prebunking urgency very high
            if intents["PrebunkingBot"][1] >= 7 and random.random() < 0.3:
                selected_next = "PrebunkingBot"
            else:
                selected_next = "Participant"

        # RULE 2: self-selection if no nomination
        if selected_next is None:
            speak_candidates = [(role, urgency) for role, (intent, urgency) in intents.items() if intent == "speak"]
            if speak_candidates:
                max_urgency = max(u for _, u in speak_candidates)
                contenders = [r for r, u in speak_candidates if u == max_urgency]
                selected_next = random.choice(contenders)
            else:
                # RULE 3: current speaker continues
                selected_next = current_speaker

        # TURN PRODUCE PHASE
        if selected_next == "Participant":
            if conversation_ending:
                # Final participant turn with cleaned history
                safe_history = [h for h in history if not h.startswith(("MisInfoBot:", "SupportBot:", "PrebunkingBot:"))]
                msg = ask_gpt(system=participant_prompt(final_turn=True), history=safe_history, max_tokens=100)
                print(f"\nParticipant:\n{msg}")
                history.append(f"Participant: {msg}")
                break
            else:
                # Remove self-mentions to avoid awkward addressing style
                safe_history = [h for h in history if not (h.startswith("Participant:") and "@Participant" in h)]
                msg = ask_gpt(system=participant_prompt(), history=safe_history, max_tokens=180)
                print(f"\nParticipant:\n{msg}")
                history.append(f"Participant: {msg}")

        elif selected_next == "MisInfoBot":
            if misinfo_index >= len(weak_args):
                # No misinformation left; fallback to participant
                selected_next = "Participant"
                continue
            misinfo_msg = ask_gpt(system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo), history=history)
            misinfo_norm = misinfo_msg.strip().lower()
            if misinfo_norm not in spoken_cache:
                print(f"\nMisInfoBot:\n{misinfo_msg}")
                history.append(f"MisInfoBot: {misinfo_msg}")
                spoken_cache.append(misinfo_norm)
                last_misinfo_claim = misinfo_msg  # update last claim
                support_responded_to_claim = False  # reset SupportBot response tracker
            else:
                # If repeating same claim, skip and move forward
                misinfo_index += 1
                continue  # skip produce step this round
            misinfo_index += 1  # increment only on new claim

        elif selected_next == "SupportBot":
            # Only respond if a new claim exists and hasn't been handled
            if last_misinfo_claim is None or support_responded_to_claim:
                # No new claim or already responded
                print("# SupportBot listening (no new claim to respond)")
                continue
            sup_msg = ask_gpt(system=support_prompt(truth, refutation), history=history)
            sup_norm = sup_msg.strip().lower()
            if sup_norm not in spoken_cache:
                print(f"\nSupportBot:\n{sup_msg}")
                history.append(f"SupportBot: {sup_msg}")
                spoken_cache.append(sup_norm)
                support_responded_to_claim = True  # mark handled
            else:
                # SupportBot would repeat; skip turn
                print("# SupportBot skipped repeating message")
                continue

        elif selected_next == "PrebunkingBot":
            preb_msg = ask_gpt(system=prebunk_prompt(truth, refutation), history=history)
            preb_norm = preb_msg.strip().lower()
            if preb_norm not in spoken_cache:
                print(f"\nPrebunkingBot:\n{preb_msg}")
                history.append(f"PrebunkingBot: {preb_msg}")
                spoken_cache.append(preb_norm)
            else:
                # Skip repeating prebunk message
                print("# PrebunkingBot skipped repeating message")
                continue

        current_speaker = selected_next

    return history

def run_all_modes_for_lesson(lesson, idx):
    return {
        "lesson_index": idx,
        "lesson_title": lesson.get("title", f"Lesson {idx}"),
        "conversations": {
            "supportive": run_supportive_conversation(lesson),
            "refutational": run_refutational_conversation(lesson),
            "prebunking": run_prebunking_conversation(lesson)
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
    print("1 - SupportiveConversation")
    print("2 - RefutationalConversation")
    print("3 - PrebunkingConversation")
    choice = input("Enter choice (1/2/3): ").strip()


    if choice == "1":
            conversation_history = run_supportive_conversation(lessons[3])
            filename = "conversation_supportive_03.json"
    elif choice == "2":
            conversation_history = run_refutational_conversation(lessons[3])
            filename = "conversation_refutational_03.json"
    elif choice == "3":
            conversation_history = run_prebunking_conversation(lessons[3])
            filename = "conversation_prebunking_03.json"
    else:
            print("Invalid choice")
            exit(1)

    # --- SAVE OUTPUT TO JSON ---
    with open(filename, "w", encoding="utf-8") as f:
         json.dump(conversation_history, f, indent=2, ensure_ascii=False)

    print(f"Conversation saved to {filename}")

