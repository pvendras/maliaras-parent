"""Read the student's weekly timetable; subjects and periods only, no teachers or rooms."""
import argparse
from datetime import datetime, timedelta
import json
import subprocess
from zoneinfo import ZoneInfo

from client import BASE, Client, STUDENTS
from lessons import parse_date

DAYS = {1: 'Δευτέρα', 2: 'Τρίτη', 3: 'Τετάρτη', 4: 'Πέμπτη', 5: 'Παρασκευή',
        6: 'Σάββατο', 7: 'Κυριακή'}
# Period start times as configured in the ERP schedule page (not returned by the API).
PERIOD_STARTS = {1: '08:30', 2: '09:15', 3: '10:15', 4: '11:00', 5: '12:00', 6: '12:45',
                 7: '13:30', 8: '14:15', 9: '15:00', 10: '16:00', 11: '16:50'}
# The ERP stores no end times; 45 minutes matches every gap between the starts above.
PERIOD_MINUTES = 45


def period_end(start):
    if start is None:
        return None
    end = datetime.strptime(start, '%H:%M') + timedelta(minutes=PERIOD_MINUTES)
    return end.strftime('%H:%M')


def build_week(data):
    if not isinstance(data, dict):
        raise RuntimeError('Unexpected timetable schema; cannot establish the schedule')
    week = []
    for day_key in sorted(data, key=int):
        day = int(day_key)
        hours = data[day_key]
        if day not in DAYS or not isinstance(hours, dict):
            raise RuntimeError('Unexpected timetable day; content suppressed')
        periods = []
        for hour_key in sorted(hours, key=int):
            slots = hours[hour_key].get('lesson_schedules') if isinstance(hours[hour_key], dict) else None
            if not isinstance(slots, list):
                raise RuntimeError('Unexpected timetable period; content suppressed')
            period = int(hour_key)
            for slot in slots:
                # Never expose teacher, class or room objects.
                try:
                    subject, lesson_id = slot['lesson']['name'], int(slot['id'])
                except (KeyError, TypeError, ValueError):
                    raise RuntimeError('Unexpected timetable lesson; content suppressed') from None
                if not isinstance(subject, str):
                    raise RuntimeError('Unexpected timetable lesson; content suppressed')
                periods.append({'period': period, 'start': PERIOD_STARTS.get(period),
                                'end': period_end(PERIOD_STARTS.get(period)),
                                'subject': subject,
                                'source': f'{BASE}/eclass/lesson/{lesson_id}'})
        week.append({'day': day, 'day_name': DAYS[day], 'periods': periods})
    return week


def select_days(week, start):
    """Return the searched date and the next later date that has lessons."""
    by_day = {d['day']: d['periods'] for d in week}
    selected = [{'date': start.isoformat(), 'day_name': DAYS[start.isoweekday()],
                 'periods': by_day.get(start.isoweekday(), [])}]
    for offset in range(1, 8):
        day = start + timedelta(days=offset)
        if by_day.get(day.isoweekday()):
            selected.append({'date': day.isoformat(), 'day_name': DAYS[day.isoweekday()],
                             'periods': by_day[day.isoweekday()]})
            break
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--student', required=True, choices=STUDENTS)
    parser.add_argument('--date', type=parse_date,
                        help='Athens date YYYY-MM-DD (default: today); returns that day '
                             'and the next day with lessons')
    parser.add_argument('--week', action='store_true', help='Return the whole week instead')
    args = parser.parse_args()
    client = Client(args.student)
    user = client.login()
    if not isinstance(user, dict) or not user.get('studentid'):
        raise RuntimeError('Login response lacks a student id; cannot select the timetable')
    year = client.get('/api/defaultYear')
    week = build_week(client.post('/api/eclass/calculateSchedule', {
        'yearid': int(year['id']), 'studentid': user['studentid'],
    }))
    output = {
        'student': args.student, 'student_name': STUDENTS[args.student]['name'],
        'school_year': year['name'], 'mode': 'schedule',
        'retrieved_at': datetime.now(ZoneInfo('Europe/Athens')).isoformat(),
        'source': f'{BASE}/eclass/schedule',
        'notice': 'Recurring weekly timetable; it does not show holidays, trips, '
                  'substitutions or attendance. Start times come from the ERP page '
                  'configuration; end times are estimated as start + 45 minutes.',
    }
    if args.week:
        output['days'] = week
    else:
        start = args.date or datetime.now(ZoneInfo('Europe/Athens')).date()
        output['date'] = start.isoformat()
        output['days'] = select_days(week, start)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error))
