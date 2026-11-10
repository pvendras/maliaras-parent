import unittest

from report_viber import render_viber


class ViberTests(unittest.TestCase):
    def report(self):
        return {'student_name': 'Άννα', 'date': '2026-11-10', 'school_year': '2026-2027',
                'retrieved_at': '2026-11-10T18:00:00+02:00', 'subjects': [
                    {'subject': 'ΓΛΩΣΣΑ', 'source': 'https://erp.maliaras.gr/eclass/lesson/1',
                     'entries': [{'name': 'Μάθημα', 'description': '<p>1) σελ. 48-49</p>',
                                  'fornextime': '<p>1) Ανάγνωση σελ. 48</p><script>bad()</script>'}]},
                    {'subject': 'ΑΓΓΛΙΚΑ', 'source': 'https://erp.maliaras.gr/eclass/lesson/2',
                     'entries': []}]}

    def days(self):
        period = {'period': 1, 'start': '08:30', 'end': '09:15', 'subject': 'ΓΛΩΣΣΑ'}
        return [{'date': '2026-11-10', 'day_name': 'Τρίτη', 'periods': [period]},
                {'date': '2026-11-11', 'day_name': 'Τετάρτη', 'periods': [period, dict(period, period=2)]}]

    def test_no_name_links_or_notes(self):
        text = render_viber(self.report(), self.days())
        self.assertNotIn('Άννα', text)
        self.assertNotIn('http', text)
        self.assertNotIn('Πηγές', text)
        self.assertNotIn('bad()', text)
        self.assertTrue(text.startswith('📋 *Αναφορά — Τρίτη 10/11*'))
        self.assertIn('• Ανάγνωση σελ. 48', text)
        self.assertIn('• σελ. 48-49', text)

    def test_ends_with_timetable_without_merging_periods(self):
        text = render_viber(self.report(), self.days())
        self.assertIn('_Τετάρτη 11/11_', text)
        self.assertEqual(text.count('📖 Γλώσσα'), 2 + 3)  # 2 sections + 3 periods
        self.assertTrue(text.endswith('2η 08:30–09:15 📖 Γλώσσα'))

    def test_no_records(self):
        self.assertIn('Δεν βρέθηκαν', render_viber(dict(self.report(), date=None), []))


if __name__ == '__main__':
    unittest.main()
