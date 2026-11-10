"""Plain-text report for pasting into Viber.

Deliberately leaves out the child's name, notes and source links: the message
ends with the timetable. Nothing is sent; the parent pastes and sends it.
"""
import base64
from datetime import date
import os
import subprocess
import sys

from lessons import normalize
from report_md import subject_emoji
from report_pdf import note_lines
from report_format import formatted_lines

WEEKDAYS = ('Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή')


def day_label(value):
    day = date.fromisoformat(value)
    return f'{WEEKDAYS[day.weekday()]} {day.day}/{day.month}'


# ERP names are unaccented capitals; show the usual accented names.
SUBJECT_NAMES = {
    'γλωσσα': 'Γλώσσα', 'μαθηματικα': 'Μαθηματικά', 'αγγλικα': 'Αγγλικά',
    'μελετη περιβαλλοντοσ': 'Μελέτη Περιβάλλοντος', 'πληροφορικη': 'Πληροφορική',
    'μουσικη': 'Μουσική', 'εικαστικα': 'Εικαστικά', 'φυσικη αγωγη': 'Φυσική Αγωγή',
    'εργαστηρια δεξιοτητων': 'Εργαστήρια Δεξιοτήτων', 'θεατρικη αγωγη': 'Θεατρική Αγωγή',
}


def subject_title(name):
    key = normalize(name)
    known = next((title for prefix, title in SUBJECT_NAMES.items() if key.startswith(prefix)), None)
    return known or ' '.join(w if '.' in w else w.capitalize() for w in name.split())


def render_viber(report, days):
    """`days` is schedule.select_days() output for the report date (may be empty)."""
    day = report.get('date')
    if not day:
        return '📋 Δεν βρέθηκαν καταχωρισμένα μαθήματα.'
    lines = [f'📋 *Αναφορά — {day_label(day)}*', '']
    subjects = [s for s in report['subjects'] if s['entries']]
    if not subjects:
        lines += ['Δεν υπάρχει καταχώριση για αυτή την ημερομηνία.', '']
    for emoji, label, field, fallback in (
        ('🎒', 'Για το σπίτι / τσάντα', 'fornextime', 'Δεν έχει καταχωριστεί εργασία.'),
        ('📝', 'Τι έκαναν', 'description', 'Δεν έχει καταχωριστεί περιγραφή.'),
    ):
        if not subjects:
            break
        lines += [f'{emoji} *{label}*']
        for subject in subjects:
            lines.append(f'{subject_emoji(subject["subject"])} {subject_title(subject["subject"])}')
            for entry in subject['entries']:
                for kind, text, marker in formatted_lines(note_lines(entry.get(field)) or [fallback]):
                    lines.append(f'   {text}' if kind == 'heading' else f'   • {text}')
        lines.append('')
    if days:
        lines.append('🗓️ *Πρόγραμμα*')
        for scheduled in days:
            lines.append(f'_{day_label(scheduled["date"])}_')
            if not scheduled['periods']:
                lines.append('   • Χωρίς μαθήματα στο εβδομαδιαίο πρόγραμμα')
            for p in scheduled['periods']:
                times = f'{p["start"]}–{p["end"]} ' if p.get('start') else ''
                lines.append(f'   • {p["period"]}η {times}{subject_emoji(p["subject"])} '
                             f'{subject_title(p["subject"])}')
    return '\n'.join(lines).rstrip()


def copy_to_clipboard(text):
    if sys.platform == 'darwin':
        subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True, timeout=10)
    elif sys.platform == 'win32':
        # Base64 in an environment variable keeps Greek and emojis intact; the
        # Windows console code page would otherwise mangle them on stdin.
        script = ('Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString('
                  '[Convert]::FromBase64String($env:MALIARAS_CLIPBOARD_B64)))')
        subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                       env={**os.environ, 'MALIARAS_CLIPBOARD_B64':
                            base64.b64encode(text.encode('utf-8')).decode('ascii')},
                       check=True, timeout=30)
    else:
        raise RuntimeError('Viber clipboard support is available on macOS and Windows only')


def launch_viber():
    """Best effort: the text is already on the clipboard even if Viber does not open."""
    try:
        if sys.platform == 'darwin':
            subprocess.run(['open', '-a', 'Viber'], check=True, timeout=10)
        else:
            os.startfile('viber://')  # Windows: Viber Desktop registers this link
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def open_in_viber(text):
    """Copy to the clipboard and bring Viber forward; the parent pastes and sends."""
    copy_to_clipboard(text)
    opened = launch_viber()
    paste = 'Cmd+V' if sys.platform == 'darwin' else 'Ctrl+V'
    chat = os.environ.get('MALIARAS_VIBER_CHAT', '').strip()
    where = f' into «{chat}»' if chat else ''
    return (('Copied to clipboard and opened Viber' if opened else
             'Copied to clipboard; Viber did not open, open it manually')
            + f'; paste{where} with {paste} and send manually.')


if __name__ == '__main__':
    # Text already written for the parent (e.g. the chat report) arrives on stdin as UTF-8.
    message = sys.stdin.buffer.read().decode('utf-8-sig').strip()
    if not message:
        raise SystemExit('No message on stdin')
    try:
        print(open_in_viber(message))
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        raise SystemExit(f'Could not copy to clipboard: {error}')
