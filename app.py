# app.py — simple website for your ISFE2 Assistant
import os, time
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# Load .env (API key + assistant id)
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("ASSISTANT_ID")
if not API_KEY or not ASSISTANT_ID:
    st.error("Missing OPENAI_API_KEY or ASSISTANT_ID in .env")
    st.stop()

client = OpenAI(api_key=API_KEY)

st.set_page_config(page_title="ISFE2 Assistant", page_icon="💬")
st.title("ISFE2 Assistant")
st.caption("Ask about ISFE2 / Oracle Fusion (NHS ICB)")

# One conversation per visitor
if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id
    st.session_state.history = []

# Show chat history
for role, msg in st.session_state.history:
    with st.chat_message(role):
        st.markdown(msg)

prompt = st.chat_input("Type your question…")
if prompt:
    # show user message
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    # send to assistant
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )

    # run assistant with your project’s system instructions & File Search
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=ASSISTANT_ID
    )

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.write("_Thinking…_")

    # poll until done
    while True:
        r = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread_id, run_id=run.id
        )
        if r.status == "completed":
            break
        if r.status in ("failed","cancelled","expired"):
            placeholder.error(f"Run status: {r.status}")
            st.stop()
        time.sleep(0.4)

    # read reply
    msgs = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
    answer = ""
    for m in reversed(msgs.data):
        if m.role == "assistant":
            for c in m.content:
                if c.type == "text":
                    answer = c.text.value
                    break
            if answer:
                break

    st.session_state.history.append(("assistant", answer))
    with st.chat_message("assistant"):
        st.markdown(answer)
