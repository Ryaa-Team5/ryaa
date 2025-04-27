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

worker_colors = {
    "MessageWorker": "blue",
    "FaissRAGWorker" : "green"
}

worker_names = {
    "MessageWorker": "Message",
    "FaissRAGWorker": "RAG"
}

# derived from Arklex, "run.py" file
def agent_response(input_dir, history, user_text, parameters, env):
    data = {"text": user_text, 'chat_history': history, 'parameters': parameters}
    orchestrator = AgentOrg(config=os.path.join(input_dir, "taskgraph.json"), env=env)
    result = orchestrator.get_response(data)

    return result['answer'], result['parameters'], result['human_in_the_loop']

def gen_stream(text, delay=0.025):
    test_list = text.split()
    for word in test_list:
        yield word + " "
        time.sleep(delay)

# searches trajectory used by system to determine workers used
def find_workers(params):
    trajectory = params["memory"]["trajectory"]
    workers = []
    for instance in trajectory:
        for details in instance: 
            #st.write(details)       # DEBUG 
            workers.append(details["info"]["name"])
    return workers

# TODO: Allow horizontal worker display used to generate response
#def display_workers(workers):
    #pass
