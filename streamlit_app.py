import streamlit as st
import requests

# Config
st.set_page_config(layout="wide")
st.title("🧠 Multi-Persona Debate Chat UI")

# Fixed API key and endpoint
API_KEY = "sk-iatujsoeiwtzoffknvnpfeephnhlytkzmwiakgibxktozovz"
DASHSCOPE_ENDPOINT = "https://api.siliconflow.cn/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# Topic input
if "topic" not in st.session_state:
    st.session_state.topic = "Enter your topic here"

new_topic = st.text_input("Enter a topic for debate:", st.session_state.topic)
if new_topic != st.session_state.topic:
    st.session_state.topic = new_topic
    st.session_state.debate_rounds = []
    st.session_state.bookmarks = {}

st.markdown(f"### Topic: {st.session_state.topic}")

# Initialize session state
if "personas" not in st.session_state:
    st.session_state.personas = [
        {"name": "The Rational Analyst", "desc": "You are a rational decision analyst. Rely strictly on logic, statistical evidence, and expected value. Avoid emotional language. Your goal is to provide normatively correct choices regardless of human intuitions or biases."},
        {"name": "The Intuitive Humanist", "desc": "You are a humanistic advisor who cares deeply about emotions, fairness, and perceived losses. You reason like a typical human, placing greater weight on loss aversion, fairness, and emotionally charged outcomes."},
        {"name": "The Devil’s Advocate", "desc": "Your role is to challenge the consensus and expose flawed reasoning. Always question assumptions, point out inconsistencies or missing data, and provide counterarguments even if they are unpopular."},
        
        {"name": "The Moderator", "desc": "You are a moderator who observes and summarises the debate. You introduce rounds, connect points, and provide brief summaries after each round."},
    ]

if "debate_rounds" not in st.session_state:
    st.session_state.debate_rounds = []
if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = {}

for persona in st.session_state.personas:
    if persona['name'] not in st.session_state.bookmarks:
        st.session_state.bookmarks[persona['name']] = []

def call_dashscope_api(messages):
    body = {
        "model": "deepseek-ai/DeepSeek-R1",
        "messages": messages,
        "temperature": 0.3
    }
    response = requests.post(DASHSCOPE_ENDPOINT, headers=HEADERS, json=body)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        st.error(f"API Error: {response.status_code} - {response.text}")
        return None

# Persona display panel
st.sidebar.header("👥 Personas in Debate")
for i, persona in enumerate(st.session_state.personas):
    with st.sidebar.expander(persona["name"], expanded=True):
        st.write(persona["desc"])

def generate_interactive_debate_round():
    prompt = [
        {"role": "system", "content": "You are a debate moderator. Each persona should respond to the others' arguments as if in real conversation. Include a summary from the Moderator at the end. Use turn-taking structure with back-and-forth critique or support. Format clearly by persona."},
        {"role": "user", "content": f"Debate topic: {st.session_state.topic}\n\nSimulate one round of dynamic interaction between the following personas, each reacting to at least one other:\n" + "\n".join([f"- {p['name']}: {p['desc']}" for p in st.session_state.personas]) + "\n\nOutput a full conversational round where personas address one another’s reasoning, ending with a short summary from the Moderator."}
    ]
    return call_dashscope_api(prompt)

# Start debate round
if st.button("Start Interactive Debate Round"):
    response = generate_interactive_debate_round()
    if response:
        parsed_personas = {p['name']: "" for p in st.session_state.personas}
        moderator_summary = ""

        for persona in st.session_state.personas:
            if persona['name'] in response:
                start = response.find(persona['name'])
                next_names = [p['name'] for p in st.session_state.personas if p['name'] != persona['name'] and p['name'] in response[start:]]
                end = response.find(next_names[0], start) if next_names else len(response)
                parsed_personas[persona['name']] = response[start:end].strip()
                if persona['name'] == "The Moderator":
                    moderator_summary = parsed_personas[persona['name']]

        st.session_state.debate_rounds.append({
            "text": response,
            "parsed": parsed_personas,
            "moderator_summary": moderator_summary
        })

# Show rounds and bookmarking
if st.session_state.debate_rounds:
    tabs = st.tabs([f"Round {i+1}" for i in range(len(st.session_state.debate_rounds))] + ["Summary"])
    for i, tab in enumerate(tabs[:-1]):
        with tab:
            round_data = st.session_state.debate_rounds[i]
            st.markdown(round_data["text"])
            for persona in st.session_state.personas:
                with st.expander(f"Bookmark for {persona['name']}"):
                    content = round_data["parsed"].get(persona['name'], "")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"👍 Relevant ({persona['name']})", key=f"bookmark_up_{i}_{persona['name']}"):
                            st.session_state.bookmarks[persona['name']].append({"content": content, "relevance": "Relevant"})
                    with col2:
                        if st.button(f"👎 Not Relevant ({persona['name']})", key=f"bookmark_down_{i}_{persona['name']}"):
                            st.session_state.bookmarks[persona['name']].append({"content": content, "relevance": "Not Relevant"})

    with tabs[-1]:
        st.subheader("🧭 Moderator Summaries by Round")
        for i, round_data in enumerate(st.session_state.debate_rounds):
            if round_data.get("moderator_summary"):
                st.markdown(f"**Round {i+1}:** {round_data['moderator_summary']}")

        st.subheader("⭐ Bookmarked Arguments by Persona")
        for persona_name, bookmarks in st.session_state.bookmarks.items():
            if bookmarks:
                st.markdown(f"#### {persona_name}")
                for i, b in enumerate(bookmarks):
                    if b["content"].strip():
                        color = "success" if b["relevance"] == "Relevant" else "warning"
                        getattr(st, color)(f"Bookmark {i+1} ({b['relevance']}):\n{b['content']}")

# Chat follow-up
if user_prompt := st.chat_input("Continue the debate or ask a follow-up question..."):
    context = [
        {"role": "system", "content": "Continue responding in character as the defined personas. Each should interact, reference others’ views, and respond as in a real-time moderated debate. Include a final summary by the Moderator."},
        {"role": "user", "content": f"Topic: {st.session_state.topic}\n\nQuestion: {user_prompt}\n\nPersonas:\n" + "\n".join([f"- {p['name']}: {p['desc']}" for p in st.session_state.personas])}
    ]
    reply = call_dashscope_api(context)
    if reply:
        parsed_personas = {p['name']: "" for p in st.session_state.personas}
        moderator_summary = ""

        for persona in st.session_state.personas:
            if persona['name'] in reply:
                start = reply.find(persona['name'])
                next_names = [p['name'] for p in st.session_state.personas if p['name'] != persona['name'] and p['name'] in reply[start:]]
                end = reply.find(next_names[0], start) if next_names else len(reply)
                parsed_personas[persona['name']] = reply[start:end].strip()
                if persona['name'] == "The Moderator":
                    moderator_summary = parsed_personas[persona['name']]

        round_data = {
            "text": reply,
            "parsed": parsed_personas,
            "moderator_summary": moderator_summary
        }
        st.session_state.debate_rounds.append(round_data)
        st.chat_message("assistant").markdown(reply)
