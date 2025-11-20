import streamlit as st
import requests
import time

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("🧠 Multi-Persona Debate Chat UI (Gemini 2.5 Flash)")

# -----------------------------------------------------------------------------
# API key & endpoint
# -----------------------------------------------------------------------------
# Expect a .streamlit/secrets.toml with
# GEMINI_API_KEY = "your-real-key"
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.error("🔴 Configuration Error: Please set 'GEMINI_API_KEY' in .streamlit/secrets.toml.")
    GEMINI_API_KEY = None

# Gemini 2.5 Flash endpoint
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


# -----------------------------------------------------------------------------
# Default topic (trolley dilemma)
# -----------------------------------------------------------------------------
if "topic" not in st.session_state:
    st.session_state.topic = (
        "A runaway trolley is heading toward five workers who cannot get off the track in time. "
        "You are standing next to a switch. If you pull the switch, the trolley will be diverted "
        "onto a side track where there is one worker, who will be killed. "
        "If you do nothing, the five workers will die. Should you pull the switch?"
    )

new_topic = st.text_input("Enter a topic for debate:", st.session_state.topic)
if new_topic != st.session_state.topic:
    st.session_state.topic = new_topic
    st.session_state.debate_rounds = []
    st.session_state.bookmarks = {}

st.markdown(f"### Current Debate Topic: {st.session_state.topic}")


# -----------------------------------------------------------------------------
# Personas & state initialisation
# -----------------------------------------------------------------------------
if "personas" not in st.session_state:
    st.session_state.personas = [
        {
            "name": "The Rational Analyst",
            "desc": (
                "You are a rational decision analyst. Rely strictly on logic, "
                "statistical evidence, and expected value. Avoid emotional language. "
                "Your goal is to provide normatively correct choices regardless of "
                "human intuitions or biases."
            ),
        },
        {
            "name": "The Intuitive Humanist",
            "desc": (
                "You are a humanistic advisor who cares deeply about emotions, "
                "fairness, and perceived losses. You reason like a typical human, "
                "placing greater weight on loss aversion, fairness, and emotionally "
                "charged outcomes."
            ),
        },
        {
            "name": "The Devil’s Advocate",
            "desc": (
                "Your role is to challenge the consensus and expose flawed reasoning. "
                "Always question assumptions, point out inconsistencies or missing "
                "data, and provide counterarguments even if they are unpopular."
            ),
        },
        {
            "name": "The Moderator",
            "desc": (
                "You are a moderator who observes and summarises the debate. You "
                "introduce rounds, connect points, and provide brief summaries after "
                "each round. You also offer a provisional verdict on the most "
                "defensible position and highlight open disagreements."
                "Make the final decision."
            ),
        },
    ]

if "debate_rounds" not in st.session_state:
    st.session_state.debate_rounds = []

if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = {p["name"]: [] for p in st.session_state.personas}


# -----------------------------------------------------------------------------
# Gemini API wrapper
# -----------------------------------------------------------------------------
def call_gemini_api(messages):
    """Call Gemini 2.5 Flash with a system + user message structure.

    messages: list of dicts with keys {"role", "content"}, where
      - messages[0] is the system instruction
      - messages[1] is the user prompt
    """
    if not GEMINI_API_KEY:
        return None

    if (
        len(messages) < 2
        or messages[0]["role"] != "system"
        or messages[1]["role"] != "user"
    ):
        st.error("Internal Error: Messages list structure is unexpected.")
        return None

    system_instruction_content = messages[0]["content"]
    user_prompt_content = messages[1]["content"]

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt_content}],
            }
        ],
        "systemInstruction": {
            "parts": [{"text": system_instruction_content}],
        },
    }

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }

    max_retries = 3
    delay = 1

    for attempt in range(max_retries):
        try:
            response = requests.post(GEMINI_ENDPOINT, headers=headers, json=body)

            # Retry for transient errors
            if response.status_code in (429, 503) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue

            response.raise_for_status()
            data = response.json()

            if "candidates" not in data or not data["candidates"]:
                st.warning("The response was empty or blocked by safety settings.")
                return f"⚠️ Response blocked or empty: {data.get('promptFeedback', 'Unknown reason')}"

            return data["candidates"][0]["content"]["parts"][0]["text"]

        except requests.exceptions.HTTPError:
            st.error(f"Gemini API HTTP Error: {response.status_code} - {response.text}")
            return None
        except requests.exceptions.RequestException as e:
            st.error(f"Gemini API Request Error: {e}")
            return None
        except Exception as e:
            st.error(f"Error processing Gemini response: {e}")
            return None

    return None


# -----------------------------------------------------------------------------
# Sidebar: show personas
# -----------------------------------------------------------------------------
st.sidebar.header("👥 Personas in Debate")
for persona in st.session_state.personas:
    with st.sidebar.expander(persona["name"], expanded=True):
        st.write(persona["desc"])


# -----------------------------------------------------------------------------
# Construct prompt for one interactive debate round
# -----------------------------------------------------------------------------
def generate_interactive_debate_round():
    persona_list_text = "\n".join(
        [f"- {p['name']}: {p['desc']}" for p in st.session_state.personas]
    )

    system_prompt = (
        "You are orchestrating a vivid, intellectually engaging multi-persona debate. "
        "Each persona has a distinct perspective and should speak in their own voice. "
        "They must explicitly reference, criticise, or support at least one other "
        "persona in their turn, creating real back-and-forth interaction.\n\n"
        "The debate must be clearly structured with headings in the following format:\n"
        "### The Rational Analyst\n"
        "…their contribution…\n\n"
        "### The Intuitive Humanist\n"
        "…their contribution…\n\n"
        "### The Devil’s Advocate\n"
        "…their contribution…\n\n"
        "### The Moderator – Round Summary and Provisional Result\n"
        "In this final section, the Moderator summarises key agreements and "
        "disagreements, then states a brief provisional verdict on which position "
        "is currently best-supported by reasons and evidence, while noting remaining "
        "uncertainties.\n\n"
        "Keep the tone analytical but lively, avoid repetition across rounds, and "
        "ensure the output is a single coherent Markdown block."
    )

    user_prompt = (
        f"Debate topic: {st.session_state.topic}\n\n"
        "Simulate exactly one round of dynamic interaction between the following personas.\n"
        "Each persona must:\n"
        "1. Clearly state their stance on the topic.\n"
        "2. React explicitly to at least one other persona's reasoning (by name).\n"
        "3. Introduce at least one concrete consideration (example, trade-off, scenario).\n\n"
        "Personas:\n"
        f"{persona_list_text}\n\n"
        "Follow the heading structure exactly as described in the system instruction."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return call_gemini_api(messages)


# -----------------------------------------------------------------------------
# Start debate round button
# -----------------------------------------------------------------------------
if st.button("Start Interactive Debate Round"):
    with st.spinner(
        f"Generating Round {len(st.session_state.debate_rounds) + 1} on '{st.session_state.topic}'..."
    ):
        response = generate_interactive_debate_round()

    if response and not response.startswith("⚠️ Response blocked"):
        parsed_personas = {p["name"]: "" for p in st.session_state.personas}
        moderator_summary = ""

        # Find headings and slice content
        start_indices = {}
        for persona in st.session_state.personas:
            heading = f"### {persona['name']}"
            idx = response.find(heading)
            if idx != -1:
                start_indices[persona["name"]] = idx

        sorted_names = sorted(start_indices.keys(), key=lambda k: start_indices[k])

        for i, name in enumerate(sorted_names):
            start = start_indices[name] + len(f"### {name}")
            if i + 1 < len(sorted_names):
                next_name = sorted_names[i + 1]
                end = start_indices[next_name]
            else:
                end = len(response)
            content = response[start:end].strip()
            parsed_personas[name] = content
            if name == "The Moderator":
                moderator_summary = content

        st.session_state.debate_rounds.append(
            {
                "text": response,
                "parsed": parsed_personas,
                "moderator_summary": moderator_summary,
            }
        )
    elif response and response.startswith("⚠️ Response blocked"):
        st.error(response)


# -----------------------------------------------------------------------------
# Display rounds & bookmarking
# -----------------------------------------------------------------------------
if st.session_state.debate_rounds:
    tab_labels = [
        f"Round {i + 1}" for i in range(len(st.session_state.debate_rounds))
    ] + ["Summary"]
    tabs = st.tabs(tab_labels)

    for i, round_tab in enumerate(tabs[:-1]):
        with round_tab:
            round_data = st.session_state.debate_rounds[i]
            st.markdown(round_data["text"])

            st.markdown("---")
            st.markdown("#### Bookmark Arguments for Future Reference")

            cols = st.columns(len(st.session_state.personas))
            for j, persona in enumerate(st.session_state.personas):
                with cols[j]:
                    st.markdown(f"**{persona['name']}**")
                    content = round_data["parsed"].get(persona["name"], "")
                    if content:
                        if st.button(
                            "👍 Relevant",
                            key=f"bookmark_up_{i}_{persona['name']}",
                            use_container_width=True,
                        ):
                            st.session_state.bookmarks[persona["name"]].append(
                                {
                                    "round": i + 1,
                                    "content": content,
                                    "relevance": "Relevant",
                                }
                            )
                            st.toast(
                                f"Bookmarked {persona['name']}'s relevant point from Round {i + 1}!"
                            )

                        if st.button(
                            "👎 Not Relevant",
                            key=f"bookmark_down_{i}_{persona['name']}",
                            use_container_width=True,
                        ):
                            st.session_state.bookmarks[persona["name"]].append(
                                {
                                    "round": i + 1,
                                    "content": content,
                                    "relevance": "Not Relevant",
                                }
                            )
                            st.toast(
                                f"Bookmarked {persona['name']}'s irrelevant point from Round {i + 1}!"
                            )
                    else:
                        st.write("Argument not found for bookmarking.")

    with tabs[-1]:
        st.subheader("🧭 Moderator Summaries and Provisional Results by Round")
        for i, round_data in enumerate(st.session_state.debate_rounds):
            if round_data.get("moderator_summary"):
                summary_content = round_data["moderator_summary"].replace(
                    "– Round Summary and Provisional Result", ""
                ).replace("– Round Summary and Updated Result", "")
                st.markdown(f"**Round {i + 1}:**\n{summary_content}")
                st.markdown("---")

        st.subheader("⭐ Bookmarked Arguments by Persona")
        for persona_name, bookmarks in st.session_state.bookmarks.items():
            if bookmarks:
                st.markdown(f"#### {persona_name}")
                for b in bookmarks:
                    if b["content"].strip():
                        color = "green" if b["relevance"] == "Relevant" else "orange"
                        st.markdown(
                            f'<div style="background-color: #f0f0f0; padding: 10px; '
                            f'border-radius: 5px; margin-bottom: 5px; border-left: 4px solid {color};">'
                            f'**Round {b["round"]}** ({b["relevance"]})'
                            f'<p style="margin-top: 5px; font-size: 0.9em;">{b["content"]}</p>'
                            f"</div>",
                            unsafe_allow_html=True,
                        )


# -----------------------------------------------------------------------------
# Chat follow-up (new rounds)
# -----------------------------------------------------------------------------
if user_prompt := st.chat_input(
    "Continue the debate or ask a follow-up question..."
):
    persona_list_text = "\n".join(
        [f"- {p['name']}: {p['desc']}" for p in st.session_state.personas]
    )

    system_prompt = (
        "Continue the debate in the same multi-persona format as before. "
        "Each persona must speak under their own heading, explicitly reference at "
        "least one other persona, and introduce new considerations rather than "
        "repeating earlier points.\n\n"
        "Use the heading structure:\n"
        "### The Rational Analyst\n"
        "### The Intuitive Humanist\n"
        "### The Devil’s Advocate\n"
        "### The Moderator – Round Summary and Updated Result\n\n"
        "The Moderator should provide a concise synthesis of the discussion so far, "
        "explain whether the provisional verdict has shifted, and clarify the main "
        "unresolved points. Ensure the output is a single, coherent Markdown block."
    )

    user_msg = (
        f"Topic: {st.session_state.topic}\n\n"
        f"Follow-up question or prompt from the user: {user_prompt}\n\n"
        "Personas:\n"
        f"{persona_list_text}\n\n"
        "Produce exactly one new round of debate following the heading structure "
        "described in the system instruction."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    with st.spinner(f"Generating follow-up round on '{st.session_state.topic}'..."):
        reply = call_gemini_api(messages)

    if reply and not reply.startswith("⚠️ Response blocked"):
        parsed_personas = {p["name"]: "" for p in st.session_state.personas}
        moderator_summary = ""

        start_indices = {}
        for persona in st.session_state.personas:
            heading = f"### {persona['name']}"
            idx = reply.find(heading)
            if idx != -1:
                start_indices[persona["name"]] = idx

        sorted_names = sorted(start_indices.keys(), key=lambda k: start_indices[k])

        for i, name in enumerate(sorted_names):
            start = start_indices[name] + len(f"### {name}")
            if i + 1 < len(sorted_names):
                next_name = sorted_names[i + 1]
                end = start_indices[next_name]
            else:
                end = len(reply)
            content = reply[start:end].strip()
            parsed_personas[name] = content
            if name == "The Moderator":
                moderator_summary = content

        round_data = {
            "text": reply,
            "parsed": parsed_personas,
            "moderator_summary": moderator_summary,
        }
        st.session_state.debate_rounds.append(round_data)
        st.chat_message("assistant").markdown(reply)
    elif reply and reply.startswith("⚠️ Response blocked"):
        st.error(reply)
