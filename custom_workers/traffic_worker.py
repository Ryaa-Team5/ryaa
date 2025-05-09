import logging
from datetime import datetime
from typing import Optional, Tuple
import math
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

from langgraph.graph import StateGraph, START
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from arklex.env.workers.worker import BaseWorker, register_worker
from arklex.utils.graph_state import MessageState
from arklex.utils.model_config import MODEL

logger = logging.getLogger(__name__)

# You might want to customize this prompt based on your specific needs
TRAFFIC_PREDICTION_PROMPT = """
Given the following context and user query about traffic, provide a helpful response:

System Instructions: {sys_instruct}
User Chat History: {formatted_chat}
Current Query: {message}

Consider:
1. Time of day and day of week
2. Known traffic patterns
3. Any mentioned events or conditions
4. Alternative routes if applicable
5. Distance between locations if mentioned

Provide a clear, concise response about the traffic situation and recommendations.
"""

@register_worker
class TrafficWorker(BaseWorker):
    description = "Worker that provides traffic predictions and recommendations based on user queries."

    def __init__(self):
        super().__init__()
        self.llm = ChatOpenAI(model=MODEL["model_type_or_path"], timeout=30000)
        self.action_graph = self._create_action_graph()
        self.geocoder = Nominatim(user_agent="traffic_worker")

    def get_location_coordinates(self, location: str) -> Tuple[float, float]:
        """Get coordinates for a location using geocoding."""
        try:
            location_data = self.geocoder.geocode(location)
            if location_data:
                return (location_data.latitude, location_data.longitude)
            raise ValueError(f"Could not find coordinates for location: {location}")
        except Exception as e:
            logger.error(f"Error geocoding location {location}: {str(e)}")
            raise

    def calculate_distance(self, location1: str, location2: str) -> float:
        """Calculate the distance between two locations in kilometers."""
        try:
            coords1 = self.get_location_coordinates(location1)
            coords2 = self.get_location_coordinates(location2)
            distance = geodesic(coords1, coords2).kilometers
            return round(distance, 2)
        except Exception as e:
            logger.error(f"Error calculating distance between {location1} and {location2}: {str(e)}")
            raise

    def predict_traffic(self, state: MessageState) -> MessageState:
        user_message = state['user_message']
        orchestrator_message = state['orchestrator_message']

        # Takes the locations the user is asking about
        locations = self._extract_locations(orchestrator_message.message)
        distance_info = ""
        if locations and len(locations) == 2:
            try:
                distance = self.calculate_distance(locations[0], locations[1])
                distance_info = f"\nDistance between {locations[0]} and {locations[1]}: {distance} km"
            except Exception as e:
                logger.error(f"Error calculating distance: {str(e)}")

        prompt = PromptTemplate.from_template(TRAFFIC_PREDICTION_PROMPT)
        input_prompt = prompt.invoke({
            "sys_instruct": state["sys_instruct"],
            "message": orchestrator_message.message + distance_info,
            "formatted_chat": user_message.history
        })

        logger.info(f"Traffic Prediction Prompt: {input_prompt.text}")
        final_chain = self.llm | StrOutputParser()
        prediction = final_chain.invoke(input_prompt.text)

        state["response"] = prediction
        return state

    def _extract_locations(self, message: str) -> list:
        """Extract location names from the message using the LLM."""
        location_prompt = f"""
        Extract location names from the following message. Return only the locations as a comma-separated list.
        If there are no locations, return an empty string.
        
        Message: {message}
        """
        try:
            response = self.llm.invoke(location_prompt)
            if response and response.strip():
                return [loc.strip() for loc in response.split(",")]
            return []
        except Exception as e:
            logger.error(f"Error extracting locations: {str(e)}")
            return []

    def _create_action_graph(self):
        workflow = StateGraph(MessageState)
        workflow.add_node("predict_traffic", self.predict_traffic)
        workflow.add_edge(START, "predict_traffic")
        return workflow

    def execute(self, msg_state: MessageState):
        graph = self.action_graph.compile()
        result = graph.invoke(msg_state)
        return result 