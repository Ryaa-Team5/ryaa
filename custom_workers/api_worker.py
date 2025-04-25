import logging
import json
import requests
from langgraph.graph import StateGraph, START
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from arklex.env.workers.worker import BaseWorker, register_worker
from arklex.utils.graph_state import MessageState
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import PROVIDER_MAP

API_FORMATTER_URL= "http://localhost:8000/eval/chat"
API_FORMAT = '''{
    "history": [{"role": "user", "content": API_GENERATED_INFORMATION}],
    "parameters": {},
    "workers": [],
    "tools": [],
    }'''
API_CONTEXT = '''
    This API will connect to a local endpoint, and it is a LLM worker that specializes in a robotics company.

    Note "API_GENERATED_INFORMATION" is not the user's message, despite the role name. Instead, "message" would involve your
    generated response that you find appropriate according to the goals of the user. 
    '''
API_ENCODE = "JSON"
HEADER = '''{"Content-Type": "application/json"}'''

logger = logging.getLogger(__name__)

@register_worker
class RequestWorker(BaseWorker):
    description = "Processes information from the user (and other workers where appropriate) to generate a valid API payload which is sent to a relevant endpoint." \
    "The worker will return to the state information on the response from the API for use to contribute to address the user's goal." \
    "IMPORTANT: If the user ever asks a question related to making an API request, this worker should be used"

    def __init__(self, formatter_url=API_FORMATTER_URL):
        super().__init__()
        self.action_graph = self._create_action_graph()
        self.formatter = formatter_url
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

        alt_context = state.get("message_flow", "")
        if alt_context:
            alt_context = f"Here is context from other workers that are working to help the user: {alt_context}"
        #else:
        #    alt_context = "N/A"

        formatter_template = """
        This is the users input: {user_message}
        
        {alt_context}

        Consider the user's context, any other context, and create an API request that will appropriately contribute to solving the problem. 
        IMPORTANT: Never include the user's original message in the API payload. The user is talking to YOU, not the API. Instead, you should create a new message that appropriately contributes to solving the user's problem.

        API Context & Information: {API_CONTEXT}

        Encode the information in a JSON {API_ENCODE}

        The API itself accepts the following payload format: {API_FORMAT}

        Currently, only one API is accessible. The URL is: {API_FORMATTER_URL}
        The header format is: {HEADER_FORMAT}

        Your output MUST be the API encoded string. It must not include anything else, ever. 
        """
        formatter_template2 = """


        """

        formatter_prompt = PromptTemplate.from_template(formatter_template)

        input_prompt = formatter_prompt.invoke({
            "user_message": user_message,
            "alt_context": alt_context,
            "API_CONTEXT": API_CONTEXT,
            "API_ENCODE": API_ENCODE,
            "API_FORMAT": API_FORMAT,
            "API_FORMATTER_URL": API_FORMATTER_URL,
            "HEADER_FORMAT": HEADER
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
        request = self.req_str_to_dict(call_string)
        print(f"Request: {request}")
        logger.info(f"dict Request: {request}")

        match request["call_type"]:
            case "POST":
                api_response = requests.post(
                    request["endpoint"],
                    headers=request["headers"],
                    data=request["payload"],
                    timeout=30
                )
                state["metadata"]["api_response"] = api_response
                return state
            case "GET":
                api_response = requests.get(
                    url=request["endpoint"],
                    headers=request["headers"],
                    data=request["payload"],
                    timeout=30
                )
                state["metadata"]["api_response"] = api_response
                return state
            case _:
                state["metadata"]["api_response"] = "API request could not be made"
                return state
    
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

    








