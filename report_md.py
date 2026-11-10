"""Markdown export of selected records; no raw ERP HTML or embedded links."""
from pathlib import Path
import os
import re
import tempfile

from lessons import normalize
from report_pdf import note_lines
from report_format import formatted_lines

# Decoration only: sync_exports.comparable() strips these so a format change is not new content.
SUBJECT_EMOJIS = {
    'γλωσσα': '📖', 'μαθηματικα': '🔢', 'αγγλικα': '🇬🇧',
    'μελετη περιβαλλοντοσ': '🌍', 'πληροφορικη': '💻', 'μουσικη': '🎵',
    'εικαστικα': '🎨', 'φυσικη αγωγη': '⚽', 'εργαστηρια δεξιοτητων': '🧩',
}
DEFAULT_SUBJECT_EMOJI = '📘'
EMOJIS = ('📋', '🎒', '📝', '🔗', '📅', '❓', DEFAULT_SUBJECT_EMOJI, *SUBJECT_EMOJIS.values())


def subject_emoji(name):
    key = normalize(name)
    return next((e for prefix, e in SUBJECT_EMOJIS.items() if key.startswith(prefix)),
                DEFAULT_SUBJECT_EMOJI)


def strip_emojis(markdown):
    for emoji in EMOJIS:
        markdown = markdown.replace(emoji + ' ', '')
    return markdown


def literal(value):
    # Escape Markdown punctuation and HTML so teacher text stays literal.
    return re.sub(r'([\\`*_{}\[\]()<>#+.!|~\-])', r'\\\1', str(value))


def render_report_md(report):
    lines = []

    def add(value):
        lines.extend([value, ''])

    day = report.get('date')
    add('# 📋 Αναφορά — ' + literal(report['student_name']))
    add('**Ημερομηνία καταχωρίσεων:** ' + literal(day or 'Δεν βρέθηκε'))
    add('**Σχολικό έτος:** ' + literal(report['school_year']))
    add('**Ανάκτηση:** ' + literal(report['retrieved_at']))
    add('Οι οδηγίες παρατίθενται όπως καταχωρίστηκαν. Το «αύριο» αφορά την ημερομηνία '
        'της καταχώρισης· το «επόμενο μάθημα» δεν σημαίνει απαραίτητα αύριο.')
    subjects = [s for s in report['subjects'] if s['entries']]
    if not subjects:
        add('Δεν υπάρχει καταχώριση για αυτή την ημερομηνία.' if day else
            'Δεν βρέθηκαν καταχωρισμένα μαθήματα μέχρι την ημερομηνία ανάκτησης.')
    else:
        for emoji, label, field, fallback in (
            ('🎒', 'Για το σπίτι / Προετοιμασία και τσάντα', 'fornextime', 'Δεν έχει καταχωριστεί εργασία.'),
            ('📝', f'Τι έκαναν — {day}', 'description', 'Δεν έχει καταχωριστεί περιγραφή.'),
        ):
            add('## ' + emoji + ' ' + literal(label))
            for subject in subjects:
                add('### ' + subject_emoji(subject['subject']) + ' ' + literal(subject['subject']))
                for entry in subject['entries']:
                    for line in note_lines(entry.get('name')):
                        add('*' + literal(line) + '*')
                    indent = ''
                    for kind, line, marker in formatted_lines(note_lines(entry.get(field)) or [fallback]):
                        if kind == 'heading':
                            lines.append('- **' + literal(line) + '**')
                            indent = '    '
                        else:
                            # Keep explicit teacher numbering literal: Markdown renderers
                            # otherwise renumber discontinuous lists automatically.
                            prefix = '' if marker == '•' else literal(marker) + ' '
                            lines.append(indent + '- ' + prefix + literal(line))
                    lines.append('')
                    if field == 'fornextime' and entry.get('nextdate'):
                        add('📅 **Επόμενο μάθημα (όπως καταχωρίστηκε):** ' + literal(entry['nextdate']))
        missing = [s['subject'] for s in report['subjects'] if not s['entries']]
        if missing:
            add('❓ Χωρίς καταχώριση για αυτή την ημερομηνία: ' + literal(', '.join(missing)))
        add('Η αναφορά δεν αποτελεί ωρολόγιο πρόγραμμα ή πλήρη λίστα εκκρεμών εργασιών. '
            'Παλαιότερες οδηγίες δεν μεταφέρονται αυτόματα και η ολοκλήρωση εργασιών είναι άγνωστη.')
        add('## 🔗 Πηγές')
        for subject in subjects:
            source = subject['source']
            prefix = 'https://erp.maliaras.gr/eclass/lesson/'
            if source.startswith(prefix) and source[len(prefix):].isdigit():
                add(f'- [{literal(subject["subject"])}]({source})')
    return '\n'.join(lines)


def write_report_md(report, destination):
    content = render_report_md(report)
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.report-', suffix='.md', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise RuntimeError(f'Markdown already exists; choose another --md path: {destination}') from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(destination)
