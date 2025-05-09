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

        self._configure_scheduler()
        self.action_graph = self._create_action_graph()


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

        trigger = DateTrigger(run_date=task_time)
        job_id = f"user_task_{user_id}_{task_time}"
        self.scheduler.add_job(self.execute_user_task, trigger, args=[user_id, task_data], id=job_id)
        logger.info(f"Task scheduled for user {user_id} at {task_time}. Task details: {task_data}")

        try:
            self._create_calendar_event(task_time, task_data['message'], user_id)
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")

    def _create_calendar_event(self, task_time, message, user_id):

        service = get_calendar_service()
        print(f"Attempting to create calendar event at {task_time} with message: {message}")

        event = {
            'summary': message,
            'description': f'Scheduled Through RYAA for {user_id}',
            'start': {
                'dateTime': task_time.isoformat(),

                'timeZone': 'America/New_York',
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


    def extract_task_details(self, user_input: str):
        time_pattern = re.compile(
            r"((on\s+)?[A-Z]?[a-z]+\s+\d{1,2}(st|nd|rd|th)?(,?\s+\d{4})?)?\s*(at\s+)?"
            r"(\d{1,2}(:\d{2})?\s*(am|pm)?|noon|midnight|twelve)",
            re.IGNORECASE
        )
        match = time_pattern.search(user_input)

        if match:
            time_phrase = match.group(0)
            parsed_time = dateparser.parse(time_phrase, settings={"PREFER_DATES_FROM": "future"})
            cleaned = user_input.replace(time_phrase, "").strip(",. ")
        else:
            parsed_time = dateparser.parse(user_input, settings={"PREFER_DATES_FROM": "future"})
            cleaned = user_input.strip()

        prefix_pattern = re.compile(
            r"^(add|schedule|set( up)?|book( me)?|remind( me)?( to| about)?|put( me)?( down)?( for)?|create)\s+(a|an|my)?\s*",
            re.IGNORECASE
        )
        cleaned = prefix_pattern.sub("", cleaned)
        cleaned_message = cleaned.strip().capitalize()

        return parsed_time, cleaned_message

    def main_func(self, state):
        """
        A simplified single-node graph function to parse and schedule tasks.
        """
        user_input = state["user_message"]["history"]
        parsed_time, cleaned_message = self.extract_task_details(user_input)

        if not parsed_time:
            state.response = "⚠️ Could not extract time from input."
            return state

        self.schedule_user_task(
            user_id="test_user",
            task_time=parsed_time,
            task_data={
                "message": cleaned_message,
                "orchestrator_message": "Scheduled from natural input"
            }
        )

        state.response = f" Task scheduled for {parsed_time.isoformat()} EDT."
        return state

    def _create_action_graph(self):
        """
        Defines a simplified graph with a single node: main_func.
        """
        workflow = StateGraph(MessageState)
        workflow.add_node("main_func", self.main_func)
        workflow.add_edge(START, "main_func")
        return workflow

    def _execute(self, msg_state: MessageState):

        graph = self.action_graph.compile()
        result = graph.invoke(msg_state)
        return result





# TEST BLOCK

# if __name__ == "__main__":
#     print("SchedulerWorker test run starting")

#     user_input = "Schedule a meeting at 10pm today with my mommy"
#     worker = SchedulerWorker()
#     parsed_time, cleaned_message = worker.extract_task_details(user_input)

#     if not parsed_time:
#         print("Failed to parse a time from user input.")
#     else:
#         print(f"Parsed time: {parsed_time}")
#         print(f"Cleaned message: {cleaned_message}")

#         worker.schedule_user_task(
#             user_id="test_user",
#             task_time=parsed_time,
#             task_data={
#                 "message": cleaned_message,
#                 "orchestrator_message": "Scheduled from natural input"
#             }
#         )
#         print(f" Task scheduled for {parsed_time.isoformat()} EDT.")

