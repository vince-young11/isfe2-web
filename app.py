# app.py — Streamlit site for your ISFE2 Assistant
# Works on Streamlit Cloud (st.secrets) and locally (.env)

import os, time
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------
# Load secrets (cloud & local)
# -----------------------------
load_dotenv(override=True)  # local dev: .env can override shell vars

API_KEY      = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")    or st.secrets.get("ASSISTANT_ID")
PROJECT_ID   = os.getenv("OPENAI_PROJECT")  or st.secrets.get("OPENAI_PROJECT")  # optional

if not API_KEY or not ASSISTANT_ID:
    st.error("Missing OPENAI_API_KEY or ASSISTANT_ID. Add them in Streamlit Secrets (cloud) or .env (local).")
    st.stop()

# If your Assistant ID looks like asst_proj_..., pass project=... to the client
client = OpenAI(api_key=API_KEY, project=PROJECT_ID) if PROJECT_ID else OpenAI(api_key=API_KEY)

# -----------------------------
# Streamlit page setup
# -----------------------------
st.set_page_config(page_title="ISFE2 Assistant", page_icon="💬")
st.title("ISFE2 Assistant")
st.caption("Ask about ISFE2 / Oracle Fusion (NHS ICB)")

with st.sidebar:
    st.markdown("### Status")
    st.write(f"API key: {'✅' if API_KEY else '❌'}  |  Assistant ID: {'✅' if ASSISTANT_ID else '❌'}")
    st.write(f"Project set: {'✅' if PROJECT_ID else '—'}")
    if st.button("Reset chat"):
        st.session_state.clear()
        st.rerun()

# -----------------------------
# Helpers
# -----------------------------
def ensure_thread():
    """Create one thread per visitor session."""
    if "thread_id" not in st.session_state:
        try:
            st.session_state.thread_id = client.beta.threads.create().id
            st.session_state.history = []
        except Exception as e:
            st.error(f"Could not create thread: {e}")
            st.stop()

def ask_assistant(thread_id: str, question: str) -> str:
    """Send a question to the Assistant, poll until the run completes, return text answer."""
    try:
        # Add user message
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=question)

        # Start a run
        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)

        # Poll for completion
        # (Simple polling keeps code portable on Streamlit Cloud)
        while True:
            r = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            if r.status == "completed":
                break
            if r.status in ("failed", "cancelled", "expired"):
                return f"Sorry—assistant run ended with status: **{r.status}**."
            time.sleep(0.4)

        # Grab the latest assistant message
        msgs = client.beta.threads.messages.list(thread_id=thread_id)
        for m in reversed(msgs.data):
            if m.role == "assistant":
                for c in m.content:
                    if c.type == "text":
                        return c.text.value
        return "No reply received—please try again."
    except Exception as e:
        return f"Error talking to assistant: `{e}`"

# -----------------------------
# UI: history + chat input
# -----------------------------
ensure_thread()

# Show prior messages
for role, msg in st.session_state.get("history", []):
    with st.chat_message(role):
        st.markdown(msg)

# Chat input
prompt = st.chat_input("Type your question…")
if prompt:
    # Echo user message
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    # Placeholder while thinking
    with st.chat_message("assistant"):
        ph = st.empty()
        ph.markdown("_Thinking…_")
        answer = ask_assistant(st.session_state.thread_id, prompt)
        ph.markdown(answer)

    # Store assistant reply
    st.session_state.history.append(("assistant", answer))
