'''
This script can be used to generate the TA reports.

Note that the code is hideous and poorly documented.
'''

import yaml
import os
import sys
import requests
import requests_cache
import argparse
import hashlib
import csv
from pprint import pprint
from datetime import datetime
import time
from natsort import natsorted
from collections import Counter, defaultdict
try:
    from tqdm import tqdm
except:
    print("TQDM is not installed. No progress bars will be available.")
    tqdm = list

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pyplot

from canvas_tools import get, post, put, delete
from canvas_tools import get_setting, courses

from canvas_tools import yaml_load

#requests_cache.install_cache('canvas_requests')

plt.style.use('seaborn-darkgrid')
matplotlib.rcParams.update({'font.size': 12})

if len(sys.argv) >= 2:
    COURSE = sys.argv[1]
else:
    COURSE = get_setting('course')
course_id = courses[COURSE]['id']

CANVAS_DATE_STRING = "%Y-%m-%dT%H:%M:%SZ"
def days_between(d1, d2=None):
    d1 = datetime.strptime(d1, CANVAS_DATE_STRING)
    if d2 is None:
        d2 = datetime.utcnow()
    else:
        d2 = datetime.strptime(d2, CANVAS_DATE_STRING)
    return abs((d2 - d1).days)
    
def seconds_to_days(time):
    return time/60./60/24

today = time.strftime("%m-%d")
log_path = 'reports/'+COURSE+'_report_{}.html'.format(today)
log_path_pdf = 'reports/'+COURSE+'_report_{}.pdf'.format(today)
log_file = open(log_path, 'w')
def log(*data, type="body"):
    print(*data)
    message = ' '.join(map(str, data))
    if type == "body":
        log_file.write("<p>"+message+"</p>\n")
        
from io import BytesIO
import base64
def log_plot(size=(3.5, 3)):
    fig = plt.gcf()
    fig.set_size_inches(*size)
    figfile = BytesIO()
    plt.tight_layout()
    plt.savefig(figfile, format='png')
    figfile.seek(0)  # rewind to beginning of file
    figdata_png = base64.b64encode(figfile.getvalue()).decode('utf8')
    log_file.write('<img src="data:image/png;base64,{}">\n'.format(figdata_png))
    
log_file.write('''
<!doctype html>

<html lang="en">
<head>
  <meta charset="utf-8">

  <title>The HTML5 Herald</title>
  <meta name="description" content="The HTML5 Herald">
  <meta name="author" content="SitePoint">

  <style>
  body {
    font-size: 14pt;
  }
  </style>

  <!--[if lt IE 9]>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html5shiv/3.7.3/html5shiv.js"></script>
  <![endif]-->
</head>
<body>
''')
log_file.write("<h2>Course Statistics</h2>\n")
log_file.write("<div style='margin-left:10px'>")

# TA Map
print("Reading TA Map")
ta_map_filename = courses[COURSE]["ta_map"]
ta_lookup = yaml_load(ta_map_filename)
group_ta_lookup = defaultdict(list)
for group_name, ta_name in ta_lookup.items():
    group_ta_lookup[ta_name].append(group_name)
tas = set(ta_lookup.values())
log(len(tas), "TAs")
known_groups = set(ta_lookup.keys())
log(len(known_groups), "groups")
# Download groups
print("Downloading groups")
groups = get('groups', all=True, course=COURSE)
groups = [g for g in groups if g['name'] in known_groups]
# Download users
print("Downloading users")
users = get('users', all=True, course=COURSE,
            data={'enrollment_type[]': 'student',
                  'enrollment_state[]': ['active', 'invited', 'rejected', 
                                         'completed', 'inactive']})
user_lookup = {u['id']: u for u in users}
get_user_id = lambda u: u['id']
student_index = {u['id']: i
                 for i, u in enumerate(sorted(users, key=get_user_id))}
log(len(users), "students")log(
# Download mapping
print("Downloading group/user mapping")
group_users = {}
user_ta_lookup = {}
for group in groups:
    group_id = group['id']
    group_name = group['name']
    group_membership = get('groups/{}/users'.format(group_id), 
                           course=None, all=True)
    group_users[group_name] = [m['id'] for m in group_membership]
    for user in group_membership:
        user_ta_lookup[user['id']] = ta_lookup[group_name]
log(sum(map(len, group_users.values())), "users")
# Download assignments
print("Downloading assignments")
assignments = get('assignments', all=True, data={
    'include[]': ['all_dates', 'overrides']
}, course=COURSE)
assignments = [a for a in assignments if a['needs_grading_count']]
assignment_lookup = {a['id']: a for a in assignments}
log(len(assignments), "ungraded assignments")
# Download assignment groups
print("Downloading assignment groups")
assignment_groups = {a['id']: a for a in get('assignment_groups', all=True)}
log(len(assignment_groups), "overall assignment groups")
# Download submissions
print("Downloading submissions")
submissions = get('students/submissions', all=True, data={
    'student_ids[]': 'all',
    # TODO: Speed hack to skip graded assignments
    'assignment_ids[]': list(assignment_lookup.keys()),
    'include[]': ['visibility']
}, course=COURSE)
log(len(submissions), "possible submissions")

log("Processing Data")
# Find ungraded for each TA
'workflow_state'
'seconds_late'
'late'
'graded_at'
'missing'
ta_data = {}
for ta in tas:
    ta_data[ta] = {
        'students': set(),
        'ungradeds': 0,
        'ungraded links': [],
        'graded': 0,
        'lates': 0,
        'late durations': [],
        'ungrade delays': [],
        'grade delays': []
    }
SPEED_GRADER_URL = (get_setting('canvas-base-url')
                    +'courses/{course_id}/gradebook/'
                    +'speed_grader?assignment_id={assignment_id}'
                    +'#%7B%22student_id%22%3A%22{user_id}%22%7D')
all_ungraded = 0
students_lateness = defaultdict(list)
high_priority = 0
for submission in submissions:
    # Assignment info
    assignment_id = submission['assignment_id']
    if assignment_id not in assignment_lookup:
        # Somehow, found an invalid assignment
        log("Invalid assignment ID:", assignment_id)
        continue
    assignment = assignment_lookup[assignment_id]
    assignment_name = assignment['name']
    due_at = assignment['due_at']
    # Skip attendance
    if assignment_name == "Roll Call Attendance":
        continue
    
    # Submission info
    grade_delay = 0
    late = submission['late']
    graded_at = submission['graded_at']
    submitted_at = submission['submitted_at']
    missing = submission['missing']
    user_id = submission['user_id']
    if user_id not in user_lookup:
        continue
    user_name = user_lookup[user_id]['name']
    workflow_state = submission['workflow_state']
    grade = submission['grade']
    grader_id = submission['grader_id']
    if grader_id and grader_id <= 0 and workflow_state == "graded":
        continue
    seconds_late = submission['seconds_late']
    speedgrader_url = SPEED_GRADER_URL.format(assignment_id=assignment_id, user_id=user_id, course_id=course_id)
    clean_url = "<a href='{}' target='_blank'>{} for {}</a>".format(speedgrader_url, assignment_name, user_name)
    students_lateness[user_id].append(seconds_to_days(seconds_late))
    ta = user_ta_lookup[user_id]
    if late:
        ta_data[ta]['lates'] += 1
        ta_data[ta]['late durations'].append(seconds_late/60./60/24)
        if workflow_state == "graded":
            #Submitted late, graded
            grade_delay = days_between(graded_at, submitted_at)
            ta_data[ta]['grade delays'].append(grade_delay)
            ta_data[ta]['graded'] += 1
        else:
            #Submitted late, not graded yet
            ta_data[ta]['ungradeds'] += 1
            all_ungraded += 1
            grade_delay = days_between(submitted_at)
            very_late = grade_delay >= 7
            ta_data[ta]['ungraded links'].append((due_at, very_late, clean_url))
            if very_late:
                high_priority += 1
            ta_data[ta]['ungrade delays'].append(grade_delay)
        ta_data[ta]['students'].add(user_id)
    elif missing:
        #Not due yet, not yet submitted
        pass
    elif submitted_at and workflow_state == "graded":
        #Submitted early, graded
        grade_delay = days_between(graded_at, submitted_at)
        ta_data[ta]['grade delays'].append(grade_delay)
        ta_data[ta]['graded'] += 1
        ta_data[ta]['students'].add(user_id)
    elif submitted_at:
        #Submitted early, not graded yet
        ta_data[ta]['ungradeds'] += 1
        all_ungraded += 1
        grade_delay = days_between(submitted_at)
        very_late = grade_delay >= 7
        ta_data[ta]['ungraded links'].append((due_at, very_late, clean_url))
        if very_late:
            high_priority += 1
        ta_data[ta]['ungrade delays'].append(grade_delay)
        
log(all_ungraded, "submissions still ungraded")
log(high_priority, "overdue for grading (>=7 days)")
log_file.write("</div>")

ta_rename = {}

ungraded_counts = {ta_rename.get(ta, ta): ta_data[ta]['ungradeds'] for ta in ta_data}
df = pd.DataFrame.from_dict(ungraded_counts, orient='index')
df.sort_values(by=0, inplace=True)
df.plot.barh(legend=False, )
plt.xlabel("Number of Ungraded Assignments")
plt.title("Number of Ungraded Assignments per TA")
plt.xticks(rotation=45)
log_plot((7, 5))
plt.clf()
for column, label in [('ungrade delays', 'Delay in Ungraded Assignments'),
                      ('grade delays', 'Delay in Graded Assignments'),
                      ('late durations', 'Delay in Student Submission')]:
    tidy_data = []
    for ta, ta_item in ta_data.items():
        for grade in ta_item[column]:
            tidy_data.append((ta_rename.get(ta, ta), grade))
    if not tidy_data:
        continue
    df = pd.DataFrame(tidy_data, columns=['TA', label])
    ax = df.boxplot(column=label, by='TA')
    plt.ylabel("Days")
    plt.xticks(rotation=45)
    ax.get_figure().suptitle("")
    log_plot((7, 4))
    plt.clf()
    
def color_patches(bins, patches):
    for c, p in zip(bins, patches):
        if c < 7:
            plt.setp(p, 'facecolor', 'cornflowerblue')
        elif c >= 7 and c < 14:
            plt.setp(p, 'facecolor', 'blue')
        else:
            plt.setp(p, 'facecolor', 'darkblue')

for ta in sorted(tas):
    log_file.write("<h2>{}</h2>\n".format(ta))
    #
    log_file.write("<div style='margin-left:10px'>")
    log("Students:", len(ta_data[ta]['students']))
    log("Submitted Late:", ta_data[ta]['lates'])
    log("Graded:", ta_data[ta]['graded'])
    log("Ungraded:", ta_data[ta]['ungradeds'])
    log("Overdue (>=7 days):", len([delay
                                    for delay in ta_data[ta]['ungrade delays']
                                    if delay >= 7]))

    log("Ungraded Assignments:")
    # Links
    log_file.write('<ul>\n')
    sort_subs = lambda r: (-r[1] if r[1] is not None else 0, 
                           r[0] if r[0] is not None else 0)
    ungraded = ta_data[ta]['ungraded links']
    for aname, is_high_priority, url in natsorted(ungraded, key=sort_subs):
        if is_high_priority:
            log_file.write('<li><em>{}</em></li>\n'.format(url))
        else:
            log_file.write('<li>{}</li>\n'.format(url))
    log_file.write('</ul>\n')
    # Distribution
    n, bins, patches = plt.hist(ta_data[ta]['grade delays'])
    color_patches(bins, patches)
    plt.title("Graded Assignments Delay")
    plt.xlabel("Days Late")
    plt.ylabel("Submissions")
    log_plot()
    plt.clf()
    n, bins, patches = plt.hist(ta_data[ta]['ungrade delays'])
    color_patches(bins, patches)
    plt.title("Ungraded Assignments Delay")
    plt.xlabel("Days Late")
    plt.ylabel("Submissions")
    log_plot()
    plt.clf()
    #
    log_file.write("</div>")
# Close everything off
log_file.write('''
</body>
</html>
''')
log_file.close()

import pdfkit
pdfkit.from_file(log_path, log_path_pdf, options={
    'page-size': 'Letter',
    'margin-top': '1in',
    'margin-right': '1in',
    'margin-bottom': '1in',
    'margin-left': '1in'
})