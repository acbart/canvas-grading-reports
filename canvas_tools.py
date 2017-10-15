import json
import requests
import yaml
import os
import sys
from datetime import datetime

SETTINGS_PATH = 'settings.yaml'
CACHE_PATH = 'cache.json'

settings = {
    'courses': {},
    'canvas-token': '',
    'defaults': {},
    'canvas-url': 'https://vt.instructure.com/api/v1/'
}

def yaml_load(path):
    with open(path) as settings_file:
        return yaml.load(settings_file)

# Create settings file if it doesn't exist
if not os.path.exists(SETTINGS_PATH):
    with open(SETTINGS_PATH, 'w') as settings_file:
        yaml.dump(settings, settings_file)
        print("A settings.yaml file was created. Please add your token and courses.")
        sys.exit()

# Load in the settings file
new_settings = yaml_load(SETTINGS_PATH)
settings.update(new_settings)

# Shortcut to access courses
courses = settings['courses']
defaults = settings['defaults']

def get_setting(setting, course=None):
    if course is None:
        return defaults[setting]
    if course in courses:
        if setting in courses[course]:
            return courses[course][setting]
        return defaults[setting]
    raise Exception("Course not found in settings.yaml: {course}".format(course=course))
    
def _canvas_request(verb, command, course, data, all, params):
    try:
        if data is None:
            data = {}
        if params is None:
            params = {}
        if course == 'default':
            course = get_setting('course')
        next_url = get_setting('canvas-url', course=course)
        if course != None:
            course_id = courses[course]['id']
            next_url += 'courses/{course_id}/'.format(course_id=course_id)
        next_url += command
        data['access_token'] = get_setting('canvas-token')
        if all:
            data['per_page'] = 100
            final_result = []
            while True:
                response = verb(next_url, data=data, params=params)
                final_result += response.json()
                if 'next' in response.links:
                    next_url = response.links['next']['url']
                else:
                    return final_result
        else:
            response = verb(next_url, data=data, params=params)
            return response.json()
    except json.decoder.JSONDecodeError:
        raise Exception("{}\n{}".format(response, next_url))
    
def get(command, course='default', data=None, all=False, params=None):
    return _canvas_request(requests.get, command, course, data, all, params)
    
def post(command, course='default', data=None, all=False, params=None):
    return _canvas_request(requests.post, command, course, data, all, params)
    
def put(command, course='default', data=None, all=False, params=None):
    return _canvas_request(requests.put, command, course, data, all, params)
    
def delete(command, course='default', data=None, all=False, params=None):
    return _canvas_request(requests.delete, command, course, data, all, params)


CANVAS_DATE_STRING = "%Y-%m-%dT%H:%M:%SZ"
def from_canvas_date(d1):
    return datetime.strptime(d1, CANVAS_DATE_STRING)

def to_canvas_date(d1):
    return d1.strftime(CANVAS_DATE_STRING)