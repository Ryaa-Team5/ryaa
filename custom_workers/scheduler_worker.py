import logging
import sys
import os
import re
import dateparser
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.triggers.date import DateTrigger

from langgraph.graph import StateGraph, START

from arklex.env.workers.worker import BaseWorker, register_worker
from arklex.utils.graph_state import MessageState
from arklex.env.workers.message_worker import MessageWorker

# Ensure parent directory is in path so utility modules can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from calendar_utils import get_calendar_service  # Google Calendar utility

logger = logging.getLogger(__name__)


@register_worker
class SchedulerWorker(BaseWorker):
    """
    A worker that schedules user tasks using APScheduler and optionally creates Google Calendar events.
    """

    description = "Schedules tasks for the user, such as sending messages or performing actions."

    def __init__(self):
        super().__init__()
        # Set up the background scheduler
        self.scheduler = BackgroundScheduler()
        self.message_worker = MessageWorker()  # Worker used to handle the scheduled message
        self._configure_scheduler()
        self.action_graph = self.create_action_graph()  # Create LangGraph task flow

    def _configure_scheduler(self):
        # Attach a listener to log job success or failure
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self.scheduler.start()

    def _job_listener(self, event):
        # Log job result
        if event.exception:
            logger.error(f"Job {event.job_id} failed!")
        else:
            logger.info(f"Job {event.job_id} executed successfully.")

    def schedule_user_task(self, user_id, task_time, task_data):
        """
        Schedule a task for execution and optionally create a calendar event.
        """
        trigger = DateTrigger(run_date=task_time)
        job_id = f"user_task_{user_id}_{task_time}"

        # Schedule task execution
        self.scheduler.add_job(self.execute_user_task, trigger, args=[user_id, task_data], id=job_id)
        logger.info(f"Task scheduled for user {user_id} at {task_time}. Task details: {task_data}")

        # Attempt to create a calendar event
        try:
            self._create_calendar_event(task_time, task_data['message'], user_id)
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")

    def _create_calendar_event(self, task_time, message, user_id):
        """
        Adds a scheduled task to Google Calendar with a 15-minute duration.
        """
        service = get_calendar_service()
        print(f"Attempting to create calendar event at {task_time} with message: {message}")

        event = {
            'summary': message,
            'description': f'Scheduled Through RYAA for {user_id}',
            'start': {
                'dateTime': task_time.isoformat(),
                'timeZone': 'America/New_York',  # Set calendar time zone to Eastern
            },
            'end': {
                'dateTime': (task_time + timedelta(minutes=15)).isoformat(),
                'timeZone': 'America/New_York',
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Created Google Calendar event: {created_event.get('htmlLink')}")

    def execute_user_task(self, user_id, task_data):
        """
        Called by APScheduler when it's time to perform the scheduled task.
        """
        logger.info(f"Executing scheduled task for user {user_id}: {task_data}")
        user_message = task_data['message']
        orchestrator_message = task_data.get('orchestrator_message', "Default orchestrator message")

        msg_state = MessageState(
            user_message={"history": user_message},
            orchestrator_message=orchestrator_message,
            sys_instruct="Sample instruction"
        )

        result = self.message_worker.execute(msg_state)
        logger.info(f"Task executed for user {user_id}: {result}")

    def format_user_message(self, state: MessageState) -> MessageState:
        """
        Placeholder: currently passes state through unchanged.
        """
        user_message = state["user_message"]
        alt_context = state.get("message_flow", "")
        return state

    def gen_request(self, state: MessageState) -> MessageState:
        """
        Parses user input to extract time and message, then schedules the task.
        """
        user_input = state["user_message"]["history"]
        user_id = state.get("user_id", "default_user")

        parsed_time, message = self.extract_task_details(user_input)

        if parsed_time:
            self.schedule_user_task(
                user_id=user_id,
                task_time=parsed_time,
                task_data={
                    "message": message,
                    "orchestrator_message": state.orchestrator_message or "Scheduled from input"
                }
            )
            logger.info(f" Task parsed and scheduled at {parsed_time}")
        else:
            logger.warning("⚠️ Could not parse time from user input.")

        return state

    def handle_response(self, state: MessageState) -> MessageState:
        """
        Placeholder for processing any response post scheduling.
        """
        return state

    def extract_task_details(self, user_input: str):
        """
        Extracts a datetime and cleaned event title from natural language input.
        Returns (datetime, cleaned_message) or (None, original_input) if parsing fails.
        """
        time_pattern = re.compile(
            r"((on\s+)?[A-Z]?[a-z]+\s+\d{1,2}(st|nd|rd|th)?(,?\s+\d{4})?)?\s*(at\s+)?"
            r"(\d{1,2}(:\d{2})?\s*(am|pm)?|noon|midnight|twelve)",
            re.IGNORECASE
        )
        match = time_pattern.search(user_input)

        # Step 1: Remove time phrase
        if match:
            time_phrase = match.group(0)
            parsed_time = dateparser.parse(time_phrase, settings={"PREFER_DATES_FROM": "future"})
            cleaned = user_input.replace(time_phrase, "").strip(",. ")
        else:
            parsed_time = dateparser.parse(user_input, settings={"PREFER_DATES_FROM": "future"})
            cleaned = user_input.strip()

        # Step 2: Remove common natural language command prefixes
        prefix_pattern = re.compile(
            r"^(add|schedule|set( up)?|book( me)?|remind( me)?( to| about)?|put( me)?( down)?( for)?|create)\s+(a|an|my)?\s*",
            re.IGNORECASE
        )
        cleaned = prefix_pattern.sub("", cleaned)

        # Step 3: Capitalize the result
        cleaned_message = cleaned.strip().capitalize()

        return parsed_time, cleaned_message

    def create_action_graph(self):
        """
        Defines the LangGraph workflow for task processing.
        """
        workflow = StateGraph(MessageState)
        # Add nodes for time extraction, task scheduling, and optional confirmation
        workflow.add_node("extract_time_and_message", self.extract_time_and_message_node)
        workflow.add_node("schedule_task", self.schedule_task_node)
        workflow.add_node("confirmation", self.confirmation_node)
        
        workflow.add_edge(START, "extract_time_and_message")
        workflow.add_edge("extract_time_and_message", "schedule_task")
        workflow.add_edge("schedule_task", "confirmation")  # Optional: add confirmation step if needed
        
        return workflow

    def extract_time_and_message_node(self, state: MessageState):
        """
        Extracts time and message from user input.
        """
        user_input = state["user_message"]["history"]
        parsed_time, message = self.extract_task_details(user_input)
        
        if parsed_time:
            return parsed_time, message
        else:
            return "⚠️ Could not extract time from input", ""

    def schedule_task_node(self, state: MessageState):
        """
        Schedules the task based on extracted time and message.
        """
        parsed_time, message = self.extract_time_and_message_node(state)
        if isinstance(parsed_time, str):  # If error, return error message
            return parsed_time
        
        user_id = state.get("user_id", "default_user")
        self.schedule_user_task(user_id, parsed_time, {"message": message})
        return f"📅 Your task has been scheduled for {parsed_time}"

    def confirmation_node(self, state: MessageState):
        """
        Optional confirmation message after task scheduling.
        """
        parsed_time, message = self.extract_time_and_message_node(state)
        if isinstance(parsed_time, str):  # If error, return error message
            return parsed_time
        
        return f"Task '{message}' successfully scheduled for {parsed_time}."

    def execute(self, msg_state: MessageState):
        """
        Entry point for invoking the action graph.
        """
        graph = self.action_graph.compile()
        result = graph.invoke(msg_state)
        return result

    def _execute(self, state: MessageState):
        """
        Required by BaseWorker – delegates to execute().
        """
        return self.execute(state)


# TESTS REMOVE FOR FINAL SUBMISSION


if __name__ == "__main__":
    print("SchedulerWorker test run starting")

    # Example input string
    #user_input = "Schedule a meeting with Christian May 6th at 11:30pm"
    #user_input = "Schedule a meeting at 10:00pm today with my mommy"
    user_input = "Schedule a meeting at 10pm today with my mommy"

    # Initialize the worker
    worker = SchedulerWorker()

    # Extract datetime and message
    parsed_time, cleaned_message = worker.extract_task_details(user_input)

    if not parsed_time:
        print(" Failed to parse a time from user input.")
    else:
        print(f" Parsed time: {parsed_time}")
        print(f"Cleaned message: {cleaned_message}")

        # Schedule the task using parsed values
        worker.schedule_user_task(
            user_id="test_user",
            task_time=parsed_time,
            task_data={
                "message": cleaned_message,
                "orchestrator_message": "Scheduled from natural input"
            }
        )
        print(f"Task scheduled for {parsed_time.isoformat()} EDT.")
