'''Module for classes and functions that fetch content from Leetcode.'''
import functools
import json
import logging
import time

import urllib.error
import urllib.request

import retry
import requests.compat


_BASE_URL = 'https://leetcode.com/api/'
_ALL_PROBLEMS_URL = requests.compat.urljoin(_BASE_URL, 'problems/all/')
_SUBMISSIONS_URL_FMT = requests.compat.urljoin(_BASE_URL, 'submissions/%s')
_FETCH_DELAY = 1


class LeetFetcher:
    '''Class for getting data from Leetcode using http requests.'''
    def __init__(self, cookies):
        self.cookies = cookies
        self.headers = {
                'User-Agent': 'LeetFS',
                'Cookie': self.cookies,
        }
        self.last_fetch = 0

    @functools.lru_cache
    @retry.retry(tries=10, delay=_FETCH_DELAY, backoff=2)
    def _fetch_url(self, url):
        logging.info('Fetching %s', url)
        cur_time = time.time()
        if cur_time - self.last_fetch < _FETCH_DELAY:
            time.sleep(_FETCH_DELAY)

        request = urllib.request.Request(url, headers=self.headers)
        self.last_fetch = time.time()
        with urllib.request.urlopen(request) as response:
            ans = response.read()
            return ans

    def fetch_problem_slugs(self):
        '''Fetches a list of problems solved by the user.'''
        all_problems = self._fetch_url(_ALL_PROBLEMS_URL)
        all_problem_data = json.loads(all_problems)
        logging.debug('user name: %s', all_problem_data['user_name'])
        if not all_problem_data['user_name']:
            logging.critical('Login failed')
            raise IOError('login failed')
        return [stat_data['stat']['question__title_slug']
                for stat_data in all_problem_data['stat_status_pairs']
                if  stat_data['status'] == 'ac']

    def fetch_submissions(self, slug):
        '''Fetches all submission for the sepcified problem.'''
        submission_data = self._fetch_url(_SUBMISSIONS_URL_FMT % slug)
        return json.loads(submission_data)['submissions_dump']

    def fetch_code(self, slug, submission_id):
        '''Fetches code for the given problem and submission id.'''
        submission_data = self.fetch_submissions(slug)
        for submission in submission_data:
            if submission['id'] == submission_id:
                return submission['code']
        return None
