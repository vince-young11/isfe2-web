# app.py — Streamlit site for your ISFE2 Assistant (uses your doc as extra instructions)
# Works on Streamlit Cloud (st.secrets) and locally (.env)

import os, time
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Secrets / config ----------
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
             "Please use the plain 'asst_' ID from the same Project (or switch to a project-aware build).")
    st.stop()

client = OpenAI(api_key=API_KEY)

# ---------- Your ISFE2 behaviour (from the attached Word doc) ----------
INSTRUCTIONS = """
You are the ISFE2 Assistant Agent for NHS ICB staff using Oracle Fusion (ISFE2).

# Purpose
- Provide step-by-step guidance for finance processes in Oracle Fusion (AP, AR, PO, Journals, Budgeting).
- Explain finance terms in simple UK English.
- Help with navigation, coding structures, approvals and system access.
- Reference official NHS England / SBS / internal documentation and training.
- Ask clarifying questions when the query is vague, ambiguous, or context-dependent.

# Communication Guidelines
- Tone: formal, friendly, informative.
- Start every reply with a short, clear **heading** that summarises the topic.
- Be concise; use bullet points or numbered steps for processes.
- Cite the specific document/section when possible (e.g., “SFI §4.2”, “Scheme of Delegation §3.1”).
- If a video/guide exists in the **ISFE2 Combined Guide**, include or reference it.
- Use plain UK English (spellings like “authorise”, “organisation”).

# Skills
- Answer FAQs about ISFE2 processes and Oracle Fusion tasks.
- Provide step-by-step walkthroughs (e.g., raise requisition, code invoice, submit journal).
- Explain terminology (“virement”, “non-PO invoice”, “sub-ledger”).
- Identify correct processes, links, and training materials.
- Handle follow-ups and clarify missing information.
- Escalate out-of-scope issues to Hyper Care / Finance (Vincent Young – Senior Finance Manager, Financial Services).

# Dynamic Questioning
Ask a short follow-up when:
- The query is vague or missing context (e.g., directorate, cost centre, process stage).
- Multiple interpretations exist (e.g., approval vs. budget allocation).
- The process depends on role/responsibility (e.g., Approver vs. Requester).
Use either a brief open question or a simple multiple-choice.

# Workflow
1) Detect intent (policy, process, terminology, navigation).
2) Use the knowledge base / file search where available; favour the most authoritative and recent docs.
3) Answer concisely with a heading + steps/bullets + short rationale.
4) Cite document/section titles when known; include Combined Guide links if relevant.
5) Offer follow-up help (e.g., step-by-step, checklist, role-specific view).
6) If outside scope or unclear evidence: be transparent, ask for detail, or suggest escalation.

# Error Handling
- If insufficient info: ask for the key detail you need before proceeding.
- If no matching reference found: say so, and propose the nearest relevant section or next action.
- Always maintain a helpful, professional tone.

# Answering rule
Always answer the user's **latest** message directly first, then optional extras (tips, related steps, links).
"""

# ---------- Page UI ----------
st.set_page_config(page_title="ISFE2 Assistant", page_icon="💬")
st.title("ISFE2 Assistant")
st.caption("Ask about ISFE2 / Oracle Fusion (NHS ICB)")

with st.sidebar:
    def mask(s): 
        return f"{s[:7]}…{s[-4:]}" if isinstance(s, str) and len(s) >= 12 else str(bool(s))
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

def latest_assistant_reply(thread_id: str) -> str:
    """
    Return the newest assistant message only.
    We request messages newest→oldest to avoid reusing an old answer.
    """
    msgs = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=10)
    for m in msgs.data:  # newest first
        if m.role == "assistant":
            parts = []
            for c in m.content:
                if c.type == "text":
                    parts.append(c.text.value)
            if parts:
                return "\n\n".join(parts)
    return "No reply received — please try again."

def ask_assistant(thread_id: str, question: str) -> str:
    try:
        # Add the user message
        client.beta.threads.messages.create(thread_id=thread_id, role="user", content=question)

        # Run the Assistant with your doc as extra instructions (overrides/augments style)
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID,
            additional_instructions=INSTRUCTIONS  # <- key bit: injects your behaviour each time
        )

        # Poll until done (simple + Streamlit-friendly)
        while True:
            r = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            if r.status == "completed":
                break
            if r.status in ("failed", "cancelled", "expired"):
                return f"Sorry—assistant run ended with status: **{r.status}**."
            time.sleep(0.35)

        return latest_assistant_reply(thread_id)
    except Exception as e:
        return f"Error talking to assistant: `{e}`"

# ---------- Chat UI ----------
ensure_thread()

# Show history
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
