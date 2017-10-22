__author__ = 'Jan Deschuttere'

from httplib import HTTPSConnection
from base64 import b64encode
import json
from datetime import timedelta, date
import ConfigParser
import argparse

parser = argparse.ArgumentParser(description="A simple script to assist in the day to day time tracking.")
parser.add_argument("--days", default=0, type=int, help="The amount of days to correct (0 is today, 6 is an entire week)")
parser.add_argument("--project", type=int, help="The id of the project you want to analyse")
parser.add_argument("--excess-task", type=int, help="The id of the task where the excess of hours need to be registered")
parser.add_argument("--max-hours", type=int, default=8, help="The max amount of hours that are billable in a day")
args = parser.parse_args()

config = ConfigParser.RawConfigParser()
config.read('config.ini')

username = config.get('auth', 'username')
password = config.get('auth', 'password')
subdomain = config.get('general', 'subdomain')

# 0 is only today, 6 is the entire week
days_to_correct = args.days

# Showpad project specific right now, we have a limit of 8h billable a day
project_id = args.project
daily_hour_limit = args.max_hours
task_non_billable_hour = args.excess_task

host = '%s.harvestapp.com' % subdomain
basicAuth = b64encode('%s:%s' % (username, password))
harvestApiHeaders = {
    'Authorization': "Basic %s" % basicAuth,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}


def requestHarvest(day_of_year, year):
    conn = HTTPSConnection(host)
    conn.request("GET", "/daily/%d/%d" % (day_of_year, year), None, harvestApiHeaders)
    raw_response = conn.getresponse()
    body = raw_response.read().decode('utf-8')
    conn.close()
    if raw_response.status > 206:
        print("Unexpected response %d, %s" % (raw_response.status, body))
        exit()
    return json.loads(body)


def readProjectConfig(response, project_id):
    project_config = None
    for project in response['projects']:
        if project['id'] == project_id:
            project_config = project
            break
        else:
            continue

    if project_config is None:
        print("Project is not an active project, not sure what to do, exiting to do no harm")
        exit()
    return project_config


def detectBillableTasks(project_config):
    tasks = []
    if 'tasks' not in project_config:
        print("There are no billable tasks for the project")
    else:
        for task in project_config['tasks']:
            if task['billable']:
                tasks.append(task['id'])

    return tasks


def detectTasksInDay(dayEntries, project_id, billable_tasks):
    dayDictionaryHours = {}
    dayDictionaryTasks = {}

    for entry in dayEntries:
        # Skip projects we have no interest in
        if int(entry['project_id']) != project_id:
            continue

        # Skip tasks that are not billable
        if int(entry['task_id']) not in billable_tasks:
            continue

        day = entry['spent_at']
        if day in dayDictionaryHours:
            dayHours = dayDictionaryHours[day]
        else:
            dayHours = 0
        dayDictionaryHours[day] = dayHours + entry['hours']

        if day not in dayDictionaryTasks:
            dayDictionaryTasks[day] = []
        dayDictionaryTasks[day].append(entry)

    return {'hours': dayDictionaryHours, 'tasks': dayDictionaryTasks}


def correctHarvestTimetracking(day_of_year, year):
    response = requestHarvest(day_of_year, year)
    project_config = readProjectConfig(response, project_id)
    billable_tasks = detectBillableTasks(project_config)
    view_by_day = detectTasksInDay(response['day_entries'], project_id, billable_tasks)

    tasksToBeDeleted = []

    for day in view_by_day['hours']:
        hours = view_by_day['hours'][day]
        tasks = {}
        nonBillableTasks = []
        if hours > daily_hour_limit:
            # Merge tasks that are the same
            for task in view_by_day['tasks'][day]:
                # We're not checking on project_id because that should've already been done way before getting here
                # Making sure if we can map the task as expected
                if 'task_id' not in task:
                    continue
                taskId = task['task_id']
                if 'hours_without_timer' not in task and 'hours' not in task:
                    # What is this madness? skip!
                    continue
                elif 'hours' not in task:
                    task['hours'] = task['hours_without_timer']
                elif 'hours_without_timer' not in task:
                    task['hours_without_timer'] = task['hours']

                if taskId in tasks:
                    previousTask = tasks[taskId]
                    previousTask['hours_without_timer'] += task['hours_without_timer']
                    previousTask['hours'] += task['hours']
                    # The task is merged, time to map it for deletion
                    tasksToBeDeleted.append(task['id'])
                else:
                    tasks[task['task_id']] = task

            # Correct to limit
            for task_id in tasks:
                task = tasks[task_id]
                differenceHoursTimer = task['hours'] - daily_hour_limit
                differenceHoursNoTimer = task['hours_without_timer'] - daily_hour_limit
                # Add non billable task
                if differenceHoursTimer > 0 or differenceHoursNoTimer > 0:
                    non_billable_entry = {
                        "notes": "Non billable overtime",
                        "hours": differenceHoursTimer,
                        "hours_without_timer": differenceHoursNoTimer,
                        "project_id": project_id,
                        "task_id": task_non_billable_hour,
                        "spent_at": task['spent_at']
                    }
                    nonBillableTasks.append(non_billable_entry)
                    task['hours'] = daily_hour_limit
                    task['hours_without_timer'] = daily_hour_limit

                    withoutTimerNote = "without timer -%d" % differenceHoursNoTimer
                    withTimerNote = "with timer -%d" % differenceHoursTimer

                    if 'notes' in task and task['notes'] is not None:
                        original_notes = task['notes'] + " "
                    else:
                        original_notes = ""

                    task['notes'] = original_notes + "** corrected: %s and %s ** " % (withTimerNote, withoutTimerNote)

            # Update harvest with the changes
            for nonBillableTask in nonBillableTasks:
                conn = HTTPSConnection(host)
                conn.request("POST", "/daily/add", json.dumps(nonBillableTask), harvestApiHeaders)
                response = conn.getresponse()
                conn.close()
                if response.status > 201:
                    print(" Could not add non billable task %s, response: %s" % (nonBillableTask, response.readall()))
                else:
                    print(" Added non billable task %s" % nonBillableTask)

            for task_id in tasks:
                updatedBillableTask = tasks[task_id]
                print(updatedBillableTask)
                # Just changing the things we want to change, not posting anything else atm...
                updateInfo = {'hours': updatedBillableTask['hours'], 'hours_without_timer': updatedBillableTask['hours_without_timer'], 'notes': updatedBillableTask['notes']}
                conn = HTTPSConnection(host)
                conn.request("POST", "/daily/update/%s" % updatedBillableTask['id'], json.dumps(updateInfo), harvestApiHeaders)
                response = conn.getresponse()
                conn.close()
                if response.status > 200:
                    print(" Could not update billable task %s, response: %s" % (updatedBillableTask, response.readall()))
                else:
                    print(" update billable task %s" % updatedBillableTask)

            for deletableTaskId in tasksToBeDeleted:
                conn = HTTPSConnection(host)
                conn.request("DELETE", "/daily/delete/%d" % deletableTaskId, None, harvestApiHeaders)
                response = conn.getresponse()
                conn.close()
                if response.status > 200:
                    print(" Could not delete task %s, response: %s" % (updatedBillableTask, response.readall()))
                else:
                    print(" Deleted task %s" % updatedBillableTask)

def daterange(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)


def main():
    # Prepare a range to have the last week covered
    start_date = date.today() - timedelta(days=days_to_correct)
    end_date = date.today() + timedelta(days=1)
    # Start correcting
    for single_date in daterange(start_date, end_date):
        print("Checking date %s" % single_date.strftime('%Y-%m-%d'))
        correctHarvestTimetracking(single_date.timetuple().tm_yday, single_date.year)


if __name__ == '__main__':
    main()

