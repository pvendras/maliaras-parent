import unittest
from datetime import date
from unittest.mock import Mock

from announcements import fetch_announcements


class AnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.lessons = [{'id': 12, 'lesson': {'name': 'Γλώσσα'}}]
        self.client = Mock()

    def fetch(self, records, **kwargs):
        self.client.get.return_value = {'announcements': records, 'notes': ['private']}
        return fetch_announcements(self.client, self.lessons, **kwargs)

    def test_empty_and_source(self):
        result = self.fetch([])
        self.assertEqual(result['total_matching'], 0)
        self.assertFalse(result['truncated'])
        self.assertTrue(result['subjects_checked'][0]['source'].endswith('?tab=announcements'))
        self.client.get.assert_called_once_with('/api/eclass/lesson_schedule/12')

    def test_projection_and_athens_date(self):
        result = self.fetch([{'date': '2026-09-21T22:00:00Z', 'name': 'Title',
                              'description': '<p>Text</p>', 'teacher': {'private': 'secret'},
                              'files': ['secret']}], requested_date=date(2026, 9, 22))
        self.assertEqual(set(result['entries'][0]),
                         {'date', 'name', 'description', 'subject', 'source'})
        self.assertEqual(result['total_matching'], 1)

    def test_sort_limit_and_missing_date(self):
        records = [{'date': day, 'name': 'Title', 'description': None}
                   for day in [None, '2026-09-20', '2026-09-22']]
        result = self.fetch(records, limit=1)
        self.assertEqual(result['entries'][0]['date'], '2026-09-22')
        self.assertEqual(result['total_matching'], 3)
        self.assertTrue(result['truncated'])
        self.assertEqual(self.fetch(records, requested_date=date(2026, 9, 19))['entries'], [])

    def test_schema_failure_is_not_absence(self):
        for records in [None, {}, [None], [{'date': 'bad'}],
                        [{'date': '2026-09-22', 'name': {}, 'description': 'x'}]]:
            with self.subTest(records=records), self.assertRaises(RuntimeError):
                self.fetch(records)

    def test_accounts_are_not_accessed_by_fetch(self):
        self.fetch([])
        self.client.login.assert_not_called()


if __name__ == '__main__':
    unittest.main()
