import os
import json
import time
import logging
import streamlit as st
from dotenv import load_dotenv
from pprint import pprint
import pandas as pd
import io
from sl.utils import agent_response, gen_stream, gen_worker_list, display_workers, get_model_provider, load_secrets
load_secrets()

from arklex.utils.utils import init_logger
from arklex.orchestrator.orchestrator import AgentOrg
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import LLM_PROVIDERS
from arklex.env.env import Env


INPUT_DIR = "./agent/api_assistant2"
MODEL["model_type_or_path"] = "gpt-4.1"
LOG_LEVEL = "WARNING"
WORKER_PREFIX = "assistant"
USER_PREFIX = "user"
LOGO_FULL = "./assets/ryaa_logo.svg"
LOGO_MINI = "./assets/ryaa_mini.svg"
LOGO_MICRO = "./assets/ryaa_micro.svg"
ICON_HUMAN = ":material/face:"
BLANK = "./assets/blank.svg"
models = (
            "gpt-4.1", 
            "gpt-4.1-mini", 
            "gpt-4.1-nano",
            "gemini-2.0-flash",
            "gemini-2.5-flash-preview-04-17",
            "gemini-2.5-pro-preview-03-25",
            "claude-3-7-sonnet-20250219"
        )


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
    voice = st.toggle("Voice")
    debug = st.toggle("Debug Mode", value=False)

    model_option = st.selectbox(
        "Model", models, 
        help="""
        *gpt-4.1* - Slowest, Most Intelligent  \n
        *gpt-4.1-mini* - Faster, Less Intelligent  \n
        *gpt-4.1-nano* - Fastest, Least Intelligent
        """
    )
    MODEL["model_type_or_path"] = model_option
    MODEL["llm_provider"] = get_model_provider(model_option)
    # generate reset button w/ loader to the right
    col1, col2 = st.columns([0.5,2], vertical_alignment='center')
    with col1:
        if st.button(":material/refresh:", type="primary", help="Reset Chat"):
            with col2:
                with st.spinner(" "):
                    blank_slate()
                    time.sleep(0.75)

# Chat History Rendering
if debug: 
    st.write(st.session_state.workers)
for message, workers in zip(st.session_state.history, st.session_state.workers):
    history_icon = LOGO_MICRO if message["role"] == "assistant" else ICON_HUMAN
    with st.chat_message(message["role"], avatar=history_icon):
        if debug and "memory" in st.session_state.params:
            st.write(st.session_state.params["memory"]["trajectory"])
        st.write(message["content"])
        display_workers(workers)

# Handle User Input & Response
if prompt := st.chat_input("Ask Ryaa"):
    st.session_state.empty = False
    
    with st.chat_message("user", avatar=ICON_HUMAN):
        st.write(prompt)
        logo.empty()
    st.session_state.history.append({"role": USER_PREFIX, "content": prompt})
    st.session_state.workers.append("")    
    with st.spinner("Loading..."):
        output, st.session_state.params, hitl = agent_response(INPUT_DIR, st.session_state.history, 
                                                               prompt, st.session_state.params, env)
        
        workers, sources = gen_worker_list(st.session_state.params) 

        

    with st.chat_message("assistant", avatar=LOGO_MICRO):
        if debug: 
            st.write(st.session_state.params["memory"]["trajectory"]) # 
        st.write(output)
        #st.write_stream(gen_stream(output, delay=0.0001))
        detail_col1, detail_col2 = st.columns([0.5,2], vertical_alignment='center')
        with detail_col1:
            display_workers(workers)
            if "FaissRAGWorker" in workers:
                with detail_col2:
                    with st.expander("Sources Used"):
                        for source in sources:
                            st.write(source)

    st.session_state.history.append({"role": WORKER_PREFIX, "content": output})
    st.session_state.workers.append(workers)


    #st.rerun()