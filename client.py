"""Read-only Maliaras API client; credentials and cookies stay in memory."""
import argparse
import json
import os
import re
import subprocess
from http.cookies import SimpleCookie

BASE = "https://erp.maliaras.gr"


def load_students(value=None):
    """Children come from MALIARAS_STUDENTS, e.g. "anna:Άννα,nikos:Νίκος" (key:display name)."""
    value = os.environ.get('MALIARAS_STUDENTS', '') if value is None else value
    students = {}
    for part in filter(None, (p.strip() for p in value.split(','))):
        key, _, name = part.partition(':')
        key, name = key.strip().lower(), name.strip()
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key) or not name:
            raise RuntimeError('MALIARAS_STUDENTS must look like "anna:Άννα,nikos:Νίκος" '
                               '(Latin lowercase key, colon, display name)')
        students[key] = {'name': name}
    return students


STUDENTS = load_students()
# The timetable is a read-only query the ERP UI sends as POST; nothing else may POST.
POST_PATHS = {'/api/auth/login', '/api/eclass/calculateSchedule'}


class Client:
    def __init__(self, student):
        if student not in STUDENTS:
            raise ValueError('Unknown student; choose one of: ' + ', '.join(STUDENTS)
                             + ' (configured in MALIARAS_STUDENTS)')
        self.student = student
        self.cookies = SimpleCookie()

    def _request(self, path, payload=None):
        if not path.startswith('/api/') or any(c in path for c in '\r\n?#'):
            raise ValueError('Only same-origin API paths are allowed')
        if payload is not None and path not in POST_PATHS:
            raise ValueError('Only login and timetable queries may use POST')
        config = [
            'url = ' + json.dumps(BASE + path),
            'header = "Accept: application/json"',
        ]
        if self.cookies:
            cookie = '; '.join(m.OutputString(attrs=[]) for m in self.cookies.values())
            config.append('header = ' + json.dumps('Cookie: ' + cookie))
        if payload is not None:
            config += ['header = "Content-Type: application/json"',
                       'data = ' + json.dumps(json.dumps(payload))]
        # stdin avoids exposing credentials/cookies in process arguments or files.
        result = subprocess.run(
            ['curl', '--silent', '--show-error', '--max-time', '30',
             '--proto', '=https', '--include', '--config', '-'],
            input='\n'.join(config), capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError('HTTPS request failed (details suppressed)')
        remaining = result.stdout.replace('\r\n', '\n')
        while True:
            headers, sep, body = remaining.partition('\n\n')
            if not sep or not headers.startswith('HTTP/'):
                raise RuntimeError('Unexpected HTTP response')
            status = int(headers.splitlines()[0].split()[1])
            for line in headers.splitlines()[1:]:
                if line.lower().startswith('set-cookie:'):
                    self.cookies.load(line.split(':', 1)[1].strip())
            if 100 <= status < 200 or (status == 200 and 'Connection established' in headers):
                remaining = body
                continue
            break
        if not 200 <= status < 300:
            raise RuntimeError(f'HTTP {status} from {path}; response body suppressed')
        try:
            return json.loads(body)
        except ValueError:
            raise RuntimeError('Expected JSON; response body suppressed') from None

    def login(self):
        prefix = f'MALIARAS_{self.student.upper()}'
        username = os.environ.get(f'{prefix}_USERNAME')
        password = os.environ.get(f'{prefix}_PASSWORD')
        if not username or not password:
            raise RuntimeError(f'Set {prefix}_USERNAME and {prefix}_PASSWORD in .env')
        return self._request('/api/auth/login', {
            'username': username, 'password': password,
        })

    def get(self, path):
        return self._request(path)

    def post(self, path, payload):
        return self._request(path, payload)


def shape(data):
    """Describe structure without printing student data or authentication values."""
    if isinstance(data, dict):
        return {'type': 'object', 'keys': sorted(data)}
    if isinstance(data, list):
        return {'type': 'array', 'count': len(data),
                'item': shape(data[0]) if data else None}
    return {'type': type(data).__name__}


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--student', choices=STUDENTS, help='Probe this account (structure only)')
        mode.add_argument('--list-students', action='store_true',
                          help='Print configured children (key -> name); no login, no secrets')
        args = parser.parse_args()
        if args.list_students:
            print(json.dumps({key: s['name'] for key, s in STUDENTS.items()}, ensure_ascii=False))
            raise SystemExit(0 if STUDENTS else 'MALIARAS_STUDENTS is empty; see .env.example')
        client = Client(args.student)
        user = client.login()
        print('Login successful:', json.dumps(shape(user)))
        print('Profile:', json.dumps(shape(client.get('/api/profile'))))
        year = client.get('/api/defaultYear')
        year_id = int(year['id'])
        print('School year:', year['name'])
        lessons = client.get(f'/api/eclass/mylessons/{year_id}')
        print('Lessons:', json.dumps(shape(lessons)))
        grades = client.get(f'/api/eclass/grades/getGradesInfo/{year_id}')
        print('Grades:', json.dumps(shape(grades)))
        if isinstance(lessons, list) and lessons:
            lesson_id = int(lessons[0]['id'])
            detail = client.get(f'/api/eclass/lesson_schedule/{lesson_id}')
            print('First lesson detail:', json.dumps(shape(detail)))
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
