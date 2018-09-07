from zipfile import ZipFile
import traceback
import shutil
import json
import yaml
import os
import sys
import requests
import requests_cache
import argparse
import csv
import dateutil.parser
import csv
import codecs
import re
from natsort import natsorted

from datetime import datetime, timedelta
from datetime import date as datetime_date
from pprint import pprint
from collections import Counter, defaultdict
try:
    from tqdm import tqdm
except:
    print("TQDM is not installed. No progress bars will be available.")
    tqdm = list

from canvas_tools import get, post, put, delete
from canvas_tools import get_setting, courses
from canvas_tools import from_canvas_date, to_canvas_date
from canvas_tools import yaml_load

# Make sure they have a dates folder
if not os.path.exists('groups/'):
    os.mkdir('groups/')
    
quiet = True
def log(*args):
    if not quiet:
        print(*args)
        
def show_categories(course):
    categories = get('group_categories', all=True, course=course)
    for category in categories:
        print(category['id'], ': ', category['name'], sep='')
        
def make_groups(course, file, category):
    category = get('group_categories/{}'.format(category), course=None)
    log("Clearing out groups for category:", category['name'])
    old_groups = get('group_categories/{}/groups'.format(category), course=None)
    if isinstance(old_groups, dict) and old_groups['status'] == 'not found':
        pass
    else:
        for group in old_groups:
            log("\tDeleting group", group['name'])
            delete('groups/{}'.format(group['id']), course=None)
    log("Reading new groups")
    with open(file) as inp:
        groups = [line.split(",") for line in inp]
    log("Creating", len(groups), "groups.")
    for i, group_ids in enumerate(groups):
        log("\tCreating Group", i)
        group = post('group_categories/{}/groups'.format(category['id']), 
                     course=None, data= {'name': "Group {}".format(i)})
        for user in group_ids:
            log("\t\tAdding", user)
            post('groups/{}/memberships'.format(group['id']), 
                 data={'user_id': user}, course=None)
            
def import_dates(course, filename):
    if filename is None:
        filename = 'dates/'+str(course)+'_dates.csv'
    log("Reading from", filename)
    dates = []
    with open(filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        header = next(csv_reader)
        next(csv_reader)
        sections = list(extract_sections_from_header(header))
        for line in csv_reader:
            m, k, a, id = line[:4]
            sections_times = {}
            for i, (name, section_id) in enumerate(sections):
                offset = i*3 + 4
                times = line[offset:offset+3]
                fill_missing_times(times)
                sections_times[int(section_id)] = times
            dates.append((m, k, a, int(id), sections_times))
    log("Processed", len(dates), "entries")
    
    log("Downloading assignments")
    assignments = get('assignments', all=True, course=course,
                      data={"include[]": ['overrides']})
    overrides_lookup = {a['id']: a['overrides'] 
                        for a in assignments}
    log("Downloaded", len(assignments), "assignments")
    
    log("Uploading section dates")
    put_count, post_count = 0, 0
    for (m, k, a, aid, section_dates) in tqdm(dates):
        overrides = overrides_lookup[aid]
        override_sections = {o['course_section_id']: o
                             for o in overrides
                             if 'course_section_id' in o}
        for sid, times in section_dates.items():
            o, d, l = map(to_iso8601, times)
            if sid in override_sections:
                override = override_sections[sid]
                oid = override['id']
                put('assignments/{aid}/overrides/{oid}'
                    .format(aid=aid, oid=oid),
                    data={'assignment_override[due_at]': d,
                          'assignment_override[unlock_at]': o,
                          'assignment_override[lock_at]': l}, 
                    course=course)
                put_count += 1
            else:
                post('assignments/{aid}/overrides'.format(aid=aid),
                     data={'assignment_override[course_section_id]': sid,
                           'assignment_override[due_at]': d,
                           'assignment_override[unlock_at]': o,
                           'assignment_override[lock_at]': l},
                     course=course)
                post_count += 1
    log("Created", post_count, "new overrides")
    log("Updated", put_count, "old overrides")
    
    log("Verifying assignments")
    assignments = get('assignments', all=True, course=course,
                      data={"include[]": ['overrides']})
    for assignment in assignments:
        aid = assignment['id']
        overrides = assignment['overrides']
        for override in overrides:
            log("{name} for {section}:\t{due_date},\t{lock_date},\t{open_date}"
                .format(name=assignment['name'], 
                        section=override['title'], 
                        due_date=override.get('due_at', 'None'), 
                        lock_date=override.get('lock_at', 'None'),
                        open_date=override.get('unlock_at', 'None')))
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create groups of students based on a list')
    parser.add_argument('--file', help='The path to a file of groups, where each group member is separated by commas and each group is separated by new lines.', default=None)
    parser.add_argument('--category', help='The category to assign to this group. If not given, all the categories available will be shown instead.', default=None)
    parser.add_argument('--course', '-c', help='The specific course to perform operations on. Should be a valid course label, not the ID')
    #parser.add_argument('--extensions', '-e', help='Include extensions for students (overrides).', action='store_true')
    parser.add_argument('--quiet', '-q', help='Silences the output', action='store_true', default=False)
    args = parser.parse_args()
    
    # Override default course
    if args.course:
        course = args.course
        if course not in courses:
            raise Exception("Unknown course name: {}".format(course))
    else:
        course = get_setting('course')
    
    # Handle quiet
    quiet = args.quiet

    # Handle the dates exporting
    if args.category is None:
        show_categories(course)
    else:
        make_groups(course, args.file, args.category)
