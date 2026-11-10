from datetime import date
import unittest

from client import Client
from schedule import PERIOD_STARTS, build_week, period_end, select_days


def slot(lesson_id, name):
    return {'id': lesson_id, 'lesson': {'id': 1, 'name': name},
            'lesson_schedule_teachers': [{'teacher': {'name': 'secret'}}],
            'class': {'name': 'secret'}, 'lesson_schedule_day': {'room': {'name': 'secret'}}}


class ScheduleTests(unittest.TestCase):
    def test_projection_and_order(self):
        week = build_week({'2': {'1': {'lesson_schedules': [slot(7, 'ΓΛΩΣΣΑ')], 'office_hours': []}},
                           '1': {'2': {'lesson_schedules': [], 'office_hours': []},
                                 '1': {'lesson_schedules': [slot(8, 'ΜΑΘΗΜΑΤΙΚΑ')],
                                       'office_hours': []}}})
        self.assertEqual([d['day_name'] for d in week], ['Δευτέρα', 'Τρίτη'])
        self.assertEqual(week[0]['periods'], [{
            'period': 1, 'start': '08:30', 'end': '09:15', 'subject': 'ΜΑΘΗΜΑΤΙΚΑ',
            'source': 'https://erp.maliaras.gr/eclass/lesson/8'}])
        self.assertNotIn('secret', repr(week))

    def test_estimated_end_leaves_breaks(self):
        self.assertEqual([period_end(PERIOD_STARTS[p]) for p in (2, 4)], ['10:00', '11:45'])
        self.assertIsNone(period_end(None))

    def test_schema_failure_is_not_absence(self):
        for data in [None, [], {'9': {}}, {'1': {'1': {}}}, {'1': {'1': {'lesson_schedules': [{}]}}},
                     {'1': {'1': {'lesson_schedules': [{'id': 1, 'lesson': {'name': None}}]}}}]:
            with self.subTest(data=data), self.assertRaises(RuntimeError):
                build_week(data)

    def test_searched_day_and_next_lesson_day(self):
        week = [{'day': d, 'periods': [{'subject': str(d)}]} for d in range(1, 6)]
        tuesday = select_days(week, date(2026, 9, 29))
        self.assertEqual([d['date'] for d in tuesday], ['2026-09-29', '2026-09-30'])
        friday = select_days(week, date(2026, 10, 2))
        self.assertEqual([d['day_name'] for d in friday], ['Παρασκευή', 'Δευτέρα'])
        saturday = select_days(week, date(2026, 10, 3))
        self.assertEqual(saturday[0]['periods'], [])
        self.assertEqual(saturday[1]['date'], '2026-10-05')

    def test_post_is_allowlisted(self):
        with self.assertRaises(ValueError):
            Client('anna').post('/api/eclass/other', {})


if __name__ == '__main__':
    unittest.main()
