import functools
import json
import logging
import pprint
import requests.compat
import urllib.error
import urllib.request


_BASE_URL = 'https://leetcode.com/api/'
_ALL_PROBLEMS_URL = requests.compat.urljoin(_BASE_URL, 'problems/all/')
_SUBMISSIONS_URL_FMT = requests.compat.urljoin(_BASE_URL, 'submissions/%s')


class LeetFetcher:
    def __init__(self, cookies):
        self.cookies = cookies
        self.headers = {
                'User-Agent': 'LeetFS',
                'Cookie': self.cookies,
        }

    @functools.lru_cache
    def _fetchUrl(self, url):
        logging.info('Fetching %s', url)
        request = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(request) as response:
            return response.read()

    def fetchProblemSlugs(self):
        all_problems = self._fetchUrl(_ALL_PROBLEMS_URL)
        all_problem_data = json.loads(all_problems)
        return [stat_data['stat']['question__title_slug'] for stat_data in all_problem_data['stat_status_pairs'] if  stat_data['status'] == 'ac']

    def fetchSubmissions(self, slug):
        submission_data = self._fetchUrl(_SUBMISSIONS_URL_FMT % slug)
        return json.loads(submission_data)['submissions_dump']

    def fetchCode(self, slug, submission_id):
        submission_data = self.fetchSubmissions(slug)
        for submission in submission_data:
            if submission['id'] == submission_id:
                return submission['code']
        return None


def main():

    with open('cookie.txt') as cookie:
        fetcher = LeetFetcher(cookie.read().strip())
        slugs = fetcher.fetchProblemSlugs()
        for problem in slugs:
            pprint.pprint(problem)
        pprint.pprint(fetcher.fetchSubmissions(slugs[0]))
        pprint.pprint(fetcher.fetchCode(slugs[0], 1343707442))
    

if __name__ == '__main__':
    main()
