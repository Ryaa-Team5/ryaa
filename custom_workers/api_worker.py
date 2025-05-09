import logging
import json
import requests
import os
from langgraph.graph import StateGraph, START
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from arklex.env.workers.worker import BaseWorker, register_worker
from arklex.utils.graph_state import MessageState
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import PROVIDER_MAP
from arklex.env.tools.RAG.retrievers.faiss_retriever import RetrieveEngine
import streamlit as st
logger = logging.getLogger(__name__)
formatting_context = """
To format a response, use the following encode, and include nothing more in the response. Your output will be parsed appropriately. 

{
	“url”: [insert here full API call URL. replace any authkey requirements with the AuthKeyName],
	“AuthKeyName”: [insert here name of AuthKey e.g. ALPHA_VANTAGE_API_KEY]
}
"""

@register_worker
class RequestWorker(BaseWorker):
    description = "Processes information from the user (and other workers where appropriate) to generate a valid API payload which is sent to a relevant endpoint." \
    "The worker will return to the state information on the response from the API for use to contribute to address the user's goal." \
    "IMPORTANT: If the user ever asks a question related to making an API request, this worker should be used"

    def __init__(self):
        super().__init__()
        self.action_graph = self._create_action_graph()
        self.llm = PROVIDER_MAP.get(MODEL['llm_provider'], ChatOpenAI)(
            model = MODEL["model_type_or_path"], timeout=30000
        )

    def gen_request(self, encoded_request):
        request = json.loads(encoded_request)
        api_call = request["url"].replace(request["AuthKeyName"], os.environ.get(request["AuthKeyName"]))
        #st.write(api_call)
        return requests.get(api_call)

    def handle_response(self, state, api_response):
        print(api_response)
        try:
            api_response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            state.response = f"API Request Failed: {e}"
            return False
        
    def req_str_to_dict(self, req_str: str, delimiter="<") -> dict:
        elements_list = req_str.split(delimiter)
        req_elements = {
            "call_type": elements_list[0],
            "endpoint": elements_list[1],
            "headers": json.loads(elements_list[2]),
            "payload": elements_list[3]
        }
        return req_elements

    def format_user_message(self, state: MessageState) -> MessageState:
        #st.write("user formatting")
        #st.write(st.session_state.history)
        api_keys_list = str(st.session_state.custom_keys)
        user_message = state.user_message
        #rag_context = state.get("message_flow", "")
        rag_context = state.message_flow if state.message_flow else ""
        #st.write("LOG: Executed API Worker")
        #state.response = "Entered API Worker. This is a test configuration."
        #return state.response
        formatter_template = """
        {user_message}
        List of available api keys: {api_keys_list}
        {rag_context}
        {formatting_context}
        """

        formatter_prompt = PromptTemplate.from_template(formatter_template)

        input_prompt = formatter_prompt.invoke({
            "user_message": user_message,
            "api_keys_list": api_keys_list,
            "rag_context": rag_context,
            "formatting_context": formatting_context
        })
        
        final_chain = self.llm | StrOutputParser()
        prompt_string = input_prompt.text
        print(f"Format Prompt: {prompt_string}")
        formatted_api_string = final_chain.invoke(prompt_string).strip()
        summary_template = """
        You are a chatbot/agent intended to assist the user. At this point, you should have most if not 
        all the context you need. Below is the user message, rag documentation used, and the api response. 

        Address the user's inquiry based on the given information. Place a focus on the api response. 

        User Message: {user_message}
        RAG & API Docs: {rag_context}
        API_Response: {api_response}

        """
        print(f"{formatted_api_string}")

        response = self.gen_request(formatted_api_string)
        print(response.text)
        #st.write(response.text)
        status = self.handle_response(state, response)
        #st.write(status)
        if status: 
            summary_prompt = PromptTemplate.from_template(summary_template)
            input_summary = summary_prompt.invoke({
                "user_message": user_message,
                "rag_context": rag_context,
                "api_response": response.text
            })
            summary = final_chain.invoke(input_summary.text).strip()
            print(summary)
            state.response = summary
        else:
            print("API failed")
            state.response = "API FAILURE"

        return state
    
    def _create_action_graph(self):
        workflow = StateGraph(MessageState)
        workflow.add_node("retriever", RetrieveEngine.faiss_retrieve)
        workflow.add_node("format_user_message", self.format_user_message)
        #workflow.add_node("gen_request", self.gen_request)
        #workflow.add_node("handle_response", self.handle_response)

        workflow.add_edge(START, "retriever")
        workflow.add_edge("retriever", "format_user_message")
        #workflow.add_edge("format_user_message", "gen_request")
        #workflow.add_edge("gen_request", "handle_response")
        return workflow

    def _execute(self, msg_state: MessageState):
        graph = self.action_graph.compile()
        result = graph.invoke(msg_state)
        return result

    








