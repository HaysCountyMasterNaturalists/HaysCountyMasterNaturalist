from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from flask import (
    Blueprint, current_app, g, render_template, request
)
from pytz import timezone
from werkzeug.exceptions import abort

from flask_app.auth import editor_required
from flask_app.db import get_db


utc = timezone('UTC')
central = timezone('US/Central')


bp = Blueprint('opportunities', __name__)


def get_opportunities():
    '''Gets all active opportunities plus those that have occured in the last
    45 days.

    Includes recurring opportunities and anytime opportunities that either don't
    have an expiration_date or have one that is greater than the current date.

    Returns:
        opportunities(arr): An array of opportunity dicts.
    '''
    opportunities = []
    with get_db() as cursor:
        cursor.execute(
            """SELECT
                    id,
                    owner,
                    title,
                    body,
                    anywhere,
                    anytime,
                    location,
                    city,
                    event_start,
                    event_end,
                    expiration_date,
                    category,
                    project_id,
                    recurring_weekly,
                    recurring_monthly,
                    recurring_days,
                    link,
                    just_show_up
                FROM opportunities
                WHERE (event_start >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 45 DAY) AND (expiration_date IS NULL OR expiration_date >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 45 DAY)))
                    OR (anytime IS TRUE AND (expiration_date IS NULL OR expiration_date >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 45 DAY)))
                    OR (recurring_weekly IS TRUE AND (expiration_date IS NULL OR expiration_date >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 45 DAY)))
                    OR (recurring_monthly IS NOT NULL AND (expiration_date IS NULL OR expiration_date >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 45 DAY)))"""
        )
        db_opportunities = cursor.fetchall()

    for opp in db_opportunities:
        opportunities.append({
            'id': opp[0],
            'owner': opp[1],
            'title': opp[2],
            'body': opp[3],
            'anywhere': opp[4] == 1,
            'anytime': opp[5] == 1,
            'location': opp[6],
            'city': opp[7],
            'event_start': utc.localize(opp[8]) if opp[8] else None,
            'event_end': utc.localize(opp[9]) if opp[9] else None,
            'expiration_date': utc.localize(opp[10]) if opp[10] else None,
            'category': opp[11],
            'project_id': opp[12],
            'recurring_weekly': opp[13] == 1,
            'recurring_monthly': opp[14],
            'recurring_days': opp[15],
            'link': opp[16],
            'just_show_up': opp[17] == 1
        })

    return opportunities


def convert_to_local_time(opp, day=None, original_hour=None):
    '''Converts opp(dict)'s event_start, event_end, and expiration_date from utc
    to YYYY-MM-DD HH:mm local time.'''
    if opp.get('expiration_date'):
        opp['expiration_date'] = opp['expiration_date'].astimezone(central).strftime('%Y-%m-%d %H:%M')
    if opp.get('event_start'):
        event_length = timedelta(seconds=3600)
        if opp.get('event_end'):
            event_length = opp['event_end'] - opp['event_start']
        # Capture the event's true local time-of-day before `day` (which may be
        # an iteration cursor seeded from a 45-days-ago wall-clock time) replaces
        # event_start, so we can restore both hour and minute below.
        original_minute = opp['event_start'].astimezone(central).minute
        if day:
            opp['event_start'] = day
        localized_start = opp['event_start'].astimezone(central)
        if original_hour is not None:
            localized_start = localized_start.replace(hour=original_hour, minute=original_minute)
        opp['event_start'] = localized_start.strftime('%Y-%m-%d %H:%M')
        opp['event_end'] = (localized_start + event_length).strftime('%Y-%m-%d %H:%M')


def find_recurring(opportunities):
    '''Adds all opportunity recurrences to opportunities array.

    Parameters:
    opportunities (arr): a list of opportunity dicts with expiration_date,
        event_start, event_end, recurring_weekly, and recurring_monthly

    Returns:
    all_opportunities (arr): a list of opportunity dicts that inlcudes all
        occurences of recurring events from 45 days back to 3 months in the
        future.
    '''
    all_opportunities = []
    now = datetime.now(tz=utc)
    six_months_out = now + relativedelta(months=6)
    fortyfive_days_ago = now - timedelta(days=45)

    # Expand one opportunity into all_opportunities. A closure so the loop below
    # can wrap each call: one malformed recurrence must never raise out of the
    # public list endpoint and blank the whole calendar for everyone.
    def expand(opp):
        expiration_date = opp.get('expiration_date')

        if opp['recurring_weekly']:
            # Fallback logic: Use string from DB or calculate from event_start
            if opp.get('recurring_days'):
                allowed_days = [int(d) for d in opp['recurring_days'].split(',')]
            else:
                # Localize and get weekday (Python 0=Mon, so convert to Moment 0=Sun)
                localized_start = opp['event_start'].astimezone(central)
                allowed_days = [(localized_start.weekday() + 1) % 7]

            day = opp['event_start']
            original_hour = day.astimezone(central).hour
            current_day = max(day, fortyfive_days_ago)

            while current_day <= six_months_out and (not expiration_date or current_day <= expiration_date):
                # Calculate current day's Moment-style weekday index
                moment_weekday = (current_day.astimezone(central).weekday() + 1) % 7

                if moment_weekday in allowed_days:
                    new_opp = opp.copy()
                    convert_to_local_time(new_opp, current_day, original_hour)
                    all_opportunities.append(new_opp)

                current_day += timedelta(days=1)  # Check every day

        elif opp['recurring_monthly']:
            # adds opp every month for 3 months out (accounting for expiration_date).
            # recurring_monthly is the Nth week (1-5) of the month; (N-1)*7 is used
            # below as a day-of-month floor, so a value >5 makes that floor exceed
            # every real date and the advance loop never terminates. Skip such rows.
            if not 1 <= opp['recurring_monthly'] <= 5:
                current_app.logger.warning(
                    "find_recurring: skipping opp %s with out-of-range "
                    "recurring_monthly=%s", opp.get('id'), opp['recurring_monthly'])
                return
            day = opp['event_start']
            original_hour = day.astimezone(central).hour
            at_least_date = (opp['recurring_monthly'] - 1) * 7
            while day < fortyfive_days_ago or day.day <= at_least_date:
                day += timedelta(days=7)
            while day <= six_months_out and (not expiration_date or day <= expiration_date):
                new_opp = opp.copy()
                convert_to_local_time(new_opp, day, original_hour)
                all_opportunities.append(new_opp)
                current_month = day.month
                while day.month == current_month or day.day <= at_least_date:
                    day += timedelta(days=7)
        else:
            # adds non-recurring opps as-is.
            convert_to_local_time(opp)
            all_opportunities.append(opp)

    for opp in opportunities:
        try:
            expand(opp)
        except Exception:
            current_app.logger.exception(
                "find_recurring: skipping opportunity %s", opp.get('id'))

    return all_opportunities

def clean_city(city):
    '''Capitalizes each letter in city(str)'''
    if city:
        return city.title()
    else:
        return None


def clean_recurring_days(form):
    '''Normalizes recurring_days form input to a comma-separated string of
    Moment-style weekday indices (0=Sun..6=Sat), or None when empty.

    Accepts Vueform's indexed array serialization (recurring_days[0],
    recurring_days[1], ...), bracketed keys (recurring_days[]), repeated plain
    keys, or a single comma-joined value.'''
    raw = []
    for key in form.keys():
        if key == 'recurring_days' or key.startswith('recurring_days['):
            raw.extend(form.getlist(key))
    days = []
    for entry in raw:
        if entry is None:
            continue
        for d in str(entry).split(','):
            d = d.strip()
            if d:
                days.append(d)
    return ','.join(days) if days else None


def clean_recurring_monthly(value):
    '''Validate the monthly-recurrence value, or None when blank.

    recurring_monthly is the Nth occurrence (1-5) of the event's weekday each
    month. find_recurring expands it using (N-1)*7 as a day-of-month floor, so
    only 1-5 are meaningful; anything outside that range is rejected here so a
    bad value can never reach the expansion loop.'''
    if not value:
        return None
    n = int(value)  # ValueError on non-numeric -> 400 via the caller's handler
    if not 1 <= n <= 5:
        raise ValueError('recurring_monthly must be between 1 and 5')
    return n


def clean_date(dt):
    '''Convert a Central-time date/datetime string to a UTC datetime.

    Handles the formats the form submits:
      - 'YYYY-MM-DD HH:MM'  (event_start / event_end, 24-hour)
      - 'YYYY-MM-DD'        (expiration_date, date only)
    and still tolerates a legacy ' am'/' pm' suffix from the old form.
    '''
    if not dt:
        return None
    dt = dt.strip()
    if not dt:
        return None
    if dt.lower().endswith(('am', 'pm')):
        pm = dt.lower().endswith('pm')
        core = dt[:-2].strip()
        dat = central.localize(datetime.strptime(core, '%Y-%m-%d %H:%M'))
        # don't add 12 hours to 12pm
        if pm and dat.hour != 12:
            dat += timedelta(hours=12)
        return dat.astimezone(utc)
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return central.localize(datetime.strptime(dt, fmt)).astimezone(utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {dt!r}")


def get_opportunity(id):
    '''Fetches opportunity from database by id.'''
    opportunity = None
    with get_db() as cursor:
        cursor.execute(
            """SELECT id, owner, title, body, anywhere, anytime, location, city,
                        event_start,
                        event_end,
                        expiration_date,
                        category, project_id, recurring_weekly,
                        recurring_monthly, recurring_days, link, just_show_up
                FROM opportunities
                WHERE id = %(id)s""",
            {'id': id}
        )
        opportunity = cursor.fetchone()

    if opportunity is None:
        abort(404, f"Post id {id} doesn't exist.")

    return opportunity


def convert_to_readable_local(dt):
    '''Converts UTC datetime to central YYYY-MM-DD HH:mm'''
    return utc.localize(dt).astimezone(central).strftime('%Y-%m-%d %H:%M') if dt else None


@bp.route('/api/opportunities')
def list():
    return find_recurring(get_opportunities())


@bp.route('/api/create', methods=['POST'])
@editor_required
def create():
    with get_db() as cursor:
        try:
            cursor.execute(
                """INSERT INTO opportunities (owner, title, body, anywhere,
                            anytime, location, city, event_start, event_end,
                            expiration_date, category, project_id,
                            recurring_weekly, recurring_monthly,
                            recurring_days, link, just_show_up)
                    VALUES (%(owner)s, %(title)s, %(body)s, %(anywhere)s,
                            %(anytime)s, %(location)s, %(city)s,
                            %(event_start)s, %(event_end)s, %(expiration_date)s,
                            %(category)s, %(project_id)s,
                            %(recurring_weekly)s, %(recurring_monthly)s,
                            %(recurring_days)s, %(link)s, %(just_show_up)s)""",
                {
                    'owner': g.user['id'],
                    'title': request.form['title'],
                    'body': request.form['body'],
                    'anywhere': 1 if request.form.get('anywhere') == 'true' else 0,
                    'anytime': 1 if request.form.get('anytime') == 'true' else 0,
                    'location': request.form.get('location') or None,
                    'city': clean_city(request.form.get('city')),
                    'event_start': clean_date(request.form.get('event_start')),
                    'event_end': clean_date(request.form.get('event_end')),
                    'expiration_date': clean_date(request.form.get('expiration_date')),
                    'category': request.form['category'],
                    'project_id': request.form['at_category'] if request.form['category'] == 'AT' else request.form.get('project_id'),
                    'recurring_weekly': 1 if request.form.get('recurring_weekly') == 'true' else 0,
                    'recurring_monthly': clean_recurring_monthly(request.form.get('recurring_monthly')),
                    'recurring_days': clean_recurring_days(request.form),
                    'link': request.form.get('link') or None,
                    'just_show_up': 1 if request.form.get('just_show_up') == 'true' else 0,
                }
            )
        except Exception as e:
            return { 'error': str(e) }, 400
    return { 'success': True }


@bp.route('/api/delete/<int:id>', methods=['POST'])
@editor_required
def delete(id):
    try:
        with get_db() as cursor:
            cursor.execute(
                """SELECT owner
                    FROM opportunities
                    WHERE id = %(id)s""",
                { 'id': id }
            )
            owner = cursor.fetchone()[0]
            if not g.user['admin'] and g.user['id'] != owner:
                return { 'error': 'User does not have permission' }, 400
            cursor.execute(
                """DELETE from opportunities
                    WHERE id = %(id)s""",
                { 'id': id }
            )
    except Exception as e:
        return { 'error': str(e) }, 400

    return { 'success': True }

@bp.route('/api/update/<int:id>', methods=['POST'])
@editor_required
def update(id):
    try:
        with get_db() as cursor:
            cursor.execute(
                """SELECT owner
                    FROM opportunities
                    WHERE id = %(id)s""",
                { 'id': id }
            )
            owner = cursor.fetchone()[0]
            if not g.user['admin'] and g.user['id'] != owner:
                return { 'error': 'User does not have permission' }, 400
            cursor.execute(
                """UPDATE opportunities
                    SET
                        title = %(title)s,
                        body = %(body)s,
                        anywhere = %(anywhere)s,
                        anytime = %(anytime)s,
                        location = %(location)s,
                        city = %(city)s,
                        event_start = %(event_start)s,
                        event_end = %(event_end)s,
                        expiration_date = %(expiration_date)s,
                        category = %(category)s,
                        project_id = %(project_id)s,
                        recurring_weekly = %(recurring_weekly)s,
                        recurring_monthly = %(recurring_monthly)s,
                        recurring_days = %(recurring_days)s,
                        link = %(link)s,
                        just_show_up = %(just_show_up)s
                    WHERE id = %(id)s""",
                {
                    'id': id,
                    'title': request.form['title'],
                    'body': request.form['body'],
                    'anywhere': 1 if request.form.get('anywhere') == 'true' else 0,
                    'anytime': 1 if request.form.get('anytime') == 'true' else 0,
                    'location': request.form.get('location') or None,
                    'city': clean_city(request.form.get('city')),
                    'event_start': clean_date(request.form.get('event_start')),
                    'event_end': clean_date(request.form.get('event_end')),
                    'expiration_date': clean_date(request.form.get('expiration_date')),
                    'category': request.form['category'],
                    'project_id': request.form['at_category'] if request.form['category'] == 'AT' else request.form.get('project_id'),
                    'recurring_weekly': 1 if request.form.get('recurring_weekly') == 'true' else 0,
                    'recurring_monthly': clean_recurring_monthly(request.form.get('recurring_monthly')),
                    'recurring_days': clean_recurring_days(request.form),
                    'link': request.form.get('link') or None,
                    'just_show_up': 1 if request.form.get('just_show_up') == 'true' else 0,
                }
            )
    except Exception as e:
        return { 'error': str(e) }, 400

    return { 'success': True }


@bp.route('/api/opportunities/<int:id>')
def opportunity_object(id):
    opp = get_opportunity(id)
    return {
        'id': opp[0],
        'owner': opp[1],
        'title': opp[2],
        'body': opp[3],
        'anywhere': opp[4] == 1,
        'anytime': opp[5] == 1,
        'location': opp[6],
        'city': opp[7],
        'event_start': convert_to_readable_local(opp[8]),
        'event_end': convert_to_readable_local(opp[9]),
        'expiration_date': convert_to_readable_local(opp[10]),
        'category': opp[11],
        'project_id': opp[12],
        'recurring_weekly': opp[13] == 1,
        'recurring_monthly': opp[14],
        'recurring_days': opp[15],
        'link': opp[16],
        'just_show_up': opp[17] == 1
    }


@bp.route('/', defaults={'path': ''})
@bp.route('/<path:path>')
def index(path):
    '''Serves the single page app.'''
    return render_template('opportunities/index.html')
