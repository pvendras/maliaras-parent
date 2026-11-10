"""Plain-text report for pasting into Viber.

Deliberately leaves out the child's name, notes and source links: the message
ends with the timetable. Nothing is sent; the parent pastes and sends it.
"""
from datetime import date
import subprocess

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


def open_in_viber(text):
    """Copy to the macOS clipboard and bring Viber forward; the parent pastes and sends."""
    subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True, timeout=10)
    subprocess.run(['open', '-a', 'Viber'], check=True, timeout=10)


if __name__ == '__main__':
    # Text already written for the parent (e.g. the chat report) arrives on stdin.
    import sys
    message = sys.stdin.read().strip()
    if not message:
        raise SystemExit('No message on stdin')
    open_in_viber(message)
    import os
    chat = os.environ.get('MALIARAS_VIBER_CHAT', '').strip()
    print('Copied to clipboard and opened Viber; paste'
          + (f' into «{chat}»' if chat else '') + ' and send manually.')
