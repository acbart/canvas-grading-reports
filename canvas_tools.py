import json
import simplejson
import requests
import yaml
import os
import sys
import time
from datetime import datetime

try:
    from tqdm import tqdm
except:
    tqdm = None

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
    
def _canvas_request(verb, command, course, data, all, params, result=list,
                    estimated=None):
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
            if tqdm is not None and estimated is not None:
                pbar = tqdm(total=estimated/100)
            while True:
                if tqdm is not None and estimated is not None:
                    pbar.update(1)
                response = verb(next_url, data=data, params=params)
                if 'error' in response.json():
                    raise(Exception(response.text))
                if result == list:
                    final_result += response.json()
                elif result == dict:
                    final_result.append(response.json())
                else:
                    final_result = response
                if 'next' in response.links:
                    next_url = response.links['next']['url']
                else:
                    if tqdm is not None and estimated is not None:
                        pbar.close()
                    return final_result
        else:
            response = verb(next_url, data=data, params=params)
            if result == list:
                return response.json()
            elif result == dict:
                return [response.json()]
    except simplejson.decoder.JSONDecodeError:
        raise Exception("{}\n{}".format(response, next_url))
    
def get(command, course='default', data=None, all=False, params=None, result=list, estimated=None):
    return _canvas_request(requests.get, command, course, data, all, params, 
                           result=result, estimated=estimated)
    
def post(command, course='default', data=None, all=False, params=None, result=list, estimated=None):
    return _canvas_request(requests.post, command, course, data, all, params, 
                           result=result, estimated=estimated)
    
def put(command, course='default', data=None, all=False, params=None, result=list, estimated=None):
    return _canvas_request(requests.put, command, course, data, all, params, 
                           result=result, estimated=estimated)
    
def delete(command, course='default', data=None, all=False, params=None, result=list, estimated=None):
    return _canvas_request(requests.delete, command, course, data, all, params, 
                           result=result, estimated=estimated)

def progress_loop(progress_id, DELAY=3):
    while True:
        result = _canvas_request(requests.get, 'progress/{}'.format(progress_id), None, None, False, None, dict)[0]
        if result['workflow_state'] == 'completed':
            return True
        elif result['workflow_state'] == 'failed':
            return False
        else:
            print(result['workflow_state'], result['message'], str(int(round(result['completion']*10))/10)+"%")
            time.sleep(DELAY)
            
def download_file(url, destination):
    data = {'access_token': get_setting('canvas-token')}
    r = requests.get(url)
    f = open(destination, 'wb')
    for chunk in r.iter_content(chunk_size=512 * 1024): 
        if chunk: # filter out keep-alive new chunks
            f.write(chunk)
    f.close()

CANVAS_DATE_STRING = "%Y-%m-%dT%H:%M:%SZ"
def from_canvas_date(d1):
    return datetime.strptime(d1, CANVAS_DATE_STRING)

def to_canvas_date(d1):
    return d1.strftime(CANVAS_DATE_STRING)
