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

from quiz_question_types import QUESTION_TYPES, DefaultQuestionType

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
        
def download_all_grades(course):
    enrollments = get('enrollments', course=course,
                      data={'type[]': 'StudentEnrollment',
                            'state[]': ['active','completed']},
                      all=True)
    return {str(e['user_id']): e['grades']['current_score']
            for e in enrollments}

#multiple_dropdowns_question
def download_quiz_report(quiz_id, course):
    return post('quizzes/{}/reports'.format(quiz_id),
                course=course,
                data={'quiz_report[report_type]': 'student_analysis',
                      'quiz_report[includes_all_versions]': True,
                      'include': ['file', 'progress']})

def download_quiz(quiz_id, format, filename, course, ignore):
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
    return process_quiz(quiz_id, format, path, course)

def download_all_quizzes(format, filename, course, ignore):
    quizzes = get('quizzes', all=True, course=course)
    return [download_quiz(quiz['id'], format, filename, course, ignore)
            for quiz in quizzes]
            
def process_quiz(quiz_id, format, path, course):
    print(quiz_id)
    # Download overall course grades for course-level discrimation
    course_scores = download_all_grades(course)
    # Process quiz data
    df = pd.read_csv(path, dtype=str)
    anonymous = 'id' not in df.columns
    FIRST_COLUMN = 5 if anonymous else 8
    # Grab out the actual columns of data
    df_submissions_subtable = df.iloc[:,FIRST_COLUMN:-3]
    attempts = df.iloc[:,FIRST_COLUMN-1].map(int)
    user_ids = None if anonymous else df.iloc[:,1]
    overall_score = df.iloc[:,-1].map(float)
    # Question IDs are stored in alternating columns as "ID: Text"
    question_ids = [x.split(':')[0] for x in
                    df_submissions_subtable.columns[::2]]
    for i, question_id in enumerate(question_ids):
        # Actual student submission is in alternating columns
        submissions = df_submissions_subtable.iloc[:, i*2]
        scores = df_submissions_subtable.iloc[:, 1+i*2]
        question = get('quizzes/{quiz}/questions/{qid}'
                       .format(quiz=quiz_id, qid=question_id),
                       course=course)
        question_type = question['question_type']
        processor = QUESTION_TYPES.get(question_type, DefaultQuestionType)
        q = processor(question, submissions, attempts, user_ids,
                      scores, overall_score, course_scores)
        q.analyze()
        if format == 'text':
            print(q.to_text().encode("ascii", errors='replace')
                  .decode())
        elif format == 'html':
            q.to_html()
        elif format == 'pdf':
            q.to_html()
        elif format == 'json':
            q.to_json()
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze quizzes')
    parser.add_argument('--course', '-c', help='The specific course to perform operations on. Should be a valid course label, not the ID')
    parser.add_argument('--id', '-i', help='The specific quiz ID to analyze. If not specified, all quizzes are used', default=None)
    parser.add_argument('--format', '-t', help='What format to generate the result into.', choices=['html', 'json', 'raw', 'pdf', 'text'], default='raw')
    parser.add_argument('--file', '-f', help='The path to the quiz folder. Otherwise, a default folder will be chosen based on the course name (For a course named CS1014, generate "quizzes/CS1014/").', default=None)
    parser.add_argument('--ignore', '-x', help='Ignores any cached files in processing the quiz results', action='store_true', default=False)
    parser.add_argument('--quiet', '-q', help='Silences the output', action='store_true', default=False)
    args = parser.parse_args()
    
    if not args.ignore:
        requests_cache.install_cache('quizzes_cache')
    
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
        successes = download_all_quizzes(args.format, args.file, 
                                         args.course, args.ignore)
        log("Finished", len(successes), "reports.")
        log(sum(map(bool, successes)), "were successful.")
    else:
        download_quiz(args.id, args.format, args.file, args.course,
                      args.ignore)
