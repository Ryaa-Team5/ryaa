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
from sl.utils import agent_response, gen_stream, gen_worker_list, display_workers

INPUT_DIR = "./agent/cs_test"
MODEL["model_type_or_path"] = "gpt-4o"
LLM_PROVIDER = "openai"
LOG_LEVEL = "WARNING"
WORKER_PREFIX = "assistant"
USER_PREFIX = "user"
LOGO_FULL = "./assets/ryaa_logo.svg"
LOGO_MINI = "./assets/ryaa_mini.svg"
LOGO_MICRO = "./assets/ryaa_micro.svg"
ICON_HUMAN = ":material/face:"
BLANK = "./assets/blank.svg"

model_provider_dict = {
    "gpt-4.1": "openai",
    "gpt-4.1-mini": "openai",
    "gpt-4o-nano": "openai"
}

def blank_slate():
    st.session_state.history = []
    st.session_state.params = {}
    st.session_state.workers = []
    st.session_state.empty = True

    # derived from Arklex, grab configured start response from config
    for node in config["nodes"]:
        if node[1].get("type", "") == "start":
            start_message = node[1]["attribute"]["value"]
            break

    st.session_state.history.append({"role": WORKER_PREFIX, "content": start_message})
    st.session_state.workers.append("")  # ensure worker list maintains equivalent index to history

# env, config derived from Arklex, "run.py" file
os.environ["DATA_DIR"] = INPUT_DIR
config = json.load(open(os.path.join(INPUT_DIR, "taskgraph.json")))
env = Env(
    tools = config.get("tools", []),
    workers = config.get("workers", []),
    slotsfillapi = config["slotfillapi"]
)

# Streamlit GUI
st.set_page_config(
    page_title="Ryaa",
    page_icon=LOGO_MICRO
)
st.logo(
    LOGO_MINI,
    size="large"
)

logo = st.empty()
# initialization or reset button
if "history" not in st.session_state:
    blank_slate()
    logo.image(
        LOGO_FULL,
        width=300
    )

with st.sidebar:
    st.toggle("Voice")
    MODEL["model_type_or_path"] = st.selectbox(
        "Model", (
            "gpt-4.1", 
            "gpt-4.1-mini", 
            "gpt-4.1-nano"
        ), 
        help="""
        *gpt-4.1* - Slowest, Most Intelligent  \n
        *gpt-4.1-mini* - Faster, Less Intelligent  \n
        *gpt-4.1-nano* - Fastest, Least Intelligent
        """
    )

    # generate reset button w/ loader to the right
    col1, col2 = st.columns([0.5,2], vertical_alignment='center')
    with col1:
        if st.button(":material/refresh:", type="primary", help="Reset Chat"):
            with col2:
                with st.spinner(" "):
                    blank_slate()
                    time.sleep(0.75)
  
#model_provider = model_provider_dict[model_option] #TODO: allow alternative API selection

# Chat History Rendering
st.write(st.session_state.workers)
for message, workers in zip(st.session_state.history, st.session_state.workers):
    history_icon = LOGO_MICRO if message["role"] == "assistant" else ICON_HUMAN
    with st.chat_message(message["role"], avatar=history_icon):
        if "memory" in st.session_state.params:
            st.write(st.session_state.params["memory"]["trajectory"])
        st.write(message["content"])
        display_workers(workers)

# Handle User Input & Response
if prompt := st.chat_input("Ask Ryaa"):
    st.session_state.empty = False
    st.session_state.history.append({"role": USER_PREFIX, "content": prompt})
    st.session_state.workers.append("")
    
    with st.chat_message("user", avatar=ICON_HUMAN):
        st.write(prompt)
        logo.empty()
        
    with st.spinner("Loading..."):
        output, st.session_state.params, hitl = agent_response(INPUT_DIR, st.session_state.history, 
                                                               prompt, st.session_state.params, env)
        st.session_state.history.append({"role": WORKER_PREFIX, "content": output})
        workers, sources = gen_worker_list(st.session_state.params) 
        #if "FaissRAGWorker" in workers:
            #source = 
        st.session_state.workers.append(workers)

    with st.chat_message("assistant", avatar=LOGO_MICRO):
        st.write(st.session_state.params["memory"]["trajectory"]) # DEBUG
        st.write_stream(gen_stream(output, delay=0.0001))
        display_workers(workers)

    #st.rerun()