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
    "FaissRAGWorker" : "green",
    "SearchWorker": "red"
}

worker_names = {
    "MessageWorker": "Message",
    "FaissRAGWorker": "RAG",
    "SearchWorker": "Internet Search"
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
def gen_worker_list(params):
    workers = []
    urls = []
    trajectory = params["memory"]["trajectory"]
    instance = trajectory[-1] # most recent message details

    for details in instance: 
        #st.write(details)       # DEBUG 
        worker = details["info"]["name"]
        workers.append(details["info"]["name"])
        if worker == "FaissRAGWorker":
            faiss_details = details["steps"][0]
            for doc in faiss_details["faiss_retrieve"]:
                url = doc["source"]
                urls.append(url)
    print(urls)
    return workers, urls

# TODO: Allow horizontal worker display used to generate response
def display_workers(workers):
    markdown_str = f""
    worker_set = set(workers)
    for worker in worker_set:
        if worker == "planner":
            continue
        color = worker_colors.get(worker, "yellow")
        name = worker_names.get(worker, worker)
        markdown_str += f":{color}-badge[{name}] "
    st.markdown(markdown_str)

def get_model_provider(model: str):  
    if "gpt" in model:
        return "openai"
    if "gemini" in model:
        return "gemini"
    if "claude" in model:
        return "anthropic"