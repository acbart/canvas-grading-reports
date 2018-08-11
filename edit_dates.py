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
if not os.path.exists('dates/'):
    os.mkdir('dates/')
    
quiet = True
def log(*args):
    if not quiet:
        print(*args)

def fix_timezone(time_str, new_tz='-05'):
    time_str = time_str.strip()
    if not time_str:
        return time_str
    elif time_str[-1].upper() == 'Z':
        return time_str[:-1]+new_tz
    else:
        return time_str
        
def to_iso8601(time_str, hour=11, minute=59):
    '''
    Should have been handled with a library, but here we are.
    '''
    if not isinstance(time_str, str):
        return ''
    if not time_str.strip():
        return ''
    if ':' in time_str:
        mmdd, hhii = time_str.strip().split()
        mm, dd, yy = mmdd.split("/")
        hh, ii = hhii.split(":")
        if ii.endswith("pm"):
            ii = int(ii[:2])
            hh = int(hh) + 12
        elif ii.endswith("am"):
            ii = int(ii[:2])
    else:
        mm, dd, yy = time_str.strip().split("/")
        hh, ii = 12+hour, minute
    yy, mm, dd, hh, ii = map(int, (yy, mm, dd, hh, ii))
    if yy <= 1000:
        yy = 2000+yy
    # TODO: Make this smarter
    dt = datetime(yy, mm, dd, hh, ii)
    if mm < 3 or (mm == 3 and dd < 11):
        dt+= timedelta(hours=1)
    dt+= timedelta(hours=4)
    yy, mm, dd, hh, ii = dt.year, dt.month, dt.day, dt.hour, dt.minute
    times = {'hh':hh, 'mm': mm, 'dd': dd, 'ii': ii, 'year': yy}
    return '{year}-{mm:02d}-{dd:02d}T{hh:02d}:{ii:02d}:00Z'.format(**times)

def export_dates(course, filename):
    # Assignments (including quizzes)
    assignments = get('assignments', all=True, course=course,
                      data={"include[]": ['overrides']})
    assignments = {a['id']: a for a in assignments}
    quiz_lookup = {a['quiz_id']: a['id']
                   for a in assignments.values() if 'quiz_id' in a}
    # Sections
    sections = get('sections', all=True, course=course)
    # Modules
    modules = get('modules', all=True, course=course)
    # Organize assignments by module
    latest_header = ''
    assignment_modules = []
    unseen = set(assignments.keys())
    for module in modules:
        new_module = {
            'module': module['id'],
            'name': module['name'],
            'assignments': []
        }
        MODULE_URL = 'modules/{}/items'.format(module['id'])
        module_items = get(MODULE_URL, all=True, course=course)
        for mi in module_items:
            assignment_ids = []
            if mi['type'] == 'Assignment':
                assignment_ids.append(mi['content_id'])
            elif mi['type'] == 'Quiz':
                if mi['content_id'] not in quiz_lookup:
                    continue
                assignment_ids.append(quiz_lookup[mi['content_id']])
            elif mi['type'] == 'SubHeader' and mi['indent'] == 0:
                latest_header = mi['title']
                continue
            else:
                continue
            for aid in assignment_ids:
                assignment = assignments[aid]
                assignment['_class_name'] = latest_header
                position = mi['position']
                new_module['assignments'].insert(position, assignment)
                unseen.remove(aid)
        assignment_modules.append(new_module)
    
    # Generate CSV
    section_names = ','.join(["{} ({}),,".format(s['name'],s['id']) for s in sections])
    section_headers = ', Open Date, Due Date, Lock Date' * (1+len(sections))
    if filename is None:
        filename = 'dates/'+str(course)+'_dates.csv'
    log("Writing to", filename)
    with open(filename, 'w') as out:
        out.write(",,,,"+section_names+"\n")
        out.write("Module, Class, Name, ID"+section_headers+"\n")
        # Print anything found in a module
        for m in assignment_modules:
            for a in m['assignments']:
                out.write('"{}",'.format(m['name']))
                out.write('"{}","{}",{}'.format(a['_class_name'], a['name'], a['id']))
                for s in sections:
                    out.write(",,,")
                    
                out.write("\n")
        # Print any unlisted assignments
        for u in natsorted(unseen, key=lambda u: assignments[u]['name']):
            out.write('"Unlisted",')
            out.write(',"{}",{}'.format(assignments[u]['name'], u))
            for s in sections:
                out.write(",,,")
            out.write("\n")

def extract_sections_from_header(header):
    sections = header[4::3]
    for section in sections:
        yield section[:-1].rsplit('(', maxsplit=1)

def fill_missing_times(times):
    while len(times) < 3:
        times.append('')
            
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
    parser = argparse.ArgumentParser(description='Manage dates for a canvas course')
    parser.add_argument('command', choices=['export', 'import', 'override', 'dst'],
                        help='Export will store the dates in a CSV, import will load them, and override will give extensions to individual students. DST will adjust all dates to be one hour greater or lesser depending on DST.')
    parser.add_argument('--course', '-c', help='The specific course to perform operations on. Should be a valid course label, not the ID')
    parser.add_argument('--file', '-f', help='The path to a file. Otherwise, a default filename will be chosen based on the course name (For a course named CS1014, generate "dates/CS1014_dates.csv").', default=None)
    #parser.add_argument('--extensions', '-e', help='Include extensions for students (overrides).', action='store_true')
    parser.add_argument('vars', nargs='*')
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
    if args.command == "export":
        export_dates(course, args.file)
    elif args.command == "import":
        import_dates(course, args.file)
    