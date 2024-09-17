import collections
import json
import logging
import threading
import time


class SubmissionState:

    def __init__(self, fetcher, json_file, poll_delay_secs):
        self.fetcher = fetcher
        self.problem_submissions = collections.defaultdict(list)
        self.json_file = json_file
        self.poll_delay_secs = poll_delay_secs
        self.last_fetched_id = 0
        self.timer = None

    def _load_data(self):
        logging.info('*** Setting Timer.')
        self.timer = threading.Timer(self.poll_delay_secs, self._load_data)
        self.timer.daemon = True
        self.timer.start()

        logging.info('*** Loading data...')
        submissions_dump = self.fetcher.fetch_all_submissions(self.last_fetched_id)
        if submissions_dump:
            self.last_fetched_id = max(submission['id'] for submission in submissions_dump)

            for submission in submissions_dump:
                if submission['status_display'] == 'Accepted':
                    self.problem_submissions[submission['title_slug']].append(submission)
        logging.info('*** Done loading data')

    def start_polling(self):
        if not self.timer:
            self._load_data()

    def stop_polling(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def dump_file(self):
        logging.info('writing to file %s', self.json_file)
        with open(self.json_file, 'w', encoding='utf-8') as outfile:
            outfile.write(json.dumps(self.problem_submissions))

    def load_file(self):
        logging.info('reading from file %s', self.json_file)
        with open(self.json_file, 'r', encoding='utf-8') as infile:
            self.problem_submissions.update(json.loads(infile.read()))
            for submission_list in self.problem_submissions.values():
                self.last_fetched_id = max(self.last_fetched_id, max(submission['id'] for submission in submission_list))


    def __getitem__(self, key):
        return self.problem_submissions[key]

    def __setitem__(self, key, value):
        self.problem_submissions[key] = value

    def keys(self):
        return self.problem_submissions.keys()
