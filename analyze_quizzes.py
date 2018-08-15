import json
import yaml
import os
import math
import requests
import requests_cache
import argparse
import re
import csv
import dateutil.parser
from datetime import datetime
from pprint import pprint
from collections import Counter, defaultdict
try:
    from tqdm import tqdm
except:
    print("TQDM is not installed. No progress bars will be available.")
    tqdm = list

import pandas as pd
import scipy as sp
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
    
from canvas_tools import get, post, put, delete, progress_loop
from canvas_tools import get_setting, courses, defaults, download_file
from canvas_tools import from_canvas_date, to_canvas_date
from canvas_tools import yaml_load

from html_tools import strip_tags, to_percent

def clean_name(filename):
    return "".join([c for c in filename
                    if c.isalpha() or c.isdigit() 
                       or c in (' ', '.')]).rstrip()

# Make sure they have a dates folder
if not os.path.exists('quizzes/'):
    os.mkdir('quizzes/')
    
quiet = True
def log(*args):
    if not quiet:
        print(*args)

#multiple_dropdowns_question
def download_quiz_report(quiz_id, course):
    return post('quizzes/{}/reports'.format(quiz_id),
                course=course,
                data={'quiz_report[report_type]': 'student_analysis',
                      'quiz_report[includes_all_versions]': True,
                      'include': ['file', 'progress']})

def download_quiz(quiz_id, type, filename, course, ignore):
    report = download_quiz_report(quiz_id, course)
    if 'errors' in report:
        log("Failure:", report['errors'])
        return False
    if 'file' not in report:
        pid = report['progress_url'].rsplit('/')[-1]
        success = progress_loop(pid)
        if success:
            report = download_quiz_report(quiz_id, course)
        else:
            log("Failure: Could not generate report for", quiz_id)
            return False
    title = report['file']['display_name']
    display_name = clean_name(title)
    if filename is None:
        path = 'quizzes/{}/'.format(course)
        os.makedirs(path, exist_ok=True)
        path += display_name
    download_file(report['file']['url'], path)
    print(title)

def download_all_quizzes(type, filename, course, ignore):
    quizzes = get('quizzes', all=True, course=course)
    return [download_quiz(quiz['id'], type, filename, course, ignore)
            for quiz in quizzes]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze quizzes')
    parser.add_argument('--course', '-c', help='The specific course to perform operations on. Should be a valid course label, not the ID')
    parser.add_argument('--id', '-i', help='The specific quiz ID to analyze. If not specified, all quizzes are used', default=None)
    parser.add_argument('--type', '-t', help='What format to generate the result into.', choices=['html', 'json', 'raw', 'pdf'], default='raw')
    parser.add_argument('--file', '-f', help='The path to the quiz folder. Otherwise, a default folder will be chosen based on the course name (For a course named CS1014, generate "quizzes/CS1014/").', default=None)
    parser.add_argument('--ignore', '-x', help='Ignores any cached files in processing the quiz results', action='store_true', default=False)
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
    if args.id is None:
        successes = download_all_quizzes(args.type, args.file, 
                                         args.course, args.ignore)
        log("Finished", len(success), "reports.")
        log(sum(successes), "were successful.")
    else:
        download_quiz(args.id, args.type, args.file, args.course,
                      args.ignore)
