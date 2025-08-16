# app.py — Streamlit site for your ISFE2 Assistant (no Project ID)
# Reads OPENAI_API_KEY and ASSISTANT_ID from Streamlit Secrets (cloud) or .env (local).

import os, time
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Load secrets ----------
load_dotenv(override=True)  # local .env if present

def get_secret(name: str):
    val = st.secrets.get(name) or os.getenv(name)
    return val.strip() if isinstance(val, str) else val

API_KEY      = get_secret("OPENAI_API_KEY")
ASSISTANT_ID = get_secret("ASSISTANT_ID")

if not API_KEY or not ASSISTANT_ID:
    st.error("Missing OPENAI_API_KEY or ASSISTANT_ID. Add them in Streamlit Secrets (or .env locally).")
    st.stop()

# Guard: this build expects a plain assistant id (asst_...), not asst_proj_...
if ASSISTANT_ID.startswith("asst_proj_"):
    st.error("Your ASSISTANT_ID looks project-scoped (asst_proj_...). "
             "Please use the plain 'asst_' ID from the same Project, or switch back to the project-aware build.")
    st.stop()

# Create client WITHOUT a project parameter
client = OpenAI(api_key=API_KEY)

# (optional masked debug—safe to keep or remove)
def mask(s): 
    return f"{s[:7]}…{s[-4:]}" if isinstance(s, str) and len(s) >= 12 else str(bool(s))

# ---------- Page ----------
st.set_page_config(page_title="ISFE2 Assistant", page_icon="💬")
st.title("ISFE2 Assistant")
st.caption("Ask about ISFE2 / Oracle Fusion (NHS ICB)")

with st.sidebar:
    st.markdown("### Status")
    st.write(f"API key: {mask(API_KEY)}  |  Assistant ID: {ASSISTANT_ID[:5]}…")
    if st.button("Reset chat"):
        st.session_state.clear()
        st.rerun()

# ---------- Helpers ----------
def ensure_thread():
    if "thread_id" not in st.session_state:
        try:
            st.session_state.thread_id = client.beta.threads.create().id
            st.session_state.history = []
        except Exception as e:
            st.error(f"Could not create thread: {e}")
            st.stop()

def ask_assistant(thread_id: str, question: str) -> str:
    try:
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=question)
        run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)

        # poll until done
        while True:
            r = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            if r.status == "completed":
                break
            if r.status in ("failed", "cancelled", "expired"):
                return f"Sorry—assistant run ended with status: **{r.status}**."
            time.sleep(0.4)

        # read latest assistant message
        msgs = client.beta.threads.messages.list(thread_id=thread_id)
        for m in reversed(msgs.data):
            if m.role == "assistant":
                for c in m.content:
                    if c.type == "text":
                        return c.text.value
        return "No reply received—please try again."
    except Exception as e:
        return f"Error talking to assistant: `{e}`"

# ---------- UI ----------
ensure_thread()

# show history
for role, msg in st.session_state.get("history", []):
    with st.chat_message(role):
        st.markdown(msg)

prompt = st.chat_input("Type your question…")
if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        ph = st.empty()
        ph.markdown("_Thinking…_")
        answer = ask_assistant(st.session_state.thread_id, prompt)
        ph.markdown(answer)

    st.session_state.history.append(("assistant", answer))
