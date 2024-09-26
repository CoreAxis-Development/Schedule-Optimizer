from datetime import date, datetime, timedelta
from django.contrib.auth.models import User


def optimizer(user_id, buffer_days=7):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found'}, 404

    user_profile = user.user_profile
    availability = user_profile.availability

    today = date.today()

    # Fetch tasks, excluding those with due dates before today
    tasks = list(user.tasks.filter(due_date__gte=today).order_by('due_date'))
    scheduled_tasks = []
    updated_availability = availability.copy()

    def is_weekend(day):
        return day.weekday() >= 5

    def get_available_hours(date):
        date_str = date.strftime('%Y-%m-%d')
        return updated_availability.get(date_str, 8)  # Default to 8 if not specified

    def find_next_available_weekday(start_date):
        next_date = start_date
        while is_weekend(next_date):
            next_date += timedelta(days=1)
        return next_date

    def schedule_task(task, schedule_date):
        date_str = schedule_date.strftime('%Y-%m-%d')
        available_hours = get_available_hours(schedule_date)

        if available_hours >= task.completion_hrs:
            updated_availability[date_str] = available_hours - task.completion_hrs
            scheduled_tasks.append({
                'task_id': task.id,
                'task_name': task.name,
                'scheduled_date': date_str,
                'location': task.location.name,
                'due_date': task.due_date.strftime('%Y-%m-%d'),
                'hours': task.completion_hrs
            })
            return True
        return False

    for task in tasks:
        earliest_start = max(today, task.due_date - timedelta(days=buffer_days))
        latest_start = task.due_date

        current_date = find_next_available_weekday(earliest_start)
        scheduled = False

        while current_date <= latest_start:
            if schedule_task(task, current_date):
                scheduled = True
                break
            current_date = find_next_available_weekday(current_date + timedelta(days=1))

        if not scheduled:
            # If we couldn't schedule within the preferred window, try to find the earliest possible date
            current_date = find_next_available_weekday(earliest_start)
            while True:
                if schedule_task(task, current_date):
                    break
                current_date = find_next_available_weekday(current_date + timedelta(days=1))

    # Sort scheduled tasks by scheduled date
    scheduled_tasks.sort(key=lambda x: x['scheduled_date'])

    # Calculate and include statistics
    total_tasks = len(tasks)
    scheduled_count = len(scheduled_tasks)
    unscheduled_count = total_tasks - scheduled_count

    return {
        'scheduled_tasks': scheduled_tasks,
        'updated_availability': updated_availability,
        'stats': {
            'total_tasks': total_tasks,
            'scheduled_tasks': scheduled_count,
            'unscheduled_tasks': unscheduled_count,
            'scheduling_success_rate': (scheduled_count / total_tasks) * 100 if total_tasks > 0 else 0
        }
    }