from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sync_exports import export_day, sync_student


class SyncTests(unittest.TestCase):
    def report(self):
        return {'student': 'anna', 'student_name': 'Άννα', 'date': '2026-09-18',
                'school_year': '2026-2027', 'retrieved_at': 'first',
                'subjects': [{'subject': 'Γλώσσα', 'source': 'https://erp.maliaras.gr/eclass/lesson/1',
                              'entries': [{'description': 'Lesson', 'fornextime': 'Work'}]}]}

    @patch('sync_exports.write_report_pdf')
    def test_skip_revision_and_missing_file(self, pdf):
        def fake(report, destination):
            Path(destination).write_bytes(b'test PDF')
            return str(destination)
        pdf.side_effect = fake
        with tempfile.TemporaryDirectory() as directory:
            report = self.report()
            first = export_day(report, directory)
            self.assertEqual(first['status'], 'exported')
            report['retrieved_at'] = 'second'
            self.assertEqual(export_day(report, directory)['status'], 'unchanged')
            report['subjects'][0]['entries'][0]['fornextime'] = 'New work'
            second = export_day(report, directory)
            self.assertTrue(second['md'].endswith('-v2.md'))
            self.assertTrue(Path(first['md']).exists())
            Path(second['pdf']).unlink()
            self.assertEqual(export_day(report, directory)['status'], 'exported')

    @patch('sync_exports.export_day')
    @patch('sync_exports.Client')
    def test_only_recorded_past_days_single_login(self, client_class, export):
        client = client_class.return_value
        client.get.side_effect = [{'id': 1, 'name': '2026-2027'},
                                 [{'id': 5, 'lesson': {'name': 'Γλώσσα'}}],
                                 {'lessons': [{'date': '2020-01-01'}, {'date': None},
                                              {'date': '2999-01-01'}]}]
        sync_student('nikos', Path('/unused'))
        client_class.assert_called_once_with('nikos')
        client.login.assert_called_once_with()
        self.assertEqual(export.call_count, 1)
        self.assertEqual(export.call_args.args[0]['date'], '2020-01-01')
