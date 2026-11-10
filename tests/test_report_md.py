from pathlib import Path
import tempfile
import unittest

from report_md import render_report_md, strip_emojis, write_report_md


class MarkdownTests(unittest.TestCase):
    def report(self):
        return {'student_name': 'Άννα', 'date': '2026-09-14', 'school_year': '2026-2027',
                'retrieved_at': '2026-09-14T19:00:00+03:00', 'subjects': [
                    {'subject': 'ΓΛΩΣΣΑ', 'source': 'https://erp.maliaras.gr/eclass/lesson/123',
                     'entries': [{'name': 'Μάθημα', 'description': '<p>σελ. 6-7</p>',
                                  'fornextime': '<p>Φέρνω βιβλίο</p><script>bad()</script>'
                                                 '<p>[click](https://example.com)</p>',
                                  'nextdate': '2026-09-15'}]}]}

    def test_render_and_safety(self):
        text = render_report_md(self.report())
        self.assertIn('Άννα', text)
        self.assertIn('σελ. 6-7'.replace('.', r'\.').replace('-', r'\-'), text)
        self.assertIn('Φέρνω βιβλίο', text)
        self.assertNotIn('bad()', text)
        self.assertNotIn('[click](', text)
        self.assertIn('[ΓΛΩΣΣΑ](https://erp.maliaras.gr/eclass/lesson/123)', text)
        self.assertIn('Επόμενο μάθημα', text)

    def test_emojis_are_decoration_only(self):
        report = self.report()
        report['subjects'].append({'subject': 'ΝΕΟ ΜΑΘΗΜΑ', 'source': 'x', 'entries': [
            {'name': '', 'description': '', 'fornextime': ''}]})
        text = render_report_md(report)
        for heading in ('# 📋 Αναφορά', '## 🎒 Για το σπίτι', '## 📝 Τι έκαναν', '### 📖 ΓΛΩΣΣΑ',
                        '### 📘 ΝΕΟ', '## 🔗 Πηγές', '📅 **Επόμενο'):
            self.assertIn(heading, text)
        plain = strip_emojis(text)
        self.assertIn('# Αναφορά', plain)
        self.assertIn('### ΓΛΩΣΣΑ', plain)
        self.assertNotIn('📖', plain)

    def test_write_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.md'
            write_report_md(self.report(), destination)
            original = destination.read_text(encoding='utf-8')
            with self.assertRaises(RuntimeError):
                write_report_md(self.report(), destination)
            self.assertEqual(destination.read_text(encoding='utf-8'), original)
            self.assertEqual(list(Path(directory).iterdir()), [destination])

    def test_missing_records(self):
        report = self.report()
        report['subjects'] = []
        self.assertIn('Δεν υπάρχει καταχώριση', render_report_md(report))
        report['date'] = None
        self.assertIn('Δεν βρέθηκαν', render_report_md(report))
