import unittest

from report_format import formatted_lines
from report_md import render_report_md


class FormatTests(unittest.TestCase):
    def test_headings_numbers_and_bullets(self):
        self.assertEqual(list(formatted_lines(['ΤΙ ΝΑ ΦΕΡΟΥΝ:', '2) Βιβλίο', 'Φάκελος'])),
                         [('heading', 'ΤΙ ΝΑ ΦΕΡΟΥΝ:', None),
                          ('item', 'Βιβλίο', '2.'), ('item', 'Φάκελος', '•')])

    def test_nested_markdown(self):
        report = {'student_name': 'Άννα', 'date': '2026-09-14',
                  'school_year': '2026-2027', 'retrieved_at': '2026-09-14',
                  'subjects': [{'subject': 'ΓΛΩΣΣΑ',
                                'source': 'https://erp.maliaras.gr/eclass/lesson/123',
                                'entries': [{'fornextime': '<p>ΤΙ ΝΑ ΦΕΡΟΥΝ:</p>'
                                                           '<p>2) Βιβλίο</p><p>Φάκελος</p>'}]}]}
        text = render_report_md(report)
        self.assertIn('- **ΤΙ ΝΑ ΦΕΡΟΥΝ:**\n    - 2\\. Βιβλίο\n    - Φάκελος', text)
        self.assertIn('### 📖 ΓΛΩΣΣΑ', text)
