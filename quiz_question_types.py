from collections import defaultdict
from itertools import repeat
from math import isnan
from pprint import pprint
from textwrap import indent
from scipy.stats import pearsonr
import re

from html_tools import strip_tags, to_percent

def clean_text(text):
    return text.replace('\\', '')

def fill_nan_str(value):
    if isinstance(value, float) and isnan(value):
        return ''
    else:
        return str(value)

def split_on_commas(text):
    return re.split(r'(?<!\\),', text)

def sort_by_value_count(pair):
    value, (count, multiples, initials) = pair
    return value, -count

def sort_by_count(pair):
    value, (count, multiples, initials) = pair
    return -count
    
'''
% of students who chose it at some point
% of students who chose it on their initial submission
% of students who chose it on their final submission
'''

class QuizQuestionType:
    name = "Abstract Quiz Question Type"
    @staticmethod
    def key_occurrences(value):
        return sort_by_value_count(value)
    
    def __init__(self, question, submissions, attempts, user_ids,
                 submission_scores, quiz_scores, course_scores,
                 max_score, anonymous, path):
        # Critical Information
        self.question = question
        self.submissions = submissions
        self.attempts = attempts
        if user_ids is None:
            user_ids = ['Anon '+str(i) for i in 
                        range(len(submissions))]
        self.user_ids = user_ids
        self.uas = zip(user_ids, attempts, submissions)
        self.scores = list(zip(user_ids, attempts, submission_scores, 
                               quiz_scores))
        self.course_scores = course_scores
        self.max_score = max_score
        self.anonymous = anonymous
        self.path = path
        # Decorative information
        self.question_name = question['question_name']
        self.points_possible = question['points_possible']
        self.text = question['question_text']
        # Helper information
        self.total_submissions = len(submissions)
        self.total_students = len(set(user_ids))
        self.final_submission = {user_id: attempt
                                 for attempt, user_id
                                 in sorted(zip(attempts, user_ids))}
        # Calculated Information
        self.results = []
    
    def analyze(self):
        pass
    
    def to_json(self):
        quiz_disc, course_disc = self.calculate_discrimination()
        o_diff, i_diff, f_diff = self.calculate_difficulty()
        return {
            'question_name': self.question_name,
            'name': self.name,
            'path': self.path,
            'anonymous': self.anonymous,
            'points_possible': self.points_possible,
            'text': self.text,
            'discrimination': {
                'quiz': quiz_disc, 
                'course': course_disc
            },
            'difficulty': {
                'overall': o_diff,
                'initial': i_diff,
                'final': f_diff
            }
        }
    
    def to_text(self):
        body = [self.question_name, 
                "\t"+self.name,
                "\t"+str(self.points_possible)+" points", 
                indent(strip_tags(self.text.strip()), "\t")]
        body.append("\t---Discrimination---")
        quiz, course = self.calculate_discrimination()
        body.append("\tQuiz: {}".format(
            to_percent(quiz)
        ))
        body.append("\tCourse: {}".format(
            to_percent(course)
        ))
        o_diff, i_diff, f_diff = self.calculate_difficulty()
        if o_diff is not None:
            body.append("\t---Difficulty---")
            body.append("\tOverall: {}".format(to_percent(o_diff)))
            body.append("\tInitial: {}".format(to_percent(i_diff)))
            body.append("\tFinal: {}".format(to_percent(f_diff)))
        body.append("\t---Answers---")
        body.extend(self.to_text_answers())
        return "\n".join(body)
    
    def to_text_answers(self):
        body = []
        for answer, correct, o, i, f in self.results:
            body.append(""+"\t{},\t{},\t{}:{}\t".format(
                *map(to_percent, (o, i, f)),
                ('*' if correct else '')
            )+strip_tags(answer))
        return body
    
    def score_occurrences(self, occurrences, correctness):
        self.results = []
        sorted_occurrences = sorted(occurrences.items(),
                                    key=self.key_occurrences)
        self.quiz_discrimination = []
        self.course_discrimiation = []
        for key, (count, initials, finals) in sorted_occurrences:
            is_correct = correctness(key)
            o_score = count/self.total_submissions
            i_score = len(initials)/self.total_students
            f_score = len(finals)/self.total_students
            self.results.append(
                (key, is_correct, o_score, i_score, f_score)
            )
    
    def submission_keys(self, submission):
        '''
        Find all the possible subquestions and parts to this
        submission, generate keys in the occurrence dictionary
        for them.
        '''
        return [clean_text(submission)]
    
    def count_occurrences(self):
        occurrences = defaultdict(lambda: [0, set(), set()])
        for (user_id, attempt, submission) in self.uas:
            submission = fill_nan_str(submission)
            for key in self.submission_keys(submission):
                count, initials, finals = occurrences[key]
                occurrences[key][0] += 1
                if attempt == 1:
                    initials.add(user_id)
                if self.final_submission[user_id] == attempt:
                    finals.add(user_id)                
        return occurrences
    
    def calculate_discrimination(self):
        initial_quizzes = []
        initial_courses = []
        for user_id, attempt, submission, quiz in self.scores:
            if attempt == 1:
                initial_quizzes.append((submission, quiz))
                if user_id in self.course_scores:
                    course = self.course_scores[user_id]
                    initial_courses.append((submission, course))
        quiz, _ = pearsonr(*zip(*initial_quizzes))
        if initial_courses:
            course, _ = pearsonr(*zip(*initial_courses))
        else:
            course = float('nan')
        return quiz, course
    
    def calculate_difficulty(self):
        if not self.max_score:
            return 0, 0, 0
        total = 0
        initial = 0
        final = 0
        for user_id, attempt, submission, quiz in self.scores:
            total += submission
            if attempt == 1:
                initial += submission
            elif self.final_submission[user_id] == attempt:
                final += submission
        o_score = total/(self.total_submissions*self.max_score)
        i_score = initial/(self.total_students*self.max_score)
        f_score = final/(self.total_students*self.max_score)
        return o_score, i_score, f_score

class ShortAnswerQuestion(QuizQuestionType):
    name = "Short Answer Question"
    
    @staticmethod
    def key_occurrences(value):
        return sort_by_count(value)
    
    def analyze(self):
        occurrences = self.count_occurrences()
        def correctness(value):
            return value in (answer['text'] if answer['text']
                             else strip_tags(answer['html'])
                             for answer in self.question['answers'])
        self.score_occurrences(occurrences, correctness)
    
    def to_question(self):
        pass
        
class MatchingQuestions(QuizQuestionType):
    name = "Matching Question"
    
    def analyze(self):
        occurrences = self.count_occurrences()
        correct_answers = {answer['left']: answer['right']
                           for answer in self.question['answers']}
        def correctness(value):
            left, right = value
            # TODO: Fix this hack, why does it work?
            # Specific case was "True"
            if left not in correct_answers:
                left = '"{}"'.format(left)
            return right == correct_answers[left]
        self.score_occurrences(occurrences, correctness)
                
    def submission_keys(self, submission):
        for answer in split_on_commas(submission):
            if not answer:
                continue
            key, value = map(clean_text, answer.split("=>"))
            yield (key, value)
    
    def to_text_answers(self):
        body = []
        previous_label = None
        for (key, value), correct, o, i, f in self.results:
            if previous_label != key:
                body.append("\t"+key)
            body.append("\t\t{},\t{},\t{}:{}\t".format(
                *map(to_percent, (o, i, f)),
                ('*' if correct else '')
            )+strip_tags(value))
            previous_label = key
        return body

class FillInMultipleBlanks(QuizQuestionType):
    name = "Fill in Multiple Blanks"
    
    def submission_keys(self, submission):
        for label, answer in zip(self.labels, split_on_commas(submission)):
            label = clean_text(label)
            answer = clean_text(answer)
            yield (label, answer)
    
    def analyze(self):
        # Retrieve all possible answers
        possible_answers = defaultdict(list)
        self.labels = []
        for answer in self.question['answers']:
            blank_id = answer['blank_id']
            cleaned_text = clean_text(answer['text'])
            possible_answers[blank_id].append(cleaned_text)
            if blank_id not in self.labels:
                self.labels.append(blank_id)
        # Calculate occurrences of each possible answer
        occurrences = self.count_occurrences()
        def correctness(value):
            label, given = value
            return given in possible_answers[label]
        self.score_occurrences(occurrences, correctness)
    
    def to_text_answers(self):
        body = []
        previous_label = None
        for (label, answer), correct, o, i, f in self.results:
            if previous_label != label:
                body.append("\t"+label)
            body.append("\t\t{},\t{},\t{}:{}\t".format(
                *map(to_percent, (o, i, f)),
                ('*' if correct else '')
            )+strip_tags(answer))
            previous_label = label
        return body
    
class MultipleChoiceQuestion(QuizQuestionType):
    name = "Multiple Choice Question"
    
    def analyze(self):
        occurrences = self.count_occurrences()
        answers = [str(answer['text']) if answer['text']
                   else strip_tags(answer['html'])
                   for answer in self.question['answers']
                   if answer['weight']]
        def correctness(value):
            # TODO: Fix this hack, why does it work?
            # Specific case was "True"
            if value not in answers:
                value = '"{}"'.format(value)
            return value in answers
        self.score_occurrences(occurrences, correctness)

class MultipleAnswersQuestion(QuizQuestionType):
    name = "Multiple Answers Question"
    
    def submission_keys(self, submission):
        for answer in split_on_commas(submission):
            yield clean_text(answer)
    
    def analyze(self):
        occurrences = self.count_occurrences()
        answers = [str(answer['text']) if answer['text']
                   else strip_tags(answer['html'])
                   for answer in self.question['answers']
                   if answer['weight']]
        def correctness(value):
            return value in answers
        self.score_occurrences(occurrences, correctness)
    
        
class MultipleDropDownsQuestion(FillInMultipleBlanks):
    name = "Multiple Drop-Down Question"

class TrueFalseQuestion(MultipleChoiceQuestion):
    name = "True/False Questions"

class EssayQuestion(QuizQuestionType):
    name = "Essay Quesion"
    
    def analyze(self):
        self.results = list(self.submissions)
    
    def to_text(self):
        return self.name

class TextOnlyQuestion(QuizQuestionType):
    def analyze(self):
        self.results = []
    
    def to_text(self):
        return self.name
    
class DefaultQuestionType(QuizQuestionType):
    def calculate_difficulty(self):
        return 0,0,0
    def calculate_discrimination(self):
        return 0,0
    
    def analyze(self):
        self.results = []
    
    def to_text(self):
        return self.name

QUESTION_TYPES = {
    'fill_in_multiple_blanks_question': FillInMultipleBlanks,
    'matching_question': MatchingQuestions,
    'short_answer_question': ShortAnswerQuestion,
    'multiple_choice_question': MultipleChoiceQuestion,
    'multiple_answers_question': MultipleAnswersQuestion,
    'true_false_question': TrueFalseQuestion,
    'multiple_dropdowns_question': MultipleDropDownsQuestion,
    'essay_question': EssayQuestion,
    'text_only_question': TextOnlyQuestion,
}