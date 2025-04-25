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

model_provider_dict = {
    "GPT-4.1": ["gpt-4.1", "openai"],
    "GPT-4o": ["gpt-4o", "openai"],
    "GPT-4o-mini": ["gpt-4o-mini","openai"]
}

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

def gen_stream(text, delay=0.02):
    test_list = text.split()
    for word in test_list:
        yield word + " "
        time.sleep(delay)

# Streamlit GUI
st.image("./assets/ryaa_logo.svg",width=300)

with st.sidebar:
    st.toggle("Voice")
    model_option = st.selectbox("Model", ("GPT-4.1", "GPT-4o", "GPT-4o-mini"))

model_provider = model_provider_dict[model_option]


if "history" not in st.session_state:
    st.session_state.history = []
    st.session_state.params = {}

    # grab configured start response from config
    for node in config['nodes']:
        if node[1].get("type", "") == 'start':
            start_message = node[1]['attribute']["value"]
            break

    st.session_state.history.append({"role": WORKER_PREFIX, "content": start_message})
    
# Chat History Rendering
for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Handle User Input & Response
if prompt := st.chat_input("Enter Message:"):

    st.session_state.history.append({"role": USER_PREFIX, "content": prompt})

    with st.chat_message("user"):
        st.write(prompt)

    output, st.session_state.params, hitl = agent_response(INPUT_DIR, st.session_state.history, 
                                                           prompt, st.session_state.params, env)
    st.session_state.history.append({"role": WORKER_PREFIX, "content": output})

    with st.chat_message("assistant"):
        response = st.write_stream(gen_stream(output))
        #response = st.write(output)