import tempfile
from pathlib import Path
import unittest

from report_pdf import note_lines, write_report_pdf


class PdfTests(unittest.TestCase):
    def test_html_is_text(self):
        self.assertEqual(note_lines('<p>σελ. 5-6 &amp; 7</p><script>bad()</script>'
                                    '<li><a href="https://example.com">Βιβλίο</a></li>'),
                         ['σελ. 5-6 & 7', 'Βιβλίο'])

    def test_pdf_and_overwrite_protection(self):
        from pypdf import PdfReader
        report = {'student_name': 'Νίκος', 'date': '2026-09-14',
                  'school_year': '2026-2027', 'retrieved_at': '2026-09-14T19:00:00+03:00',
                  'subjects': [{'subject': 'ΓΛΩΣΣΑ',
                                'source': 'https://erp.maliaras.gr/eclass/lesson/123',
                                'entries': [{'name': 'Μάθημα', 'description': '<p>σελ. 6-7</p>',
                                             'fornextime': '<p>Φέρνω βιβλίο &amp; φάκελο.</p>' * 100}]}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.pdf'
            write_report_pdf(report, path)
            reader = PdfReader(path)
            self.assertGreater(len(reader.pages), 1)
            text = '\n'.join(page.extract_text() for page in reader.pages)
            self.assertIn('Νίκος', text)
            self.assertIn('σελ. 6-7', text)
            self.assertIn('Φέρνω βιβλίο & φάκελο.', text)
            original = path.read_bytes()
            with self.assertRaises(RuntimeError):
                write_report_pdf(report, path)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            report['subjects'] = []
            report['date'] = None
            write_report_pdf(report, Path(directory) / 'empty.pdf')
            self.assertIn('Δεν βρέθηκαν', PdfReader(Path(directory) / 'empty.pdf').pages[0].extract_text())
