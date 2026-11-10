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


class ClipboardTests(unittest.TestCase):
    TEXT = '📋 *Αναφορά — Τρίτη 10/11*\n   • Γλώσσα σελ. 48'

    def test_windows_uses_powershell_with_utf8_payload(self):
        import base64
        from unittest.mock import patch
        import report_viber
        with patch.object(report_viber.sys, 'platform', 'win32'), \
                patch.object(report_viber.subprocess, 'run') as run, \
                patch.object(report_viber.os, 'startfile', create=True) as startfile, \
                patch.dict('os.environ', {'MALIARAS_VIBER_CHAT': 'Γονείς Β2'}):
            status = report_viber.open_in_viber(self.TEXT)
        command = run.call_args.args[0]
        self.assertEqual(command[0], 'powershell')
        self.assertIn('Set-Clipboard', command[-1])
        payload = run.call_args.kwargs['env']['MALIARAS_CLIPBOARD_B64']
        self.assertEqual(base64.b64decode(payload).decode('utf-8'), self.TEXT)
        startfile.assert_called_once_with('viber://')
        self.assertIn('Ctrl+V', status)
        self.assertIn('«Γονείς Β2»', status)

    def test_windows_viber_missing_keeps_clipboard(self):
        from unittest.mock import patch
        import report_viber
        with patch.object(report_viber.sys, 'platform', 'win32'), \
                patch.object(report_viber.subprocess, 'run'), \
                patch.object(report_viber.os, 'startfile', create=True, side_effect=OSError):
            status = report_viber.open_in_viber(self.TEXT)
        self.assertIn('Viber did not open', status)

    def test_macos_uses_pbcopy_and_cmd_v(self):
        from unittest.mock import patch
        import report_viber
        with patch.object(report_viber.sys, 'platform', 'darwin'), \
                patch.object(report_viber.subprocess, 'run') as run:
            status = report_viber.open_in_viber(self.TEXT)
        self.assertEqual(run.call_args_list[0].args[0], ['pbcopy'])
        self.assertEqual(run.call_args_list[0].kwargs['input'], self.TEXT.encode('utf-8'))
        self.assertEqual(run.call_args_list[1].args[0], ['open', '-a', 'Viber'])
        self.assertIn('Cmd+V', status)

    def test_linux_is_refused_clearly(self):
        from unittest.mock import patch
        import report_viber
        with patch.object(report_viber.sys, 'platform', 'linux'), \
                patch.object(report_viber.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'macOS and Windows'):
                report_viber.open_in_viber(self.TEXT)
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
