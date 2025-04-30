import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

from arklex.env.workers.worker import BaseWorker, register_worker
from arklex.utils.graph_state import MessageState
from arklex.env.workers.message_worker import MessageWorker

from calendar_utils import get_calendar_service # Utility module import

logger = logging.getLogger(__name__)

@register_worker
class SchedulerWorker(BaseWorker):
    """
    A worker that schedules tasks (e.g., message delivery) for the user at a specified time.
    """

    description = "Schedules tasks for the user, such as sending messages or performing actions."

    def __init__(self):
        super().__init__()
        self.scheduler = BackgroundScheduler()
        self.message_worker = MessageWorker()
        self._configure_scheduler()

    def _configure_scheduler(self):
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self.scheduler.start()

    def _job_listener(self, event):
        if event.exception:
            logger.error(f"Job {event.job_id} failed!")
        else:
            logger.info(f"Job {event.job_id} executed successfully.")

    def schedule_user_task(self, user_id, task_time, task_data):
        """
        Schedule a task and create a Google Calendar event.
        """
        trigger = DateTrigger(run_date=task_time)
        job_id = f"user_task_{user_id}_{task_time}"
        self.scheduler.add_job(self.execute_user_task, trigger, args=[user_id, task_data], id=job_id)

        logger.info(f"Task scheduled for user {user_id} at {task_time}. Task details: {task_data}")

        # Optionally create a Google Calendar event
        try:
            self._create_calendar_event(task_time, task_data['message'], user_id)
        except Exception as e:
            logger.error(f"Failed to create Google Calendar event: {e}")

    def _create_calendar_event(self, task_time, message, user_id):
        """
        Creates a Google Calendar event for the scheduled task.
        """
        service = get_calendar_service()

        event = {
            'summary': f'Scheduled Task for User {user_id}',
            'description': message,
            'start': {
                'dateTime': task_time.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (task_time + timedelta(minutes=15)).isoformat(),
                'timeZone': 'UTC',
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        logger.info(f"Created Google Calendar event: {created_event.get('htmlLink')}")

    def execute_user_task(self, user_id, task_data):
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
    
    def execute(self, state):
        """
        Required abstract method implementation.
        Can be left empty or used to call execute_user_task or some default logic.
        """
        logger.info("Execute method called, but it's not implemented for SchedulerWorker.")
        pass


    def cancel_user_task(self, user_id, task_time):
        job_id = f"user_task_{user_id}_{task_time}"
        job = self.scheduler.get_job(job_id)

        if job:
            job.remove()
            logger.info(f"Task for user {user_id} scheduled at {task_time} has been cancelled.")
        else:
            logger.warning(f"No task found for user {user_id} at {task_time}.")