from datetime import datetime, timedelta
import sys
import os

# Add the 'agentorg' folder to the Python path
# Add the 'Agent-First-Organization' folder to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentorg.workers.scheduler_worker import SchedulerWorker  # Now it will work

# Create the worker
workers = SchedulerWorker()

# Set up test data
user_id = "testuser1"
run_time = datetime.utcnow() + timedelta(minutes=1)  # 1 minute from now
task_data = {
    "message": "Hello from SchedulerWorker!",
    "orchestrator_message": "This is a scheduled task test."
}

# Schedule the task
workers.schedule_user_task(user_id, run_time, task_data)

print(f"Task scheduled for {run_time.isoformat()} UTC. Check your calendar!")
