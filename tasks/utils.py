from datetime import date, datetime, timedelta
from django.contrib.auth.models import User

def optimizer(user_id, buffer_days=7):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found'}, 404

    user_profile = user.user_profile
    availability = user_profile.availability

    tasks = list(user.tasks.all().order_by('due_date'))
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
                'task_name': task.name,
                'scheduled_date': date_str,
                'location': task.location.name,
                'due_date': task.due_date.strftime('%Y-%m-%d'),
                'hours': task.completion_hrs
            })
            return True
        return False

    today = date.today()

    for task in tasks:
        target_date = task.due_date - timedelta(days=buffer_days)
        schedule_date = max(today, target_date)
        schedule_date = find_next_available_weekday(schedule_date)

        while schedule_date <= task.due_date:
            if schedule_task(task, schedule_date):
                break
            schedule_date = find_next_available_weekday(schedule_date + timedelta(days=1))

        if schedule_date > task.due_date:
            schedule_task(task, task.due_date)

    scheduled_tasks.sort(key=lambda x: x['scheduled_date'])

    return {
        'scheduled_tasks': scheduled_tasks,
        'updated_availability': updated_availability
    }