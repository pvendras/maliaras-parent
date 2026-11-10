"""Render selected report data locally; ERP HTML is text, never executable markup."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import os
import tempfile

from report_format import formatted_lines


class NoteText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if not self.hidden and tag in ('p', 'div', 'li', 'br', 'h1', 'h2', 'h3', 'tr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def note_lines(value):
    parser = NoteText()
    parser.feed(str(value or ''))
    return [' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip()]


def font_paths():
    pairs = [
        ('/System/Library/Fonts/Supplemental/Arial.ttf',
         '/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ]
    for regular, bold in pairs:
        if Path(regular).is_file() and Path(bold).is_file():
            return regular, bold
    raise RuntimeError('PDF requires Greek-capable Arial or DejaVu Sans fonts')


def write_report_pdf(report, destination):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph

    regular, bold = font_paths()
    pdfmetrics.registerFont(TTFont('ReportGreek', regular))
    pdfmetrics.registerFont(TTFont('ReportGreekBold', bold))
    body = ParagraphStyle('body', fontName='ReportGreek', fontSize=10, leading=15, spaceAfter=5)
    heading = ParagraphStyle('heading', parent=body, fontName='ReportGreekBold',
                             fontSize=13, leading=18, spaceBefore=12, keepWithNext=True)
    heading.textColor = colors.HexColor('#234b68')
    heading.spaceAfter = 9
    title = ParagraphStyle('title', parent=heading, fontSize=19, leading=25)
    subject_style = ParagraphStyle('subject', parent=heading, fontSize=11, leading=15,
                                   spaceBefore=9, spaceAfter=5)
    note_title = ParagraphStyle('noteTitle', parent=body, fontSize=9, leading=13,
                               textColor=colors.HexColor('#596575'), keepWithNext=True)
    subheading = ParagraphStyle('subheading', parent=subject_style, leftIndent=12,
                                fontSize=10, spaceBefore=7, spaceAfter=4)
    item = ParagraphStyle('item', parent=body, leftIndent=26, firstLineIndent=0,
                          bulletIndent=12, bulletFontName='ReportGreek',
                          bulletFontSize=10, spaceAfter=4)
    small = ParagraphStyle('small', parent=body, fontSize=8, leading=11,
                           textColor=colors.HexColor('#596575'))
    story = []

    def add(value, style=body):
        story.append(Paragraph(escape(str(value)), style))

    name = report['student_name']
    day = report.get('date')
    add(f'Αναφορά — {name}', title)
    add(f'Ημερομηνία καταχωρίσεων: {day or "Δεν βρέθηκε"}')
    add(f'Σχολικό έτος: {report["school_year"]}', small)
    add(f'Ανάκτηση: {report["retrieved_at"]}', small)
    add('Οι οδηγίες παρατίθενται όπως καταχωρίστηκαν. Το «αύριο» αφορά την ημερομηνία '
        'της καταχώρισης· το «επόμενο μάθημα» δεν σημαίνει απαραίτητα αύριο.')
    subjects = [s for s in report['subjects'] if s['entries']]
    if not subjects:
        add('Δεν υπάρχει καταχώριση για αυτή την ημερομηνία.' if day else
            'Δεν βρέθηκαν καταχωρισμένα μαθήματα μέχρι την ημερομηνία ανάκτησης.')
    else:
        # Keep original homework and packing instructions together: arbitrary teacher
        # prose cannot be reliably classified without inventing meaning or due dates.
        for label, field, fallback in (
            ('Για το σπίτι / Προετοιμασία και τσάντα', 'fornextime',
             'Δεν έχει καταχωριστεί εργασία.'),
            (f'Τι έκαναν — {day}', 'description',
             'Δεν έχει καταχωριστεί περιγραφή.'),
        ):
            add(label, heading)
            for subject in subjects:
                add(subject['subject'], subject_style)
                for entry in subject['entries']:
                    for line in note_lines(entry.get('name')):
                        add(line, note_title)
                    for kind, line, marker in formatted_lines(note_lines(entry.get(field)) or [fallback]):
                        if kind == 'heading':
                            add(line, subheading)
                        else:
                            story.append(Paragraph(escape(line), item, bulletText=marker))
                    if field == 'fornextime' and entry.get('nextdate'):
                        add(f'Επόμενο μάθημα (όπως καταχωρίστηκε): {entry["nextdate"]}', small)
        missing = [s['subject'] for s in report['subjects'] if not s['entries']]
        if missing:
            add('Χωρίς καταχώριση για αυτή την ημερομηνία: ' + ', '.join(missing))
        add('Πηγές', heading)
        for subject in subjects:
            # Link only helper-generated, same-origin lesson URLs, never ERP HTML links.
            source = subject['source']
            prefix = 'https://erp.maliaras.gr/eclass/lesson/'
            if source.startswith(prefix) and source[len(prefix):].isdigit():
                story.append(Paragraph(f'<link href="{escape(source, quote=True)}" color="blue">'
                                       f'{escape(subject["subject"])} — {escape(source)}</link>', item, bulletText='•'))
        add('Η αναφορά δεν αποτελεί ωρολόγιο πρόγραμμα ή πλήρη λίστα εκκρεμών εργασιών. '
            'Παλαιότερες οδηγίες δεν μεταφέρονται αυτόματα και η ολοκλήρωση εργασιών είναι άγνωστη.')

    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('ReportGreek', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(42, 24, f'{name} | {day or "—"}')
        canvas.drawRightString(A4[0] - 42, 24, str(doc.page))
        canvas.restoreState()

    # Build privately and publish only a complete PDF. Never overwrite an export.
    fd, temporary = tempfile.mkstemp(prefix='.report-', suffix='.pdf', dir=destination.parent)
    os.close(fd)
    try:
        SimpleDocTemplate(temporary, pagesize=A4, rightMargin=42, leftMargin=42,
                          topMargin=36, bottomMargin=42, title=f'Αναφορά — {name} — {day}',
                          author='Maliaras parent').build(story, onFirstPage=footer, onLaterPages=footer)
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise RuntimeError(f'PDF already exists; choose another --pdf path: {destination}') from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(destination)
