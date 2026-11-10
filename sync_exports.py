# /// script
# requires-python = ">=3.10"
# dependencies = ["reportlab>=4.4,<5"]
# ///
"""Export new/changed recorded days for both children; never overwrite older exports."""
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo

from client import Client, STUDENTS
from lessons import entry_day, fetch_lesson, report_subjects
from report_md import render_report_md, strip_emojis, write_report_md
from report_pdf import write_report_pdf

ROOT = Path(__file__).resolve().parent


LESSON_ID = re.compile(r'/eclass/lesson/\d+')


def comparable(markdown):
    # Retrieval time, emoji decoration and section order are not new school content.
    # The ERP renumbers lesson IDs (source links) roughly weekly, so ignore the ID too.
    return sorted(LESSON_ID.sub('/eclass/lesson/ID', line)
                  for line in strip_emojis(markdown).splitlines()
                  if not line.startswith('**Ανάκτηση:** '))


def export_day(report, directory):
    directory = Path(directory)
    base = f'{report["student"]}-report-{report["date"]}'
    desired = comparable(render_report_md(report))
    candidates = sorted(directory.glob(base + '*.md'))
    for md in candidates:
        if md.with_suffix('.pdf').is_file() and comparable(md.read_text(encoding='utf-8')) == desired:
            return {'student': report['student'], 'date': report['date'], 'status': 'unchanged',
                    'pdf': str(md.with_suffix('.pdf').resolve()), 'md': str(md.resolve())}
    stem = base
    version = 2
    while any((directory / f'{stem}.{ext}').exists() for ext in ('pdf', 'md')):
        stem = f'{base}-v{version}'
        version += 1
    pdf = write_report_pdf(report, directory / f'{stem}.pdf')
    md = write_report_md(report, directory / f'{stem}.md')
    return {'student': report['student'], 'date': report['date'], 'status': 'exported',
            'pdf': pdf, 'md': md}


def sync_student(student, directory):
    client = Client(student)
    client.login()
    year = client.get('/api/defaultYear')
    lessons = client.get(f'/api/eclass/mylessons/{int(year["id"])}')
    subjects = [fetch_lesson(client, lesson, None) for lesson in lessons]
    now = datetime.now(ZoneInfo('Europe/Athens'))
    days = sorted({day for s in subjects for entry in s['entries']
                   if (day := entry_day(entry.get('date'))) is not None and day <= now.date()})
    results = []
    for day in days:
        report = {'student': student, 'student_name': STUDENTS[student]['name'],
                  'school_year': year['name'], 'retrieved_at': now.isoformat(),
                  **report_subjects(subjects, day, now.date())}
        results.append(export_day(report, directory))
    return results


def main():
    # Explicit standing authorization in the project skill covers both accounts.
    # Print only export metadata, not unrelated lesson text.
    for student in STUDENTS:
        results = sync_student(student, ROOT / 'reports')
        print(json.dumps({'student': student,
                          'unchanged': sum(r['status'] == 'unchanged' for r in results),
                          'exports': [r for r in results if r['status'] == 'exported']},
                         ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
