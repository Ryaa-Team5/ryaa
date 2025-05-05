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

logger = logging.getLogger(__name__)
api_keys = {
    "ALPHA_VANTAGE_KEY": "empty"
}
formatting_context = """
To format a response, use the following encode, and include nothing more in the response. Your output will be parsed appropriately. 

{
	“url”: [insert here full API call URL. replace any authkey requirements with the AuthKeyName],
	“AuthKeyName”: [insert here name of AuthKey e.g. ALPHA_VANTAGE_KEY]
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
        user_message = state["user_message"]

        rag_context = state.get("message_flow", "")
        if rag_context:
            rag_context = f"Here is context from other workers that are working to help the user: {rag_context}"
        #else:
        #    alt_context = "N/A"

        formatter_template = """

        {user_message}
        {rag_context}
        {formatting_context}
        """
        


        formatter_prompt = PromptTemplate.from_template(formatter_template)

        input_prompt = formatter_prompt.invoke({
            "user_message": user_message,
            "alt_context": rag_context,
            "API_CONTEXT": formatting_context
        })
        
        final_chain = self.llm | StrOutputParser()
        prompt_string = input_prompt.text
        print(f"Format Prompt: {prompt_string}")
        formatted_api_string = final_chain.invoke(prompt_string).strip()
        
        print(f"{formatted_api_string}")
        state["metadata"]["call_string"] = formatted_api_string

        return state

    def gen_request(self, state: MessageState) -> MessageState: #
        call_string = state["metadata"]["call_string"]
        request = json.loads(call_string)
        url_call = request["url"]
        auth_key = api_keys[request["AuthKeyName"]]
        full_call = url_call.replace(request["AuthKeyName"], auth_key)
        print(full_call)
        api_response = requests.get(full_call)
        state["metadata"]["api_response"] = api_response
        print(api_response)
        return state
        #request = self.req_str_to_dict(call_string)
        #print(f"Request: {request}")
        #logger.info(f"dict Request: {request}")


        #match request["call_type"]:
        #    case "POST":
        #        api_response = requests.post(
        #            request["endpoint"],
        #            headers=request["headers"],
        #            data=request["payload"],
        #            timeout=30
        #        )
        #        state["metadata"]["api_response"] = api_response
        #        return state
        #    case "GET":
        #        api_response = requests.get(
        #            url=request["endpoint"],
        #            headers=request["headers"],
        #            data=request["payload"],
        #            timeout=30
        #        )
        #        state["metadata"]["api_response"] = api_response
        #        return state
        #    case _:
        #        state["metadata"]["api_response"] = "API request could not be made"
        #        return state
    
    def handle_response(self, state: MessageState) -> MessageState:
        
        response = state["metadata"]["api_response"]
        logger.info(f"API Response: {response.text}")
        try:
            response.raise_for_status()
            state["response"] = response.text
        except requests.exceptions.HTTPError as e:
             state["response"] = f"API Request Failed: {e}"

        return state
    
    def _create_action_graph(self):
        workflow = StateGraph(MessageState)
        workflow.add_node("format_user_message", self.format_user_message)
        workflow.add_node("gen_request", self.gen_request)
        workflow.add_node("handle_response", self.handle_response)

        workflow.add_edge(START, "format_user_message")
        workflow.add_edge("format_user_message", "gen_request")
        workflow.add_edge("gen_request", "handle_response")
        return workflow

    def execute(self, msg_state: MessageState):
        graph = self.action_graph.compile()
        result = graph.invoke(msg_state)
        return result

    








