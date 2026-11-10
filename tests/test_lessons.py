import contextlib
from datetime import date, datetime
import io
import json
import unittest
from unittest.mock import patch

import lessons


class LessonTests(unittest.TestCase):
    @patch('report_pdf.write_report_pdf', return_value='/tmp/nikos-report.pdf')
    @patch('lessons.Client')
    def test_pdf_command(self, client_class, render):
        client_class.return_value.get.side_effect = [
            {'id': 1, 'name': '2026-2027'},
            [{'id': 10, 'lesson': {'name': 'ΜΟΥΣΙΚΗ'}}],
            {'lessons': [{'date': '2026-09-11', 'description': 'Μάθημα'}]},
        ]
        with patch('sys.argv', ['lessons.py', '--student', 'nikos', '--report',
                                '--date', '2026-09-11', '--pdf']), contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(lessons.main(), 0)
        data = json.loads(stream.getvalue())
        self.assertEqual(data['pdf'], '/tmp/nikos-report.pdf')
        client_class.assert_called_once_with('nikos')
        self.assertEqual(render.call_args.args[0]['student_name'], 'Νίκος')
        self.assertEqual(render.call_args.args[1].name, 'nikos-report-2026-09-11.pdf')

    def test_student_required(self):
        with patch('lessons.Client') as client, patch('sys.argv', ['lessons.py', '--report']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                lessons.main()
            client.assert_not_called()

    def test_account_selection(self):
        from client import Client, STUDENTS
        a, b = Client('anna'), Client('nikos')
        self.assertIsNot(a.cookies, b.cookies)
        with self.assertRaises(ValueError):
            Client('unknown')
        for student in STUDENTS:
            prefix = f'MALIARAS_{student.upper()}'
            env = {f'{prefix}_USERNAME': f'user-{student}', f'{prefix}_PASSWORD': 'secret'}
            with patch.dict('os.environ', env), patch.object(Client, '_request') as request:
                Client(student).login()
                request.assert_called_once_with('/api/auth/login', {
                    'username': f'user-{student}', 'password': 'secret'})

    def test_students_config(self):
        from client import load_students
        self.assertEqual(load_students(' anna:Άννα , nikos:Νίκος '),
                         {'anna': {'name': 'Άννα'}, 'nikos': {'name': 'Νίκος'}})
        self.assertEqual(load_students(''), {})
        for bad in ('Άννα', 'anna', 'Anna Maria:Άννα', '1anna:Άννα'):
            with self.assertRaises(RuntimeError):
                load_students(bad)

    def test_login_requires_both_credentials(self):
        from client import Client
        for env in ({}, {'MALIARAS_ANNA_USERNAME': 'user'}, {'MALIARAS_ANNA_PASSWORD': 'pw'}):
            with patch.dict('os.environ', env, clear=True), \
                    patch.object(Client, '_request') as request:
                with self.assertRaisesRegex(RuntimeError, 'MALIARAS_ANNA_USERNAME'):
                    Client('anna').login()
                request.assert_not_called()

    def test_calendar_days(self):
        for value in ('2026-09-11', '2026-09-10T21:30:00Z',
                      '2026-09-11T00:30:00', '2026-09-11T00:30:00+03:00'):
            self.assertEqual(lessons.entry_day(value), date(2026, 9, 11))
        self.assertEqual(lessons.entry_day('2026-09-11T22:00:00Z'), date(2026, 9, 12))
        self.assertEqual(lessons.entry_day('2026-01-10T22:30:00Z'), date(2026, 1, 11))
        self.assertIsNone(lessons.entry_day(None))
        with self.assertRaises(RuntimeError):
            lessons.entry_day('bad date')

    def run_helper(self, args):
        output = io.StringIO()
        with patch('sys.argv', ['lessons.py', '--student', 'anna', *args]), contextlib.redirect_stdout(output):
            result = lessons.main()
        return result, json.loads(output.getvalue())

    @patch('lessons.Client')
    def test_all_filters_and_logs_in_once(self, client_class):
        client = client_class.return_value
        client.get.side_effect = [
            {'id': 1, 'name': '2026-2027'},
            [{'id': 10, 'lesson': {'name': 'ΓΛΩΣΣΑ'}},
             {'id': 20, 'lesson': {'name': 'ΜΟΥΣΙΚΗ'}}],
            {'lessons': [
                {'date': '2026-09-11', 'description': 'Selected', 'private': 'hidden'},
                {'date': '2026-09-12', 'description': 'Unrelated'},
                {'date': None, 'description': 'Undated'}]},
            {'lessons': []},
        ]
        result, data = self.run_helper(['--all', '--date', '2026-09-11'])
        self.assertEqual(result, 0)
        client.login.assert_called_once_with()
        client_class.assert_called_once_with('anna')
        self.assertEqual(data['student'], 'anna')
        self.assertEqual(client.get.call_count, 4)
        self.assertEqual(data['date'], '2026-09-11')
        self.assertEqual(data['subjects'][0]['entries'],
                         [{'date': '2026-09-11', 'description': 'Selected'}])
        self.assertEqual(data['subjects'][0]['source'], 'https://erp.maliaras.gr/eclass/lesson/10')
        self.assertEqual(data['subjects'][1]['entries'], [])

    @patch('lessons.Client')
    def test_single_subject_compatibility(self, client_class):
        client_class.return_value.get.side_effect = [
            {'id': 1, 'name': '2026-2027'},
            [{'id': 10, 'lesson': {'name': 'ΓΛΩΣΣΑ'}}],
            {'lessons': [{'date': '2026-09-10'}, {'date': '2026-09-11'}]},
        ]
        _, data = self.run_helper(['--subject', 'γλώσσα'])
        self.assertEqual(data['subject'], 'ΓΛΩΣΣΑ')
        self.assertEqual(len(data['entries']), 2)
        self.assertEqual(data['entries'][0]['date'], '2026-09-11')

    def test_report_latest_day(self):
        subjects = [
            {'subject': 'A', 'source': 'a', 'entries': [
                {'date': '2026-09-10T21:30:00Z'},
                {'date': '2026-09-15'}, {'date': None}]},
            {'subject': 'B', 'source': 'b', 'entries': [{'date': '2026-09-10'}]},
        ]
        data = lessons.report_subjects(subjects, None, date(2026, 9, 14))
        self.assertEqual(data['date'], '2026-09-11')
        self.assertTrue(data['has_entries'])
        self.assertEqual(len(data['subjects'][0]['entries']), 1)
        self.assertEqual(data['subjects'][1]['entries'], [])
        self.assertEqual(len(subjects[0]['entries']), 3)

    def test_report_empty_and_explicit_date(self):
        subjects = [{'subject': 'A', 'entries': [{'date': '2026-09-15'}, {'date': None}]}]
        data = lessons.report_subjects(subjects, None, date(2026, 9, 14))
        self.assertIsNone(data['date'])
        self.assertFalse(data['has_entries'])
        data = lessons.report_subjects(subjects, date(2026, 9, 11), date(2026, 9, 14))
        self.assertEqual(data['date'], '2026-09-11')
        self.assertFalse(data['has_entries'])
        self.assertFalse(lessons.report_subjects([], None, date.today())['has_entries'])

    @patch('lessons.Client')
    def test_report_command(self, client_class):
        for args in (['--report'], ['--report', '--date', '2026-09-11']):
            client = client_class.return_value
            client.reset_mock()
            client.get.side_effect = [
                {'id': 1, 'name': '2026-2027'},
                [{'id': 10, 'lesson': {'name': 'ΓΛΩΣΣΑ'}}],
                {'lessons': [{'date': '2026-09-11', 'fornextime': 'Work', 'private': 'hidden'}]},
            ]
            with patch('lessons.datetime') as clock:
                clock.now.return_value = datetime.fromisoformat('2026-09-14T12:00:00+03:00')
                clock.fromisoformat.side_effect = datetime.fromisoformat
                result, data = self.run_helper(args)
            self.assertEqual(result, 0)
            self.assertEqual(data['mode'], 'report')
            self.assertEqual(data['date'], '2026-09-11')
            self.assertEqual(data['subjects'][0]['entries'],
                             [{'date': '2026-09-11', 'fornextime': 'Work'}])
            client.login.assert_called_once_with()
            self.assertEqual(client.get.call_count, 3)

    @patch('lessons.Client')
    def test_invalid_arguments_never_authenticate(self, client_class):
        for args in ([], ['--all'], ['--list', '--pdf'], ['--list', '--date', '2026-09-11'],
                     ['--all', '--subject', 'Γλώσσα'],
                     ['--all', '--date', '2026-02-30']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.run_helper(args)
        client_class.assert_not_called()


if __name__ == '__main__':
    unittest.main()
