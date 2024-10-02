from datetime import date, timedelta
from django.contrib.auth.models import User
from django.db import transaction
from typing import Dict, List, Optional, TypedDict
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ScheduledTask(TypedDict):
    task_id: int
    task_name: str
    scheduled_date: str
    location: str
    due_date: str
    hours: float


class TaskOptimizer:
    def __init__(self, user_id: int, buffer_days: int = 7):
        self.user_id = user_id
        self.buffer_days = buffer_days
        self.today = date.today()
        self.user = self._get_user()
        self.availability = self.user.user_profile.availability.copy()
        self.scheduled_tasks: List[ScheduledTask] = []
        self._initialize_availability()

    def _get_user(self) -> User:
        return User.objects.select_related('user_profile').get(id=self.user_id)

    def _initialize_availability(self):
        """Initialize availability for the next 90 days"""
        for i in range(90):  # Initialize for next 90 days
            current_date = self.today + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str not in self.availability:
                self.availability[date_str] = 8.0 if not self.is_weekend(current_date) else 0.0

    def is_weekend(self, day: date) -> bool:
        return day.weekday() >= 5

    def get_available_hours(self, target_date: date) -> float:
        date_str = target_date.strftime('%Y-%m-%d')
        if date_str not in self.availability:
            self.availability[date_str] = 8.0 if not self.is_weekend(target_date) else 0.0
        return self.availability[date_str]

    def find_valid_slot(self, task, buffer_end_date: date) -> Optional[date]:
        logger.debug(f"Finding slot for task {task.name}. Buffer end date: {buffer_end_date}")

        max_days_before_buffer = max(30, 3 * self.buffer_days)
        max_schedule_date = buffer_end_date - timedelta(days=max_days_before_buffer)

        current_date = self.today
        while current_date < buffer_end_date:  # Strict < to ensure we're before buffer
            if current_date >= max_schedule_date and not self.is_weekend(current_date):
                available_hours = self.get_available_hours(current_date)
                if available_hours >= task.completion_hrs:
                    logger.info(f"Found slot for task {task.name} on {current_date}")
                    return current_date
            current_date += timedelta(days=1)
        return None

    def schedule_task(self, task, schedule_date: date) -> None:
        date_str = schedule_date.strftime('%Y-%m-%d')
        self.availability[date_str] -= task.completion_hrs

        logger.info(f"Scheduled task {task.name} for {date_str}")

        self.scheduled_tasks.append({
            'task_id': task.id,
            'task_name': task.name,
            'scheduled_date': date_str,
            'location': str(task.location),
            'due_date': task.due_date.strftime('%Y-%m-%d'),
            'hours': task.completion_hrs
        })

    @transaction.atomic
    def optimize(self) -> Dict:
        tasks = list(self.user.tasks
                     .filter(due_date__gte=self.today)
                     .order_by('due_date'))

        logger.info(f"Starting optimization for {len(tasks)} tasks")

        for task in tasks:
            buffer_end_date = task.due_date - timedelta(days=self.buffer_days)

            if buffer_end_date <= self.today:
                logger.warning(
                    f"Task {task.name} buffer end date {buffer_end_date} is before or equal to today {self.today}")
                continue

            slot = self.find_valid_slot(task, buffer_end_date)

            if slot:
                self.schedule_task(task, slot)
            else:
                logger.error(
                    f"Could not schedule task: {task.name} - Due: {task.due_date}, Buffer end: {buffer_end_date}")

        self.scheduled_tasks.sort(key=lambda x: x['scheduled_date'])

        scheduled_count = len(self.scheduled_tasks)
        total_tasks = len(tasks)

        return {
            'scheduled_tasks': self.scheduled_tasks,
            'updated_availability': self.availability,
            'stats': {
                'total_tasks': total_tasks,
                'scheduled_tasks': scheduled_count,
                'scheduling_success_rate': (scheduled_count / total_tasks * 100) if total_tasks > 0 else 0
            }
        }


def optimizer(user_id: int, buffer_days: int = 7) -> Dict:
    optimizer = TaskOptimizer(user_id, buffer_days)
    return optimizer.optimize()