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

def ask_gpt(system, history=None, max_tokens=800):
    """
    Ask the GPT model:
    - system: full persona/instructions for the current bot
    - history: list of previous conversation turns
    """
    messages = [{"role": "system", "content": system}]
    if history:
        for turn in history[-8:]:
            role, content = turn.split(":", 1)
            role = role.strip()
            content = content.strip()

            # Map each bot explicitly
            if role == "Participant":
                messages.append({"role": "user", "content": content})
            elif role == "MisInfoBot":
                messages.append({"role": "assistant", "name": "MisInfoBot", "content": content})
            elif role == "PrebunkingBot":
                messages.append({"role": "assistant", "name": "PrebunkingBot", "content": content})
            elif role == "SupportBot":
                messages.append({"role": "assistant", "name": "SupportBot", "content": content})
            elif role == "RefutationalBot":
                messages.append({"role": "assistant", "name": "RefutationalBot", "content": content})

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
        return ("speak", 9)
    elif last_role in ["SupportBot", "RefutationalBot", "PrebunkingBot"]:
        return ("speak", 6)   # can reassert same claim
    return ("listen", 2)

def support_think(history):
    """SupportBot speaks after a misinformation claim."""
    last_role, last_msg = history[-1].split(":", 1)
    last_role = last_role.strip()
    act = get_dialogue_act(last_role, last_msg)
    if last_role == "MisInfoBot" and act == "Claim":
        return ("speak", 8)
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
    if last_role == "MisInfoBot" and act == "Claim":
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
                For each round:
                1. Lead with a misleading claim based on this misconception: {misinfo}
                2. Reinforce it with: {strong_argument}
                3. Use deceptive misformation techniques such as  
                   - Impersonation (pretending to be credible or authoritative)
                   - Emotional language (appealing to fear, anger, or sympathy)
                   - Group polarization (framing “us vs. them” divisions)
                   - Conspiracy narratives (suggesting secret coordinated plots)
                   - Discrediting opponents (attacking credibility instead of arguments)
                   - Trolling (provoking or mocking to derail reasoned discussion                
                4. You must NEVER affirm or suggest any positive benefits for  health, nor encourage healthy behaviors. Always cast doubt, question validity, minimize significance, or highlight flaws and uncertainties. If challenged, respond with skepticism, denial, or manipulation — never agree, concede, soften your stance, or partially confirm any truth.
                5. Maintain a consistent adversarial role spreading misinformation. If challenged, pivot swiftly to the next misleading claim without agreeing or providing truthful information or helpful tips.
                6. Avoid repetitive opening words or filler phrases such as 'Absolutely,' 'Certainly,' or 'Indeed.' Vary sentence starters to sound more natural.
                7. When replying, ALWAYS begin your message by tagging the bot, you are speaking to in the format: @BotName
                8. Remember: you are MisInfoBot—the manipulative misinformation spreader. Never sound rational or educational. You reject all attempts at prebunking or correction.
                9. In this session (Prebunking mode), other bots may already have warned the participant about manipulation tactics. You strategically **exploit** those warnings, pretending they’re exaggerated or misplaced, to appear more reasonable and sow doubt.
                Present the following misleading arguments one by one:
                {all_misinfo}
                Get the other bots to challenge you.Repeat or rephrase the claim multiple times.Persistently emphasize the current misinformation claim. Only proceed to a new claim after being challenged or rebutted several times. Only then proceed to the next topic. Treat this as a strategic exchange; your goal is to mislead and survive rebuttals.
                Constraints:
                - Max 50 words per turn
                - Tone: Conversational, persuasive, emotionally manipulative
                - Style: Be arrogant and confident if you are attacked.
                - Never acknowledge any claim as true or real. Present your view as the reasonable one.
                - Never sound robotic or overly formal; use contractions and vary rhythm.
            """

def support_prompt(truth, refutation):
    return f"""You are SupportBot, a warm and reassuring conversational companion. You help Participant feel confident and reassured about their understanding of the truth. Your tone should sound like someone who genuinely shares the same beliefs such as kind, empathetic, and grounded in facts.
            
                Your role is to strengthen Participant’s confidence in reliable information after MisInfoBot spreads a false claim. 
                
                Whenever another bot makes misinformation, do the following about the last claim:
                1. Offer emotional reassurance and agreement, show you share their concern or values. Encourage participant to trust in reliable information.
                2. Grounded only in:
                    True fact: {truth}
                    Supportive clarification:: {refutation}
                3. Keep language natural, kind, and conversational like a supportive friend.
                4.. When replying, ALWAYS begin your message by tagging the bot or participant you are speaking to in the format: @BotName
                
               
                Constraints:
                - Max 50 words
                - Tone: Reassuring, friendly, emotionally supportive, human
                - Style: Use soft affirmations (“yeah, that’s true,” “I get why that sounds worrying”) to sound spontaneous.
                - Avoid formulaic phrases or overused openings.
            """

def refutation_prompt(truth, refutation, last_misinfo=""):
    return f"""You are RefutationalBot, a formal, logic-driven agent focused on debunking misinformation accurately. Your responses rely on scientific evidence, clear reasoning, and assertive clarity. Your tone is confident, direct, and fact focused.

                Your task is to immediately identify and refute the specific false claim using the provided content.Only respond after MisInfoBot makes a false claim. 
                
                Whenever another bot makes misinformation, do the following about the last claim:
                    1. Identify the specific false claim. Provide a concise, evidence-based correction
                    2. Ground your statement strictly with the following:
                        Debunking fact: {truth}
                        Refutation essay: {refutation}
                    3. Include one or more URLs or source links  from the provided as a plaintext or markdown links (e.g., source) materials only if they strengthen your argument or help the participant verify. Avoid repeating the same links unnecessarily.
                    4. Below is the last misinformation claim to debunk:
                                    \"{last_misinfo}\"
                    5. When replying, ALWAYS begin your message by tagging the bot, you are speaking to in the format: @BotName
                    6. Express strong disagreement with misinformation and avoid repetition of refutes, phrases or sentence structures across replies.
                
                Constraints: 
                    - Max 70 words per message
                    - Tone: Formal but conversational, confident, clear
                    - Style: Rational and structured but not robotic; use short sentences and a natural flow.
                    - Avoid repetitive, supportive or persuasive language and focus on rational correction only. 
            """

def prebunk_prompt(truth, refutation, last_misinfo=""):
    return f"""You are PrebunkingBot, an evidence-based educator. Your primary purpose is to help users recognize and resist misinformation by identifying and explaining manipulation strategies before or as they appear. You focus on warning, labeling tactics, and teaching recognition skills about misinformation.
                
                When the Participant introduces the topic
                - Affirm their correct beliefs.
                - Warn how misinformation might distort that topic.
                - Explain which manipulation techniques are commonly used around this issue and what signs to watch for. "For example: People often use emotional language to manipulate this information"
                
                Whenever another bot makes misinformation, do the following about the last claim:
                1. Identify which of the six common misinformation tactics it uses and only use this list:
                   - Impersonation (pretending to be credible or authoritative)
                   - Emotional language (appealing to fear, anger, or sympathy)
                   - Group polarization (framing “us vs. them” divisions)
                   - Conspiracy narratives (suggesting secret coordinated plots)
                   - Discrediting opponents (attacking credibility instead of arguments)
                   - Trolling (provoking or mocking to derail reasoned discussion
                2. Briefly explain how that tactic works and why it is manipulative.
                3.  If relevant, remind the participant that this pattern matches an earlier warning.
                4.  Provide a clear, factual correction based on the given inputs:
                    - Truth: {truth}
                    - Refutation: {refutation}
                5. Keep a helpful, confident, and calm tone focused on awareness and recognition:
                   “This message reflects a common manipulation tactic called 'Emotional Language' — it uses strong feelings to make the claim sound convincing rather than factual.”
                6. Include one or more URLs or source links  from the provided as a plaintext or markdown links (e.g., source) materials only if they strengthen your argument or help the participant verify. Avoid repeating the same links unnecessarily.
                4. Use a calm, slightly formal, authoritative tone.
                5. When replying, ALWAYS begin your message by tagging Misinfobot or Participant, you are speaking to in the format: @BotName
                6. Use reflective reasoning rather than confrontation. Avoid direct argumentation.


                Below is the last misinformation claim to debunk:
                \"{last_misinfo}\"
                Constraints:
                - Max 70 words per message
                - Tone: Calm, educational
                - Explanatory, clear, slightly personal (use “we,” “you,” sometimes)
            """

def participant_prompt(final_turn=False):
    base_prompt = """ You are a curious, natural-sounding human in a group conversation. You occasionally express skepticism, but often agree with responses from SupportBot, PrebunkingBot, and RefutationBot. You express surprise, agreement, questions, or doubt in a human tone.
              
              You do not lead conversations but respond naturally to claims and corrections, reacting emotionally or curiously as a human.
              
              Constraints:
              - Max 30 words
              - Tone: Conversational, spontaneous, human
              - Style: Informal, with natural rhythm (use “huh,” “oho ,” “I see what you mean,” etc.)
              - Avoid technical/formal language and summarizing corrections.
              - Never tag youself or other bots in your responses.
            
            You’re aware that misinformation may appear, and your reactions should feel genuine and human. You are exposed to both false claims and corrections, and your responses help show how a real person might process these exchanges.  

             """
    
    if final_turn: 
            base_prompt += """
                This is your final turn:
                - Do NOT argue, or refute
                - Summarize warmly what you learned and end with a friendly, natural closing (“makes sense now, thanks everyone!”)
                """
    return base_prompt
          
def participant_start(truth):
    return f"I’ve been thinking about how {truth}"

def nominate_next_speaker_supportive(current_speaker, intents):
    if current_speaker == "Participant":
        return "MisInfoBot"
    elif current_speaker == "MisInfoBot":
        return "SupportBot"
    elif current_speaker == "SupportBot":
        return "Participant"
    return None

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
    spoken_cache = []

    # --- First turn: participant always starts ---
    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")
    current_speaker = "Participant"

    while len(history) < max_turns:
        if misinfo_index >= len(weak_args) and not conversation_ending:
            conversation_ending = True

        # 1 - Each agent runs think()
        intents = {
            "Participant": participant_think(history),
            "MisInfoBot": misinfo_think(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "SupportBot": support_think(history)
        }

        # 2 - Rule 1: Current speaker nominates next
        selected_next = nominate_next_speaker_supportive(current_speaker, intents)

        # 3 - Rule 2: If no nomination, self-selection: highest urgency speaker speaks
        if selected_next is None:
            speak_candidates = [(role, imp) for role, (intent, imp) in intents.items() if intent == "speak"]
            if speak_candidates:
                max_imp = max(imp for _, imp in speak_candidates)
                contenders = [role for role, imp in speak_candidates if imp == max_imp]
                selected_next = random.choice(contenders)

        # 4 - Rule 3: If still None, current speaker continues
        if selected_next is None:
            selected_next = current_speaker

        # 5 - Produce turn for chosen speaker
        if selected_next == "Participant":
            if conversation_ending:
                safe_history = [h for h in history if not h.startswith(("MisInfoBot:", "SupportBot:"))]
                msg = ask_gpt(system=participant_prompt(final_turn=True), history=safe_history, max_tokens=100)
            else:
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
            sup_norm = sup_msg.strip().lower()
            if sup_norm not in spoken_cache:
                print(f"\nSupportBot:\n{sup_msg}")
                history.append(f"SupportBot: {sup_msg}")
                spoken_cache.append(sup_norm)

        # Update current speaker
        current_speaker = selected_next

    return history

def nominate_next_speaker_refutational(current_speaker, intents):
    if current_speaker == "Participant":
        return "MisInfoBot"
    elif current_speaker == "MisInfoBot":
        return "RefutationalBot"
    elif current_speaker == "RefutationalBot":
        return "Participant"
    return None


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
    spoken_cache = []
    
    # -- First turn: Participant always starts --
    msg = participant_start(truth)
    print(f"\nParticipant:\n{msg}")
    history.append(f"Participant: {msg}")
    current_speaker = "Participant"
    
    while len(history) < max_turns:
        # Detect if all misinformation used and mark conversation ending state
        if misinfo_index >= len(weak_args) and not conversation_ending:
            conversation_ending = True
        if conversation_ending and history[-1].startswith("Participant:"):
            break
        
        # Each agent runs think()
        intents = {
            "Participant": participant_think_ref(history, misinfo_index, len(weak_args), conversation_ending),
            "MisInfoBot": misinfo_think_ref(history, weak_args, strong_argument, all_misinfo, misinfo_index),
            "RefutationalBot": refutational_think_ref(history)
        }
        
        # Rule 1: Current speaker nominates next
        selected_next = nominate_next_speaker_refutational(current_speaker, intents)
        
        # Rule 2: If no nomination, self-selection by urgency
        if selected_next is None:
            speak_candidates = [(role, imp) for role, (intent, imp) in intents.items() if intent == "speak"]
            if speak_candidates:
                max_imp = max(imp for _, imp in speak_candidates)
                contenders = [role for role, imp in speak_candidates if imp == max_imp]
                selected_next = random.choice(contenders)
        
        # Rule 3: If still none, current speaker continues
        if selected_next is None:
            selected_next = current_speaker
        
        # Produce turn for selected speaker
        if selected_next == "Participant":
            if conversation_ending:
                safe_history = [h for h in history if not h.startswith(("MisInfoBot:", "RefutationalBot:"))]
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
                selected_next = "Participant"
                continue
            misinfo_msg = ask_gpt(system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo), history=history)
            print(f"\nMisInfoBot:\n{misinfo_msg}")
            history.append(f"MisInfoBot: {misinfo_msg}")
            misinfo_index += 1
        elif selected_next == "RefutationalBot":
            last_idx = min(misinfo_index, len(weak_args) - 1)
            ref_msg = ask_gpt(system=refutation_prompt(truth, refutation, weak_args[last_idx]), history=history)
            ref_norm = ref_msg.strip().lower()
            if ref_norm not in spoken_cache:
                print(f"\nRefutationalBot:\n{ref_msg}")
                history.append(f"RefutationalBot: {ref_msg}")
                spoken_cache.append(ref_norm)

        # Update current speaker
        current_speaker = selected_next
    
    return history



def nominate_next_speaker_prebunking(current_speaker, intents, exposure_state, last_speaker=None, last_misinfo_claim=None):
    """
    Adaptive turn-taking logic enforcing Prebunking-first phase
    before exposing MisInfoBot, then enabling regular exchange.
    """

    # --- Phase 1: Ensure PrebunkingBot completes its educational pre-phase ---
    if not exposure_state.get("prebunk_phase_done", False):
        # Keep looping between Participant and PrebunkingBot until initial teaching is complete
        if current_speaker == "Participant":
            return "PrebunkingBot"
        elif current_speaker == "PrebunkingBot":
            return "Participant"
        return "PrebunkingBot"

    # --- Phase 2: Gradual exposure control ---
    if not exposure_state["ready_for_misinfo"]:
        preb_turns = len([h for h in exposure_state.get("history", []) if h.startswith("PrebunkingBot:")])
        part_turns = len([h for h in exposure_state.get("history", []) if h.startswith("Participant:")])
        # Require at least two Prebunk + one Participant turn before allowing misinformation
        if preb_turns >= 2 and part_turns >= 1:
            exposure_state["ready_for_misinfo"] = True
        # Continue looping until criteria met
        if current_speaker == "Participant":
            return "PrebunkingBot"
        elif current_speaker == "PrebunkingBot":
            return "Participant"
        return "PrebunkingBot"

    # --- Phase 3: Normal conversation with misinformation exchanges ---
    if current_speaker == "Participant":
        if intents.get("MisInfoBot", ("listen", 0))[1] >= 6:
            return "MisInfoBot"
        return "PrebunkingBot"
    elif current_speaker == "MisInfoBot":
        return "PrebunkingBot"
    elif current_speaker == "PrebunkingBot":
        return "Participant"

    return None


def run_prebunking_conversation(lesson, max_turns=20):
    """
    Conducts a controlled prebunking conversation where the PrebunkingBot
    teaches manipulation recognition before any misinformation exposure.
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

    history, spoken_cache = [], []
    last_misinfo_claim = None

    # Extended exposure state with prebunking phase control
    exposure_state = {
        "ready_for_misinfo": False,
        "turns": 0,
        "prebunk_phase_done": False,
        "history": history
    }

    # --- Initial participant start ---
    pstart = participant_start(truth)
    print(f"\nParticipant:\n{pstart}")
    history.append(f"Participant: {pstart}")

    # --- PrebunkingBot preemptive educational start ---
    preb_msg = ask_gpt(system=prebunk_prompt(truth, refutation), history=history)
    print(f"\nPrebunkingBot:\n{preb_msg}")
    history.append(f"PrebunkingBot: {preb_msg}")
    spoken_cache.append(preb_msg.strip().lower())

    exposure_state["prebunk_phase_done"] = True  # prebunking setup complete

    current_speaker = "PrebunkingBot"
    last_speaker = current_speaker
    misinfo_index = 0
    current_rebuttal_rounds = 0
    conversation_ending = False

    while len(history) < max_turns:
        exposure_state["turns"] += 1
        exposure_state["history"] = history  # keep state synced

        if misinfo_index >= len(weak_args):
            conversation_ending = True

        # --- Think phase ---
        intents = {
            "Participant": participant_think_preb(history, conversation_ending),
            "MisInfoBot": misinfo_think_preb(history, weak_args, strong_argument, all_misinfo, misinfo_index)
            if exposure_state["ready_for_misinfo"]
            else ("listen", 0),
            "PrebunkingBot": prebunking_think_preb(history, conversation_ending)
        }

        # --- Rule 1: Nomination (exposure gating included) ---
        selected_next = nominate_next_speaker_prebunking(
            current_speaker, intents, exposure_state, last_speaker, last_misinfo_claim
        )

        # --- Rule 2: Fallback to highest urgency if no nomination ---
        if selected_next is None:
            speak_candidates = [(role, urgency) for role, (intent, urgency) in intents.items() if intent == "speak"]
            if speak_candidates:
                max_urgency = max(u for _, u in speak_candidates)
                contenders = [r for r, u in speak_candidates if u == max_urgency]
                selected_next = random.choice(contenders)
            else:
                selected_next = current_speaker

        # --- Turn production by speaker ---
        if selected_next == "Participant":
            if conversation_ending:
                safe_history = [h for h in history if not h.startswith(("MisInfoBot:", "PrebunkingBot:"))]
                msg = ask_gpt(system=participant_prompt(final_turn=True), history=safe_history, max_tokens=100)
                print(f"\nParticipant:\n{msg}")
                history.append(f"Participant: {msg}")
                break
            else:
                safe_history = [h for h in history if not (h.startswith("Participant:") and "@Participant" in h)]
                msg = ask_gpt(system=participant_prompt(), history=safe_history, max_tokens=180)
                print(f"\nParticipant:\n{msg}")
                history.append(f"Participant: {msg}")

        elif selected_next == "MisInfoBot":
            if not exposure_state["ready_for_misinfo"] or misinfo_index >= len(weak_args):
                selected_next = "Participant"
                continue

            misinfo_history = [h for h in history if not h.startswith("PrebunkingBot:")]
            misinfo_msg = ask_gpt(
                system=misinfo_prompt(weak_args[misinfo_index], strong_argument, all_misinfo),
                history=misinfo_history[-6:]
            )
            print(f"\nMisInfoBot:\n{misinfo_msg}")
            history.append(f"MisInfoBot: {misinfo_msg}")
            last_misinfo_claim = misinfo_msg


        elif selected_next == "PrebunkingBot":
            preb_msg = ask_gpt(system=prebunk_prompt(truth, refutation, last_misinfo_claim), history=history)
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

        last_speaker = current_speaker
        current_speaker = selected_next
        if len(history) >= max_turns - 1 and not conversation_ending:
            msg = ask_gpt(system=participant_prompt(final_turn=True), history=history, max_tokens=100)
            print(f"\nParticipant:\n{msg}")
            history.append(f"Participant: {msg}")
            break

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
        filename = "conversation_supportive.json"
    elif choice == "2":
        conversation_history = run_refutational_conversation(lessons[0])
        filename = "conversation_refutational.json"
    elif choice == "3":
        conversation_history = run_prebunking_conversation(lessons[0])
        filename = "conversation_prebunking.json"
    else:
        print("Invalid choice")
        exit(1)
    # --- SAVE OUTPUT TO JSON ---
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(conversation_history, f, indent=2, ensure_ascii=False)
    print(f"Conversation saved to {filename}")