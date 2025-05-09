import os
import json
import time
import streamlit as st
from dotenv import load_dotenv

from sl.utils import agent_response, gen_stream, gen_worker_list, display_workers, get_model_provider, load_secrets, gen_agent
load_secrets()
from sl.audio_utils import transcribe_audio, tts_conversion

from arklex.utils.utils import init_logger
from arklex.orchestrator.orchestrator import AgentOrg
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import LLM_PROVIDERS
from arklex.env.env import Env


if "custom_keys" not in st.session_state:
    st.session_state.custom_keys = []
if "gen_counter" not in st.session_state:
    st.session_state.gen_counter = 0
if "agent_btn_disabled" not in st.session_state:
    st.session_state.agent_btn_disabled = True

if "tmp_api_info" not in st.session_state:
    st.session_state.tmp_api_info = {
        "api_name": None,
        "api_key": None,
        "docs_link": None,
        "api_desc": None
    }

if "INPUT_DIR" not in st.session_state:
    #ryaa_test
    st.session_state.INPUT_DIR = "./agent/api_agent0"
    os.environ["DATA_DIR"] = st.session_state.INPUT_DIR
    st.session_state.config = json.load(open(os.path.join(st.session_state.INPUT_DIR, "taskgraph.json")))
    st.session_state.env = Env(
        tools = st.session_state.config.get("tools", []),
        workers = st.session_state.config.get("workers", []),
        slotsfillapi = st.session_state.config["slotfillapi"]
    )

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

@st.dialog("Add in API functionality")
def new_agent_config():
    api_info = st.session_state.tmp_api_info
    
    api_name = st.text_input("API Key Name")
    api_key = st.text_input("API Key")
    docs_link = st.text_input("API Documentation Source", placeholder="Enter Link to Docs...")
    api_desc = st.text_input("API Docs Description", placeholder="API Docs for...")

    if st.button("Submit"):
        api_info["api_name"] = api_name
        api_info["api_key"] = api_key
        api_info["docs_link"] = docs_link
        api_info["api_desc"] = api_desc
        st.session_state.tmp_api_info = api_info
        st.rerun()

def load_json(path):
    with open(path, 'r') as file:
        data = json.load(file)
    return data

def reset_config(debug=True):
        data_dir = st.session_state.INPUT_DIR
        os.environ["DATA_DIR"] = data_dir
        if debug: st.write(os.environ["DATA_DIR"])
        st.session_state.config = json.load(open(os.path.join(data_dir, "taskgraph.json")))
        st.session_state.env = Env(
            tools = st.session_state.config.get("tools", []),
            workers = st.session_state.config.get("workers", []),
            slotsfillapi = st.session_state.config["slotfillapi"]
        )
        if debug: 
            st.write(st.session_state.config)
            st.write(load_json(os.path.join(data_dir, "taskplanning.json")))
        

def blank_slate():
    st.session_state.history = []
    st.session_state.params = {}
    st.session_state.workers = []
    st.session_state.empty = True

    # derived from Arklex, grab configured start response from config
    #for node in config["nodes"]:
    #    if node[1].get("type", "") == "start":
    #        start_message = node[1]["attribute"]["value"]
    #        break

    #st.session_state.history.append({"role": WORKER_PREFIX, "content": start_message})
    #st.session_state.workers.append("")  # ensure worker list maintains equivalent index to history


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
    voice_output = st.toggle("Voice Output")
    debug = st.toggle("Debug Mode", value=False)
    config_option = f"./agent/api_agent{st.session_state.gen_counter}"
    #config_option = st.selectbox(
    #    "Agent",
    #    ("./agent/blb_agent",
    #     "./agent/ryaa_test",
    #     "./agent/api_agent0")
    ##     "./agent/api_agent0",
    ##     "./agent/cs_test",
    ##     "./agent/cs_test2")
    ##)  if debug:
    #)
    st.session_state.INPUT_DIR=config_option
    reset_config(debug)

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
    #config_path = f"./configs/ryaa_config.json{st.session_state.gen_counter}"
    config_path = st.text_input("Config Location", "./configs/ryaa_config.json")
    col3, col4 = st.columns([0.5, 0.5], vertical_alignment="center")
    with col3:
        if st.button("Create Agent"):
            new_agent_config()
            st.session_state.agent_btn_disabled = False
            #st.rerun()
    with col4:
        if st.button("Load Agent", disabled=st.session_state.agent_btn_disabled):
            if debug: st.write(st.session_state.tmp_api_info)
            with st.status("Creating New Agent..."):
                st.session_state.gen_counter += 1
                st.session_state.custom_keys.append(st.session_state.tmp_api_info["api_name"])
                os.environ[st.session_state.tmp_api_info["api_name"]] = st.session_state.tmp_api_info["api_key"]
                st.write("Opening config...")
                with open(config_path, "r") as file:
                    agent_config = json.load(file)
                rag_doc = {
                    "source": st.session_state.tmp_api_info["docs_link"],
                    "desc": st.session_state.tmp_api_info["api_desc"],
                    "num": 1
                }
    
                agent_config["rag_docs"].append(rag_doc)
                st.write("Writing to config...")
                with open(config_path, "w") as file:
                    json.dump(agent_config, file, indent=2)
                #st.success(f"New Doc Added {rag_link}")
                st.write("Generating new agent...")
                gen_agent(config_path,model_option, get_model_provider(model_option))
                st.write("Clearing chat...")
                st.session_state.tmp_api_info = {key: None for key in st.session_state.tmp_api_info}
                st.session_state.INPUT_DIR = f"./agent/api_agent{st.session_state.gen_counter}"
                reset_config(debug)
                blank_slate()
                #st.rerun()
                st.session_state.agent_btn_disabled = True
                



# Chat History Rendering
if debug: 
    st.write(st.session_state.workers)
    st.write(os.listdir("./agent"))
    
    #st.write(st.session_state.INPUT_DIR)
    
for message, workers in zip(st.session_state.history, st.session_state.workers):
    history_icon = LOGO_MICRO if message["role"] == "assistant" else ICON_HUMAN
    with st.chat_message(message["role"], avatar=history_icon):
        if debug and "memory" in st.session_state.params:
            st.write(st.session_state.params["memory"]["trajectory"])
        st.write(message["content"])
        display_workers(workers)
prompt = None
if voice:
    # Capture audio input
    audio_data = st.audio_input("Record your question for Ryaa")
    if audio_data is not None:
        # Placeholder for processing audio data to text
        prompt = transcribe_audio(audio_data)
        # prompt = (
        #     "Transcribed text from audio"  # Replace with actual transcription logic
        # )
else:
    # Capture text input
    prompt = st.chat_input("Ask Ryaa")

# Handle User Input & Response
if prompt:
    st.session_state.empty = False
    
    with st.chat_message("user", avatar=ICON_HUMAN):
        st.write(prompt)
        logo.empty()
    st.session_state.history.append({"role": USER_PREFIX, "content": prompt})
    st.session_state.workers.append("")    
    with st.spinner("Loading..."):
        output, st.session_state.params, hitl = agent_response(st.session_state.INPUT_DIR, st.session_state.history, 
                                                               prompt, st.session_state.params, st.session_state.env)
        
        workers, sources = gen_worker_list(st.session_state.params) 

    with st.chat_message("assistant", avatar=LOGO_MICRO):
        if debug: 
            st.write(st.session_state.params["memory"]["trajectory"]) # 
        st.write(output)
        #st.write_stream(gen_stream(output, delay=0.0001))
        if voice_output:
            audio_output = tts_conversion(output)
            st.audio(audio_output, autoplay=True)
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