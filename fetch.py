'''Fetches recent github activity and updates README.md'''

import os
import re
import time
import traceback
from datetime import datetime
from shutil import copy

import requests
from dateutil import parser

_USERNAME = os.environ['GH_USERNAME']
_EMAIL = os.environ['GH_EMAIL']
_AUTH_TOKEN = os.environ['GH_TOKEN']


_SLEEP_TIME = 0.5
_MAX_ITEMS = 10
_DATE_FORMAT = '%H:%M %d-%m-%Y'


_MAX_EVENTS = 25
_EVENT_DETAILS_MAX_LENGHT = 50

_GITHUB_SEARCH_API_MAX_RESULTS = 1000

_GITHUB_EVENTS_API_URL = 'https://api.github.com/users/{}/events/public'
_GITHUB_COMMITS_SEARCH_API_URL = 'https://api.github.com/search/commits'
_GITHUB_ISSUES_SEARCH_API_URL = 'https://api.github.com/search/issues'


_TIME_START_MARKER = '<!-- TIME STAMP START -->'
_TIME_END_MARKER = '<!-- TIME STAMP END -->'
_EVENTS_START_MARKER = '<!-- EVENTS START -->'
_EVENTS_END_MARKER = '<!-- EVENTS END -->'
_COMMITS_START_MARKER = '<!-- COMMITS START -->'
_COMMITS_END_MARKER = '<!-- COMMITS END -->'
_PULL_REQUESTS_START_MARKER = '<!-- PULL REQUESTS START -->'
_PULL_REQUESTS_END_MARKER = '<!-- PULL REQUESTS END -->'
_ISSUES_START_MARKER = '<!-- ISSUES START -->'
_ISSUES_END_MARKER = '<!-- ISSUES END -->'


_EVENTS_HEADERS = ['Recent Activity', 'Details', 'Time']
_COMMITS_HEADERS = ['Message', 'Repository', 'URL', 'Committed At']
_ISSUES_HEADERS = ['Title', 'Repository', 'URL', 'Last Updated', 'State']


_EVENTS_HEADERS_TO_KEYS = {
    'Recent Activity': 'activity',
    'Details': 'activity_details',
    'Time': 'activity_time'
}

_COMMITS_HEADERS_TO_KEYS = {
    'Message': 'message',
    'Repository': 'repository_name',
    'URL': 'commit_url',
    'Committed At': 'committed_at'
}
_ISSUES_HEADERS_TO_KEYS = {
    'Title': 'title',
    'Repository': 'repository_name',
    'URL': 'issue_url',
    'Last Updated': 'updated_at',
    'State': 'state'
}


def _sanitize_url(url):
    return url.replace('api.', '').replace('repos/', '')

class EventProcessor:
    _EVENT_PROCESSORS = {
        'IssuesEvent': '_process_issue_event',
        'IssueCommentEvent': '_process_issue_comment_event',
        'WatchEvent': '_process_watch_event',
        'PushEvent': '_process_push_event',
        'PullRequestEvent': '_process_pull_request_event',
        'PullRequestReviewEvent': '_process_pull_request_review_event',
        'PullRequestReviewCommentEvent':
            '_process_pull_request_review_comment_event',
        'ForkEvent': '_process_fork_event',
        'CreateEvent': '_process_create_event',
        'ReleaseEvent': '_process_release_event',
        'DeleteEvent': '_process_delete_event',
        'MemberEvent': '_process_member_event',
        'PublicEvent': '_process_public_event',
    }

    def __init__(self):
        pass

    def _process_issue_event(self, event):
        details = event['payload']['issue']['title']
        state = event['payload']['issue']['state']
        state = 'opened' if state == 'open' else 'closed'
        if not event['payload']['issue']['user']['login'] == _USERNAME:
            username = event['payload']['issue']['user']['login']
            username_hyperlink = _create_hyperlink(
                '@' + username,
                'https://github.com/{}'.format(username))
            activity = 'received an issue from {} [state={}]'.format(
                username_hyperlink, state)
            activity = '{} ' + activity
        else:
            activity = '{} an issue in '.format(state)
            activity += '{}'
        url = event['payload']['issue']['html_url']
        return details, activity, url

    def _process_issue_comment_event(self, event):
        details = event['payload']['comment']['body']
        activity = 'commented on an issue in {}'
        url = event['payload']['comment']['html_url']
        return details, activity, url

    def _process_watch_event(self, event):
        details = ''
        activity = 'starred {}'
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_push_event(self, event):
        details = '*'
        num_commits = len(event['payload']['commits'])
        branch = event['payload']['ref'].split('/')[-1]
        activity = 'pushed {} {} to {} in '.format(
            num_commits,
            'commits' if num_commits > 1 else 'commit',
            branch)
        activity += '{}'
        for commit in event['payload']['commits']:
            details += ' {} *'.format(commit['message'])
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_pull_request_event(self, event):
        details = event['payload']['pull_request']['title']
        state = event['payload']['pull_request']['state']
        activity = '{} a pull request in '.format(
            'opened' if state == 'open' else 'closed')
        activity += '{}'
        url = event['payload']['pull_request']['html_url']
        return details, activity, url

    def _process_member_event(self, event):
        details = ''
        username = event['payload']['member']['login']
        username_hyperlink = _create_hyperlink(
            '@' + username,
            'https://github.com/{}'.format(username))
        activity = 'added {} as a collaborator to '.format(username_hyperlink)
        activity += '{}'
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_create_event(self, event):
        details = ''
        if event['payload']['ref_type'] == 'repository':
            activity = 'created a new repository {}'
        else:
            activity = 'created a new branch {} in '.format(
                event['payload']['ref'])
            activity += '{}'
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_pull_request_review_event(self, event):
        details = event['payload']['pull_request']['title']
        activity = 'reviewed a pull request in {}'
        url = event['payload']['review']['html_url']
        return details, activity, url

    def _process_pull_request_review_comment_event(self, event):
        details = event['payload']['comment']['body']
        activity = 'commented on a pull request in {}'
        url = event['payload']['comment']['html_url']
        return details, activity, url

    def _process_release_event(self, event):
        details = ''
        activity = 'released tag {} for '.format(
            event['payload']['release']['tag_name'])
        activity += '{}'
        url = event['payload']['release']['html_url']
        return details, activity, url

    def _process_public_event(self, event):
        details = ''
        activity = 'made {} public'
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_delete_event(self, event):
        details = ''
        activity = 'deleted {}'
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_fork_event(self, event):
        details = ''
        activity = 'forked {}'
        url = _sanitize_url(event['repo']['url'])
        return details, activity, url

    def _process_event(self, event):
        if event['type'] in EventProcessor._EVENT_PROCESSORS:
            _fn = getattr(
                self,  EventProcessor._EVENT_PROCESSORS[event['type']])
            return _fn(event)
        return '', event['type'].lower(), _sanitize_url(event['repo']['url'])

    def process_event(self, event):
        details, activity, url = self._process_event(event)
        repository_name = event['repo']['name']
        repository_hyperlink = _create_hyperlink(
            repository_name, url)
        clipped_details = details[:_EVENT_DETAILS_MAX_LENGHT]
        if len(details) > _EVENT_DETAILS_MAX_LENGHT:
            clipped_details += '...'
        return {
            'event_type': event['type'],
            'activity': activity.format(repository_hyperlink),
            'activity_details': clipped_details,
            'activity_time': _normalize_date(event['created_at'])
        }


def _sanitize_table_entries(text):
    unsafe_chars = [r'`', r'|', r'\n', r'\r']
    for ch in unsafe_chars:
        text = re.sub(ch, '', text)
    return text


def _generate_table(items, num_rows, headers, headers_to_keys):
    num_rows = min(len(items), num_rows)
    if num_rows < 1:
        return ''

    table = [['|'] for _ in range(num_rows + 2)]
    for header in headers:
        table[0] += ' {} |'.format(header)
        table[1] += (' ' + '-' * len(header) + ' |')

    for i in range(num_rows):
        for header in headers:
            table[i + 2] += ' {} |'.format(_sanitize_table_entries(
                items[i][headers_to_keys[header]]))

    for i, row in enumerate(table):
        table[i] = ''.join(row)
    return table


def _get_events():
    print('Fetching events for {}'.format(_USERNAME))
    params = {
        'per_page': min(_MAX_EVENTS, 100)
    }
    headers = {'Accept': 'application/vnd.github.cloak-preview+json'}
    current_page = 1
    events = []
    while True:
        params['page'] = current_page
        response = requests.get(
            url=_GITHUB_EVENTS_API_URL.format(_USERNAME),
            params=params,
            headers=headers)
        results = response.json()
        events += [
            x for x in results if not x['repo']['name'] == '{}/{}'
            .format(_USERNAME, _USERNAME)]

        print('On Page: {} | Fetched {} events'.format(
            current_page, len(events)))

        current_page += 1
        if len(events) >= min(_MAX_EVENTS, _GITHUB_SEARCH_API_MAX_RESULTS):
            break
        time.sleep(_SLEEP_TIME)
    return _sanitize_events(events)


def _get_commits():
    print('Fetching commits for {}'.format(_USERNAME))
    params = {
        'q': 'author:{} is:public -repo:{}/{}'.format(
            _USERNAME, _USERNAME, _USERNAME),
        'sort': 'author-date',
        'order': 'desc',
        'per_page': min(_MAX_ITEMS, 100)
    }
    headers = {'Accept': 'application/vnd.github.cloak-preview+json'}
    current_page = 1
    commits = []
    while True:
        params['page'] = current_page
        response = requests.get(
            url=_GITHUB_COMMITS_SEARCH_API_URL,
            params=params,
            headers=headers,
            auth=(_USERNAME, _AUTH_TOKEN))
        results = response.json()
        commits += results['items']

        print('On Page: {} | Fetched {}/{} commits'.format(
            current_page, len(commits), results['total_count']))

        current_page += 1
        if (len(commits) == results['total_count'] or
                len(commits) >= min(
                    _MAX_ITEMS, _GITHUB_SEARCH_API_MAX_RESULTS)):
            break
        time.sleep(_SLEEP_TIME)
    return _sanitize_commits(commits)


def _get_issues(is_issue=False, is_pull_request=False):
    if is_issue:
        _type = 'issue'
    elif is_pull_request:
        _type = 'pr'
    else:
        raise ValueError(
            'Both `is_issue` and `is_pull_request` cannot be false')

    _type_normalized = _type.replace(
        'pr', 'pull requests').replace('issue', 'issues')
    print('Fetching {} for {}'.format(_type_normalized, _USERNAME))
    params = {
        'q': 'author:{} type:{} -repo:{}/{}'.format(
            _USERNAME, _type, _USERNAME, _USERNAME),
        'sort': 'created',
        'order': 'desc',
        'per_page': min(_MAX_ITEMS, 100)
    }

    current_page = 1
    issues = []
    while True:
        params['page'] = current_page
        response = requests.get(
            url=_GITHUB_ISSUES_SEARCH_API_URL, params=params)
        results = response.json()
        if 'items' not in results:
            print(results)
        issues += results['items']

        print('On Page: {} | Fetched {}/{} {}'.format(
            current_page, len(issues),
            results['total_count'], _type_normalized))

        current_page += 1
        if (len(issues) == results['total_count'] or
                len(issues) >= min(
                    _MAX_ITEMS, _GITHUB_SEARCH_API_MAX_RESULTS)):
            break
        time.sleep(_SLEEP_TIME)
    return _sanitize_issues(issues)


def _normalize_date(date, timezon='UTC'):
    return parser.parse(date).strftime(_DATE_FORMAT) + ' UTC'


def _create_hyperlink(text, link):
    return '[{}]({})'.format(text, link)


def _sanitize_events(events):
    print('Sanitizing {} events'.format(len(events)))
    sanitized_events = []
    processor = EventProcessor()
    for event in events:
        sanitized_events += [processor.process_event(event)]
    return sanitized_events


def _sanitize_commits(commits):
    print('Sanitizing {} commits'.format(len(commits)))
    sanitized_commits = []
    for commit in commits:
        repository_hyperlink = _create_hyperlink(
            commit['repository']['full_name'],
            commit['repository']['html_url'])

        commit_id = '/'.join(commit['html_url'].split('/')[-2:])[:14]
        commit_hyperlink = _create_hyperlink(commit_id, commit['html_url'])

        sanitized_commits += [{
            'message': commit['commit']['message'].replace('\n', ' '),
            'committed_at':
                _normalize_date(commit['commit']['author']['date']),
            'commit_url': commit_hyperlink,
            'repository_name': repository_hyperlink,
            'repository_url': commit['repository']['html_url'],
        }]
    return sanitized_commits


def _sanitize_issues(issues):
    print('Sanitizing {} issues/pull requests'.format(len(issues)))
    sanitized_issues = []
    for issue in issues:
        repository_url = _sanitize_url(issue['repository_url'])
        repository_name = repository_url.split('https://github.com/')[-1]
        repository_hyperlink = _create_hyperlink(
            repository_name, repository_url)

        issue_id = '/'.join(issue['html_url'].split('/')[-2:])
        issue_hyperlink = _create_hyperlink(issue_id, issue['html_url'])

        sanitized_issues += [{
            'title': issue['title'],
            'created_at': _normalize_date(issue['updated_at']),
            'updated_at': _normalize_date(issue['updated_at']),
            'issue_url': issue_hyperlink,
            'repository_name': repository_hyperlink,
            'repository_url': repository_url,
            'state': issue['state']
        }]
    return sanitized_issues


def _edit_readme(table, start_marker, end_marker, filename):
    with open(filename, 'r') as _fp:
        lines = [x.strip('\n') for x in _fp.readlines()]

    start_idx = lines.index(start_marker)
    stop_idx = lines.index(end_marker)
    num_old_issues_lines = stop_idx - start_idx - 1
    new_lines = [''] * (
        len(lines) + len(table) - num_old_issues_lines)

    new_lines[:start_idx + 1] = lines[:start_idx + 1]
    current_line_index = start_idx + 1

    for line in table:
        new_lines[current_line_index] = line
        current_line_index += 1
    new_lines[current_line_index] = end_marker
    current_line_index += 1

    for line in lines[stop_idx + 1:]:
        new_lines[current_line_index] = line
        current_line_index += 1

    with open(filename, 'w') as _fp:
        for i in range(len(new_lines) - 1):
            _fp.write(new_lines[i] + '\n')
        _fp.write(new_lines[-1])


def _get_current_time():
    current_time = _normalize_date(str(datetime.now()))
    return ['**Last Updated at : {}**'.format(current_time)]


if __name__ == '__main__':
    _edit_readme(
        table=_get_current_time(),
        start_marker=_TIME_START_MARKER,
        end_marker=_TIME_END_MARKER,
        filename='README.md')

    copy('README.md', 'temp.md')
    try:
        events_table = _generate_table(
            _get_events(),
            _MAX_EVENTS,
            _EVENTS_HEADERS,
            _EVENTS_HEADERS_TO_KEYS)
        comits_table = _generate_table(
            _get_commits(),
            _MAX_ITEMS,
            _COMMITS_HEADERS,
            _COMMITS_HEADERS_TO_KEYS)
        pull_requests_table = _generate_table(
            _get_issues(is_pull_request=True),
            _MAX_ITEMS,
            _ISSUES_HEADERS,
            _ISSUES_HEADERS_TO_KEYS)
        issues_table = _generate_table(
            _get_issues(is_issue=True),
            _MAX_ITEMS,
            _ISSUES_HEADERS,
            _ISSUES_HEADERS_TO_KEYS)

        _edit_readme(
            table=events_table,
            start_marker=_EVENTS_START_MARKER,
            end_marker=_EVENTS_END_MARKER,
            filename='README.md')

        _edit_readme(
            table=comits_table,
            start_marker=_COMMITS_START_MARKER,
            end_marker=_COMMITS_END_MARKER,
            filename='README.md')

        _edit_readme(
            table=pull_requests_table,
            start_marker=_PULL_REQUESTS_START_MARKER,
            end_marker=_PULL_REQUESTS_END_MARKER,
            filename='README.md')

        _edit_readme(
            table=issues_table,
            start_marker=_ISSUES_START_MARKER,
            end_marker=_ISSUES_END_MARKER,
            filename='README.md')

    except Exception as e:  # pylint: disable=broad-except
        print(str(e))
        print(traceback.format_exc())
        print('Undoing edits!!!!')
        copy('temp.md', 'README.md')
    os.remove('temp.md')
