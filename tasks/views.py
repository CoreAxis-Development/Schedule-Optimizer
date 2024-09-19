from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from datetime import date, datetime, timedelta
from .models import Location, Task
import json
from datetime import date, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
import logging
import requests

logger = logging.getLogger(__name__)
def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        next_url = request.POST.get("next")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(next_url or "/")
        else:
            # Add an error message if login fails
            return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")


def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
    else:
        form = UserCreationForm()
    return render(request, "signup.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def index(request):
    today = date.today()
    formatted_date = today.strftime("Today: %A, %B %d, %Y")
    due_next = {}

    if request.method == "POST":
        sample = json.loads(request.body).get("sample", 7)
    else:
        sample = request.GET.get("sample", 7)

    # Use the optimizer to get scheduled tasks
    optimizer_data = {
        'user_id': request.user.id,
        'buffer_days': sample
    }
    optimizer_response = requests.post('http://localhost:8000/optimizer/', json=optimizer_data)
    scheduled_tasks = optimizer_response.json().get('scheduled_tasks', [])

    # Create a mapping of task names to their scheduled dates and due dates
    task_schedule = {(task['task_name'], task['location']):
                     {'scheduled_date': task['scheduled_date'],
                      'due_date': task['due_date']}
                     for task in scheduled_tasks}

    for location in request.user.locations.all():
        location_tasks = Task.objects.filter(user=request.user, location=location)
        due_next[str(location)] = {}
        for task in location_tasks:
            task_info = task_schedule.get((task.name, str(location)))
            if task_info:
                scheduled_date = task_info['scheduled_date']
                if scheduled_date not in due_next[str(location)]:
                    due_next[str(location)][scheduled_date] = []
                due_next[str(location)][scheduled_date].append({
                    'name': task.name,
                    'scheduled_date': scheduled_date,
                    'due_date': task_info['due_date']
                })

    context = {
        "today_date": formatted_date,
        "sample": sample,
        "today": today,
        "dates": (dates:=[today + timedelta(_) for _ in range(0, sample)]),
        "dates_str": [day.strftime('%Y-%m-%d') for day in dates],
        "due_next": due_next,
        "next_decade": [today.year+i for i in range(10)],
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "weekdays":["Sunday","Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    }
    if request.method == "POST":
        return JsonResponse({"text":render(request, "test_dates.html", context).content.decode()})
    return render(request, "base.html", context)

def all_yearly_tasks(request):
    data = json.loads(request.body)
    year = data.get("year")
    filt = data.get("filter", {})
    year_view = {month: {"days_in_month": 31 if month in [1, 3, 5, 7, 8, 10, 12] else 30 if month in [4, 6, 9, 11] else 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28} for month in range(1, 13)}
    year_view.update({"year":year, "unique_locations":[], "unique_tasks":{}})
    
    # Use the optimizer to get scheduled tasks for the entire year
    optimizer_data = {
        'user_id': request.user.id,
        'buffer_days': 365
    }
    optimizer_response = requests.post('http://localhost:8000/optimizer/', json=optimizer_data)
    scheduled_tasks = optimizer_response.json().get('scheduled_tasks', [])

    tasks = request.user.tasks.all()
    if filt:
        tasks = tasks.filter(**filt)
    unique_locations = list(set(task.location.name for task in tasks))
    unique_tasks = list(set(task.name for task in tasks))
    year_view["unique_locations"] = unique_locations
    year_view["unique_tasks"] = unique_tasks

    # Create a mapping of task names and locations to their database objects
    task_objects = {(task.name, task.location.name): task for task in tasks}

    for task in scheduled_tasks:
        task_date = datetime.strptime(task['scheduled_date'], "%Y-%m-%d").date()
        if task_date.year == year:
            month = task_date.month
            day = task_date.day
            db_task = task_objects.get((task['task_name'], task['location']))
            if db_task:
                task_info = {
                    "name": task['task_name'],
                    "location": task['location'],
                    "time_taken": task['hours'],
                    "due_date": task['scheduled_date'],  # Use scheduled_date as due_date
                    "milepost": db_task.location.milepost
                }
                if day not in year_view[month]:
                    year_view[month][day] = {1: task_info}
                else:
                    daily_tasks = year_view[month][day]
                    day_arr = list(daily_tasks.values()) + [task_info]
                    day_arr.sort(key=lambda x: x["milepost"])
                    year_view[month][day] = {_+1: daym for _, daym in enumerate(day_arr)}

    return JsonResponse(year_view)

def task_list_week(request):
    date_str = request.GET.get('date')
    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    start_of_week = date_obj - timedelta(days=date_obj.weekday()+1)
    end_of_week = start_of_week + timedelta(days=6)

    # Use the optimizer to get scheduled tasks for the week
    optimizer_data = {
        'user_id': request.user.id,
        'buffer_days': 7
    }
    optimizer_response = requests.post('http://localhost:8000/optimizer/', json=optimizer_data)
    scheduled_tasks = optimizer_response.json().get('scheduled_tasks', [])

    # Create a mapping of task names and locations to their database objects
    tasks = Task.objects.filter(user=request.user)
    task_objects = {(task.name, task.location.name): task for task in tasks}

    task_list = []
    for task in scheduled_tasks:
        scheduled_date = datetime.strptime(task['scheduled_date'], "%Y-%m-%d").date()
        if start_of_week <= scheduled_date <= end_of_week:
            db_task = task_objects.get((task['task_name'], task['location']))
            if db_task:
                task_list.append({
                    'name': task['task_name'],
                    'time_taken': task['hours'],
                    "location": task['location'],
                    "due_date": task['scheduled_date'],  # Use scheduled_date as due_date
                    "id": db_task.id,
                })

    return JsonResponse(task_list, safe=False)
@require_POST
def yearly_tasks(request):
    # Yearly tasks per location for page 1
    data = json.loads(request.body)
    year = data.get('year')
    location_id = data.get('location_id')
    location = Location.objects.get(name=location_id)
    tasks = location.this_year_tasks(year)

    return JsonResponse({'tasks': tasks, "length":len(tasks)})

def get_next_available_day(request, year_view: dict, year: int, month: int, day: int):
    # also page 1
    user = request.user.user_profile
    while True:
        day += 1
        if day > year_view[month]['days_in_month']:
            day = 1
            month += 1
            if month > 12:
                return None, None
        # Check if the current day is not Saturday (5) or Sunday (6)
        availability = user.availability.get(f"{year}-{month:02d}-{day:02d}", 0)
        current_date = date(year, month, day)
        if current_date.weekday() < 5 and sum(task['time_taken'] for task in year_view[month].get(day, {}).values()) < 8 + availability:
            return month, day

@require_POST
def add_availability(request):
    if request.method == 'POST':
        date = request.POST.get('date')
        hours = int(request.POST.get('hours'))
        task_list = request.POST.getlist('task_list')

        # Update user's availability
        user_profile = request.user.user_profile
        availability = dict(user_profile.availability)
        availability[date] = availability.get(date, 0) + hours
        user_profile.availability = availability
        user_profile.save()

        # Move tasks to the selected date
        for task_id in task_list:
            task = Task.objects.get(id=task_id)
            task.buffered_date = datetime.strptime(date, '%Y-%m-%d').date()
            task.save()

        return redirect('home')
    return JsonResponse({'status': 'error'}, status=400)

@require_POST
def remove_availability(request):
    if request.method == 'POST':
        date_str = request.POST.get('date')
        hours = int(request.POST.get('hours'))
        task_list = request.POST.getlist('remove_task_list')

        # Update user's availability
        user_profile = request.user.user_profile
        availability = user_profile.availability
        availability[date_str] = availability.get(date_str, 0) - hours
        user_profile.availability = availability
        user_profile.save()

        # Construct year_view on the fly
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        year = date_obj.year
        year_view = {month: {"days_in_month": 31 if month in [1, 3, 5, 7, 8, 10, 12] else 30 if month in [4, 6, 9, 11] else 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28} for month in range(1, 13)}
        

        # Populate year_view with tasks
        for task in request.user.tasks.filter(buffered_date__year=year):
            buffered_date = task.buffered_date
            month = buffered_date.month
            day = buffered_date.day
            if day not in year_view[month]:
                year_view[month][day] = {1: task.json()}
            else:
                daily_tasks = year_view[month][day]
                day_arr = list(daily_tasks.values()) + [task.json()]
                day_arr.sort(key=lambda x: x["location"])
                year_view[month][day] = {_+1: daym for _, daym in enumerate(day_arr)}

        # Move tasks to the next available day
        for task_id in task_list:
            task = Task.objects.get(id=task_id)
            current_month = date_obj.month
            current_day = date_obj.day
            next_month, next_day = get_next_available_day(request, year_view, year, current_month, current_day)
            if next_month and next_day:
                next_available_date = date(year, next_month, next_day)
                task.buffered_date = next_available_date
                task.save()

        return redirect('home')
    return JsonResponse({'status': 'error'}, status=400)

@require_POST
def move_task(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        task_id = int(data.get('task_id'))
        new_date = data.get('new_date')

        try:
            task = Task.objects.get(id=task_id, user=request.user)
            new_date_obj = datetime.strptime(new_date, '%Y-%m-%d').date()

            task.buffered_date = new_date_obj

            # Call next_occurrence() method
            task.next_occurrence()
            task.save()

            return JsonResponse({'status': 'success'})
        except Task.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid date format'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@csrf_exempt
@require_POST
def optimizer(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        buffer_days = data.get('buffer_days', 7)  # Default to 7 if not provided

        if not user_id:
            return JsonResponse({'error': 'User ID is required'}, status=400)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

        user_profile = user.user_profile
        availability = user_profile.availability

        tasks = list(user.tasks.all().order_by('due_date'))
        locations = user.locations.all()

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
            schedule_date = max(today, task.due_date - timedelta(days=buffer_days))
            schedule_date = find_next_available_weekday(schedule_date)

            while schedule_date <= task.due_date:
                if schedule_task(task, schedule_date):
                    break
                schedule_date = find_next_available_weekday(schedule_date + timedelta(days=1))

            # If we couldn't schedule before or on the due date, schedule on the due date anyway
            if schedule_date > task.due_date:
                schedule_task(task, task.due_date)

        # Sort scheduled tasks by scheduled_date
        scheduled_tasks.sort(key=lambda x: x['scheduled_date'])

        return JsonResponse({
            'scheduled_tasks': scheduled_tasks,
            'updated_availability': updated_availability
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)
@csrf_exempt
def user_info(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')

            if not user_id:
                return JsonResponse({'error': 'User ID is required'}, status=400)

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({'error': 'User not found'}, status=404)

            user_profile = user.user_profile
            tasks = user.tasks.all()
            locations = user.locations.all()

            user_info = {
                'username': user.username,
                'email': user.email,
                'profile': {
                    'availability': user_profile.availability,
                    'safety_buffer_days': user_profile.safety_buffer_days,
                    'show_tooltip': user_profile.show_tooltip,
                },
                'tasks': [
                    {
                        'name': task.name,
                        'frequency': task.frequency,
                        'completion_hrs': task.completion_hrs,
                        'due_date': task.due_date.strftime('%Y-%m-%d'),
                        'buffered_date': task.buffered_date.strftime('%Y-%m-%d') if task.buffered_date else None,
                        'location': task.location.name,
                    } for task in tasks
                ],
                'locations': [
                    {
                        'name': location.name,
                        'milepost': location.milepost,
                    } for location in locations
                ]
            }

            return JsonResponse(user_info)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


def fetch_all_yearly_tasks(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        year = data.get('year')
        filter = data.get('filter', {})
        buffer = data.get('buffer', 0)

        # Adjust the logic to consider the buffer period
        tasks = Task.objects.filter(user=request.user)
        year_view = {}
        for task in tasks:
            task.user.user_profile.safety_buffer_days = buffer
            task.save()
            occurrences = task.all_task_occurences(year)
            for month, days in occurrences.items():
                if month not in year_view:
                    year_view[month] = {}
                for day in days:
                    if day not in year_view[month]:
                        year_view[month][day] = []
                    year_view[month][day].append(task.json())

        return JsonResponse(year_view)