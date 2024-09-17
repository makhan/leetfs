'''A barebones FUSE filesystem to browse accepted Leetcode submissions.'''
import argparse
import collections
import errno
import logging
import os
import stat
import time

from fuse import FUSE, FuseOSError, Operations

import leetfetcher
import submission_state


_FILE_EXT_FROM_TYPE = {
        'bash': '.sh',
        'csharp': '.cs',
        'c': '.c',
        'cpp': '.cc',
        'dart': '.dart',
        'elixir': '.ex',
        'erlang': '.erl',
        'golang': '.go',
        'java': '.java',
        'javascript': '.js',
        'kotlin': '.kt',
        'php': '.php',
        'python': '.py',
        'python3': '.py',
        'racket': '.rkt',
        'ruby': '.rb',
        'rust': '.rs',
        'scala': '.scala',
        'sql': '.sql',
        'swift': '.swift',
}

_POLL_DELAY_SECS = 2 * 60 * 60 # 2 hour
_SUBMISSIONS_FILE = 'submissions.json'
_COOKIES_FILE = 'cookie.txt'


class IdGenerator:
    '''A simple unique Id generator.'''
    def __init__(self, start=0):
        self.next_available = start
        self.recycle_bin = collections.deque()

    def next(self):
        '''Gets the next available unique Id.'''
        if self.recycle_bin:
            return self.recycle_bin.popleft()
        self.next_available += 1
        return self.next_available - 1

    def free(self, value):
        '''Frees up the given Id for re-use.'''
        self.recycle_bin.append(value)


def is_valid_slug(slug):
    '''Checks that slug makes sense.'''
    return all(c.isalnum() or c == '-' for c in slug)


class LeetFS(Operations):
    '''FUSE file system class.'''

    def __init__(self, submissions):
        self.start_time = int(time.time())
        self.id_generator = IdGenerator()
        self.open_fd ={}
        self.problem_submissions = submissions
        self.timer = None


    def access(self, path, amode):
        logging.info('access %s %d', path, amode)
        return False

    def getattr(self, path, fh=None):
        logging.info('getattr %s', path)
        components = path.split('/')[1:]
        logging.info(components)
        st = {
                'st_atime': self.start_time,
                'st_ctime': self.start_time,
                'st_mtime': self.start_time,
                'st_gid': os.getgid(),
                'st_uid': os.getuid(),
                'st_mode': stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
                'st_size': 4096,
                'st_nlink': 2,
        }
        if path == '/':
            st['st_mode'] |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IFDIR
        elif len(components) > 2:
            logging.warn('Invalid path %s', path)
            raise FuseOSError(errno.EEXIST)
        elif len(components) == 1:
            slug = components[0]
            if not is_valid_slug(slug):
                logging.warn('Invalid slug: %s', slug)
                raise FuseOSError(errno.EEXIST)
            logging.debug('slug: %s', slug)
            st['st_mode'] |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IFDIR
            submissions = self.problem_submissions[slug]
            st['st_size'] = sum(len(submission['code'].encode()) for submission in submissions)
            st['st_ctime'] = min(submission['timestamp'] for submission in submissions)
            st['st_mtime'] = max(submission['timestamp'] for submission in submissions)
        elif len(components) == 2:
            slug = components[0]
            file_name = components[1]
            if '.' not in file_name or not is_valid_slug(file_name[:file_name.index('.')]):
                logging.error('Invalid slug for file: %s', file_name)
                raise FuseOSError(errno.EEXIST)
            submission_id = int(file_name[:file_name.index('.')])
            submissions = self.problem_submissions[slug]
            if not submissions:
                logging.error('No slug found : %s', slug)
                raise FuseOSError(errno.EEXIST)

            submission = [s for s in submissions if s['id'] == submission_id][0]

            st['st_mode'] |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IFREG
            st['st_size'] = len(submission['code'].encode())
            st['st_ctime'] = submission['timestamp']
            st['st_mtime'] = submission['timestamp']
        logging.info('status: %s', repr(st))
        return st


    def readdir(self, path, fh=None):
        logging.info('readdir %s', path)
        directory_entries = ['.', '..']
        if path == '/':
            directory_entries.extend(self.problem_submissions.keys())
        else:
            if path.startswith('/'):
                path = path[1:]
            components = path.split('/')
            if len(components) == 1:
                slug = components[0]
                submissions = self.problem_submissions[slug]
                if not submissions:
                    logging.error('No slug found : %s', slug)
                    raise FuseOSError(errno.EEXIST)
                for submission in submissions:
                    submission_id = submission['id']
                    extension = _FILE_EXT_FROM_TYPE.get(submission['lang'], '.txt')
                    directory_entries.append(f'{submission_id}{extension}')
        yield from directory_entries

    def statfs(self, path):
        # This is total nonsense
        logging.info('statvfs %s', path)
        stv = os.statvfs('/home')
        return dict(
                (key, getattr(stv, key)) for key in (
                    'f_bavail', 'f_bfree', 'f_blocks', 'f_bsize', 'f_favail',
                    'f_ffree', 'f_files', 'f_flag', 'f_frsize', 'f_namemax'))

    # File methods:

    def open(self, path, flags):
        logging.info('open %s %d', path, flags)

        if path == '/':
            raise FuseOSError(errno.EISDIR)
        if path.startswith('/'):
            path = path[1:]
        components = path.split('/')
        if len(components) != 2:
            raise FuseOSError(errno.EISDIR)

        file_name = components[-1]
        submission_id = int(file_name[:file_name.index('.')])
        logging.info('submission_id: %d', submission_id)
        submissions = self.problem_submissions[components[0]]
        if not submissions:
            logging.error('No submissions found')
            raise FuseOSError(errno.EEXIST)
        relevant_submission = [
                submission
                for submission in submissions
                if submission['id'] == submission_id][0]

        code = relevant_submission['code'].encode()
        fd = self.id_generator.next()
        self.open_fd[fd] = code
        return fd

    def read(self, path, size, offset, fh):
        logging.info('read %s %d %d %d', path, size, offset, fh)
        code = self.open_fd[fh]
        logging.info(code)
        logging.info(code[offset:offset+size])
        return code[offset:offset+size]

    def release(self, path, fh):
        logging.info('release %s %d', path, fh)
        del self.open_fd[fh]
        self.id_generator.free(fh)
        return 0



def main():
    '''Program entry point.'''
    argparser = argparse.ArgumentParser(
            description='An in-memory filesystem for LeetCode submissions')
    argparser.add_argument('--cookies_file', default=_COOKIES_FILE)
    argparser.add_argument('--submissions_file', default=_SUBMISSIONS_FILE)
    argparser.add_argument('--poll_delay_secs', default=_POLL_DELAY_SECS)
    argparser.add_argument('--mount_point', required=True)
    argparser.add_argument(
            '--log_level',
            choices=['critical', 'error', 'warn', 'info', 'debug'],
            default='warn',
            help='Provide a logging level')
    parsed_args = argparser.parse_args()
    logging.basicConfig(format='[%(asctime)s] - <%(levelname)s>: %(message)s', level=parsed_args.log_level.upper())

    with open(parsed_args.cookies_file, 'r', encoding='utf-8') as cookie:
        try:
            fetcher = leetfetcher.LeetFetcher(cookie.read().strip())
            if not os.path.isfile(parsed_args.submissions_file):
                with open(_SUBMISSIONS_FILE, 'w', encoding='utf-8') as submissions_file:
                    submissions_file.write('[]')
            submissions = submission_state.SubmissionState(
                    fetcher, parsed_args.submissions_file, parsed_args.poll_delay_secs)
            submissions.load_file()
            submissions.start_polling()
            FUSE(LeetFS(submissions), parsed_args.mount_point, nothreads=True, foreground=True)
        finally:
            submissions.dump_file()
            submissions.stop_polling()



if __name__ == '__main__':
    main()
