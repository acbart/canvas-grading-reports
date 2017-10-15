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
users = get('users', all=True, course=COURSE)
user_lookup = {u['id']: u for u in users}
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
assignment_lookup = {a['id']: a for a in assignments}
log(len(assignments), "overall assignments")
# Download submissions
print("Downloading submissions")
submissions = get('students/submissions', all=True, data={
    'student_ids[]': 'all',
    'include[]': ['visibility']
}, course=COURSE)
log(len(submissions), "possible submissions")

print("Processing Data")
# Find ungraded for each TA
'workflow_state'
'seconds_late'
'late'
'graded_at'
'missing'
ta_data = {}
for ta in tas:
    ta_data[ta] = {
        'ungradeds': 0,
        'ungraded links': [],
        'graded': 0,
        'lates': 0,
        'late durations': [],
        'ungrade delays': [],
        'grade delays': []
    }
SPEED_GRADER_URL = 'https://vt.instructure.com/courses/{course_id}/gradebook/speed_grader?assignment_id={assignment_id}#%7B%22student_id%22%3A%22{user_id}%22%7D'
all_ungraded = 0
for submission in submissions:
    grade_delay = 0
    late = submission['late']
    graded_at = submission['graded_at']
    submitted_at = submission['submitted_at']
    missing = submission['missing']
    user_id = submission['user_id']
    if user_id not in user_ta_lookup:
        continue
    user_name = user_lookup[user_id]['name']
    grade = submission['grade']
    grader_id = submission['grader_id']
    if grader_id and grader_id <= 0:
        continue
    seconds_late = submission['seconds_late']
    assignment_id = submission['assignment_id']
    if assignment_id not in assignment_lookup:
        continue
    assignment = assignment_lookup[assignment_id]
    assignment_name = assignment['name']
    if assignment_name == "Roll Call Attendance":
        continue
    #if user_id == 15866 and assignment_id==270590:
    #    pprint(submission)
    speedgrader_url = SPEED_GRADER_URL.format(assignment_id=assignment_id, user_id=user_id, course_id=course_id)
    clean_url = "<a href='{}' target='_blank'>{} for {}</a>".format(speedgrader_url, assignment_name, user_name)
    ta = user_ta_lookup[user_id]
    if late:
        ta_data[ta]['lates'] += 1
        ta_data[ta]['late durations'].append(seconds_late/60./60/24)
        if grade:
            #Submitted late, graded
            grade_delay = days_between(graded_at, submitted_at)
            ta_data[ta]['grade delays'].append(grade_delay)
            ta_data[ta]['graded'] += 1
        else:
            #Submitted late, not graded yet
            ta_data[ta]['ungradeds'] += 1
            all_ungraded += 1
            ta_data[ta]['ungraded links'].append(clean_url)
            grade_delay = days_between(submitted_at)
            ta_data[ta]['ungrade delays'].append(grade_delay)
    elif missing:
        #Not due yet, not yet submitted
        pass
    elif submitted_at and grade:
        #Submitted early, graded
        grade_delay = days_between(graded_at, submitted_at)
        ta_data[ta]['grade delays'].append(grade_delay)
        ta_data[ta]['graded'] += 1
    elif submitted_at:
        #Submitted early, not graded yet
        ta_data[ta]['ungradeds'] += 1
        all_ungraded += 1
        ta_data[ta]['ungraded links'].append(clean_url)
        grade_delay = days_between(submitted_at)
        ta_data[ta]['ungrade delays'].append(grade_delay)
        
log(all_ungraded, "still ungraded")
log_file.write("</div>")

ta_rename = {}

ungraded_counts = {ta_rename.get(ta, ta): ta_data[ta]['ungradeds'] for ta in ta_data}
df = pd.DataFrame.from_dict(ungraded_counts, orient='index')
df.plot.barh(legend=False, )
plt.xlabel("Number of Ungraded Assignments")
plt.title("Number of Ungraded Assignments per TA")
log_plot((7, 4))
plt.clf()
for column, label in [('ungrade delays', 'Delay in Ungraded Assignments'),
                      ('grade delays', 'Delay in Graded Assignments'),
                      ('late durations', 'Delay in Student Submission')]:
    tidy_data = []
    for ta, ta_item in ta_data.items():
        for grade in ta_item[column]:
            tidy_data.append((ta_rename.get(ta, ta), grade))
    df = pd.DataFrame(tidy_data, columns=['TA', label])
    ax = df.boxplot(column=label, by='TA')
    plt.ylabel("Days")
    ax.get_figure().suptitle("")
    log_plot((7, 3))
    plt.clf()

for ta in sorted(tas):
    log_file.write("<h2>{}</h2>\n".format(ta))
    #
    log_file.write("<div style='margin-left:10px'>")
    log("Submitted Late:", ta_data[ta]['lates'])
    log("Graded:", ta_data[ta]['graded'])
    log("Ungraded:", ta_data[ta]['ungradeds'])
    log("Ungraded Assignments:")
    # Links
    log_file.write('<ul>\n')
    for url in natsorted(ta_data[ta]['ungraded links']):
        log_file.write('<li>{}</li>\n'.format(url))
    log_file.write('</ul>\n')
    # Distribution
    plt.hist(ta_data[ta]['grade delays'])
    plt.title("Graded Assignments Delay")
    plt.xlabel("Days Late")
    plt.ylabel("Submissions")
    log_plot()
    plt.clf()
    plt.hist(ta_data[ta]['ungrade delays'], color='red')
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