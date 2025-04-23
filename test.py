import os
import json
import argparse
import time
import logging
import streamlit as st
from dotenv import load_dotenv
from pprint import pprint

from arklex.utils.utils import init_logger
from arklex.orchestrator.orchestrator import AgentOrg
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import LLM_PROVIDERS
from arklex.env.env import Env

INPUT_DIR = "./agent/customer_service"
MODEL = "gpt-4o"
LLM_PROVIDER = "openai"
LOG_LEVEL = "WARNING"
WORKER_PREFIX = "assistant"
USER_PREFIX = "user"
first = True

config = json.load(open(os.path.join(INPUT_DIR, "taskgraph.json")))
env = Env(
    tools = config.get("tools", []),
    workers = config.get("workers", []),
    slotsfillapi = config["slotfillapi"]
)

def agent_response(input_dir, history, user_text, parameters, env):
    data = {"text": user_text, 'chat_history': history, 'parameters': parameters}
    orchestrator = AgentOrg(config=os.path.join(input_dir, "taskgraph.json"), env=env)
    result = orchestrator.get_response(data)

    return result['answer'], result['parameters'], result['human_in_the_loop']

def gen_stream(text, delay=0.01):
    for char in text:
        yield char
        time.sleep(delay)
# Streamlit GUI

st.title("RYAA")
st.caption(
    ""
)

    
st.sidebar.toggle("Voice")
ModelOption = st.sidebar.selectbox("Model", ("GPT-4o", "GPT-4o-mini"))
#st.write("Model:", ModelOption)
LLMOption = st.sidebar.selectbox("LLM Provider", ("OPEN-AI", "..", ".."))
#st.write("LLM:", LLMOption)


if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.params = {}
    for node in config['nodes']:
        if node[1].get("type", "") == 'start':
            start_message = node[1]['attribute']["value"]
            break
    st.session_state.history.append({"role": WORKER_PREFIX, "content": start_message})
    

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):

    st.session_state.history.append({"role": USER_PREFIX, "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    output, st.session_state.params, hitl = agent_response(INPUT_DIR, st.session_state.history, prompt, st.session_state.params, env)
    st.session_state.history.append({"role": USER_PREFIX, "content": prompt})
    st.session_state.history.append({"role": WORKER_PREFIX, "content": output})

    with st.chat_message("assistant"):
        response = st.write_stream(gen_stream(output))