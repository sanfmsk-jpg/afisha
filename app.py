# -*- coding: utf-8 -*-
"""Веб-приложение «Афиша мероприятий» с фильтром по датам.

Курсовой проект по МДК.09.01.
Автор: Передрий Алексей Владимирович, группа 4ИСИП-1023.
"""

import datetime as dt
import functools
import os

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('AFISHA_SECRET', 'afisha-dev-secret-key')
app.config['TEMPLATES_AUTO_RELOAD'] = True

MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
          'августа', 'сентября', 'октября', 'ноября', 'декабря')
WEEKDAYS = ('пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс')
STATUS_TITLES = {'published': 'Опубликовано',
                 'pending': 'На модерации',
                 'rejected': 'Отклонено'}


# --- Фильтры шаблонизатора ---------------------------------------------------

def _parse(value):
    if isinstance(value, dt.datetime):
        return value
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return dt.datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    return None


@app.template_filter('rudate')
def rudate(value, with_time=True, with_year=False):
    """Преобразует дату в формат «12 ноября, ср, 19:00»."""
    d = _parse(value)
    if d is None:
        return ''
    out = '%d %s' % (d.day, MONTHS[d.month - 1])
    if with_year:
        out += ' %d' % d.year
    out += ', %s' % WEEKDAYS[d.weekday()]
    if with_time and (d.hour or d.minute):
        out += ', %02d:%02d' % (d.hour, d.minute)
    return out


@app.template_filter('price')
def price(event):
    if event['is_free']:
        return 'Бесплатно'
    return 'от %s ₽' % format(event['price_min'], ',d').replace(',', ' ')


@app.template_filter('status')
def status_title(value):
    return STATUS_TITLES.get(value, value)


# --- Контекст запроса --------------------------------------------------------

@app.before_request
def load_user():
    g.user = None
    uid = session.get('user_id')
    if uid:
        g.user = db.query('SELECT * FROM users WHERE id = ?', (uid,), one=True)


@app.context_processor
def inject_globals():
    return {
        'user': g.user,
        'cities': db.cities(),
        'categories': db.categories(),
        'today': dt.date.today().isoformat(),
        'now': dt.datetime.now(),
    }


def login_required(view):
    @functools.wraps(view)
    def wrapper(*a, **kw):
        if g.user is None:
            flash('Войдите в личный кабинет, чтобы продолжить', 'warn')
            return redirect(url_for('login', next=request.path))
        return view(*a, **kw)
    return wrapper


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*a, **kw):
        if g.user is None:
            return redirect(url_for('login', next=request.path))
        if g.user['role'] != 'admin':
            abort(403)
        return view(*a, **kw)
    return wrapper


# --- Каталог мероприятий и фильтрация ---------------------------------------

DATE_PRESETS = (('all', 'Все даты'), ('today', 'Сегодня'),
                ('tomorrow', 'Завтра'), ('weekend', 'Выходные'),
                ('week', 'Неделя'), ('month', 'Месяц'))


def resolve_period(preset, date_from, date_to):
    """Вычисляет границы периода по выбранному шаблону фильтра дат."""
    today = dt.date.today()
    if preset == 'today':
        return today.isoformat(), today.isoformat()
    if preset == 'tomorrow':
        d = today + dt.timedelta(days=1)
        return d.isoformat(), d.isoformat()
    if preset == 'weekend':
        sat = today + dt.timedelta(days=(5 - today.weekday()) % 7)
        return sat.isoformat(), (sat + dt.timedelta(days=1)).isoformat()
    if preset == 'week':
        return today.isoformat(), (today + dt.timedelta(days=7)).isoformat()
    if preset == 'month':
        return today.isoformat(), (today + dt.timedelta(days=30)).isoformat()
    return date_from or None, date_to or None


def read_filters():
    preset = request.args.get('period', 'all')
    date_from, date_to = resolve_period(preset,
                                        request.args.get('date_from', ''),
                                        request.args.get('date_to', ''))
    return {
        'period': preset,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'city': request.args.get('city', ''),
        'category': request.args.get('category', ''),
        'q': request.args.get('q', '').strip(),
        'free': request.args.get('free') == '1',
        'sort': request.args.get('sort', 'date'),
    }


@app.route('/')
def catalog():
    f = read_filters()
    # По умолчанию каталог показывает только будущие мероприятия
    f_from = f['date_from'] or dt.date.today().isoformat()
    events = db.search_events(date_from=f_from, date_to=f['date_to'],
                              city=f['city'], category=f['category'],
                              q=f['q'], only_free=f['free'], sort=f['sort'])
    favs = db.favorite_ids(g.user['id']) if g.user else set()
    return render_template('catalog.html', events=events, f=f, favs=favs,
                           presets=DATE_PRESETS)


@app.route('/api/events')
def api_events():
    """REST-метод для динамического обновления каталога без перезагрузки."""
    f = read_filters()
    f_from = f['date_from'] or dt.date.today().isoformat()
    events = db.search_events(date_from=f_from, date_to=f['date_to'],
                              city=f['city'], category=f['category'],
                              q=f['q'], only_free=f['free'], sort=f['sort'])
    return jsonify({'count': len(events),
                    'filters': f,
                    'items': [dict(e) for e in events]})


@app.route('/event/<int:event_id>')
def event_page(event_id):
    event = db.get_event(event_id)
    if event is None:
        abort(404)
    if event['status'] != 'published' and not (
            g.user and g.user['role'] == 'admin'):
        abort(404)
    similar = db.search_events(category=event['category_slug'],
                               date_from=dt.date.today().isoformat())[:3]
    favs = db.favorite_ids(g.user['id']) if g.user else set()
    return render_template('event.html', event=event, favs=favs,
                           similar=[s for s in similar if s['id'] != event_id])


# --- Регистрация и аутентификация -------------------------------------------

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        pwd = request.form.get('password', '')
        if len(name) < 3 or '@' not in email or len(pwd) < 6:
            flash('Проверьте корректность заполнения полей формы', 'error')
        elif db.query('SELECT 1 FROM users WHERE email = ?', (email,), one=True):
            flash('Пользователь с таким адресом уже зарегистрирован', 'error')
        else:
            uid = db.execute(
                'INSERT INTO users (full_name, email, password_hash, city_id)'
                ' VALUES (?, ?, ?, ?)',
                (name, email, generate_password_hash(pwd),
                 request.form.get('city_id') or None))
            session['user_id'] = uid
            flash('Регистрация завершена. Добро пожаловать!', 'ok')
            return redirect(url_for('catalog'))
    return render_template('register.html')


@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = db.query('SELECT * FROM users WHERE email = ?', (email,), one=True)
        if user and check_password_hash(user['password_hash'],
                                        request.form.get('password', '')):
            session.clear()
            session['user_id'] = user['id']
            return redirect(request.args.get('next') or url_for('catalog'))
        flash('Неверный адрес электронной почты или пароль', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('catalog'))


# --- Личный кабинет ----------------------------------------------------------

@app.route('/profile')
@login_required
def profile():
    favorites = db.user_favorites(g.user['id'])
    visits = db.user_visits(g.user['id'])
    now = dt.datetime.now()
    upcoming = [e for e in favorites if (_parse(e['starts_at']) or now) >= now]
    past = [e for e in favorites if (_parse(e['starts_at']) or now) < now]
    stats = {
        'planned': len(favorites),
        'visited': len(visits),
        'rated': len([v for v in visits if v['rating']]),
        'avg': round(sum(v['rating'] for v in visits if v['rating']) /
                     max(1, len([v for v in visits if v['rating']])), 1),
    }
    return render_template('profile.html', upcoming=upcoming, past=past,
                           visits=visits, stats=stats,
                           visited=db.visited_ids(g.user['id']),
                           favs=db.favorite_ids(g.user['id']))


@app.route('/api/favorites/<int:event_id>', methods=('POST',))
@login_required
def api_toggle_favorite(event_id):
    """Добавление мероприятия в список «Пойду» и удаление из него."""
    if db.get_event(event_id) is None:
        abort(404)
    added = db.toggle_favorite(g.user['id'], event_id)
    count = db.get_event(event_id)['fav_count']
    return jsonify({'added': added, 'count': count})


@app.route('/visits/<int:event_id>', methods=('POST',))
@login_required
def mark_visit(event_id):
    rating = request.form.get('rating')
    db.add_visit(g.user['id'], event_id,
                 int(rating) if rating else None,
                 request.form.get('comment', '').strip())
    flash('Мероприятие добавлено в историю посещений', 'ok')
    return redirect(request.referrer or url_for('profile'))


# --- Админ-панель ------------------------------------------------------------

@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', counters=db.counters(),
                           events=db.admin_events())


@app.route('/admin/moderation')
@admin_required
def moderation():
    return render_template('moderation.html',
                           pending=db.admin_events('pending'),
                           rejected=db.admin_events('rejected'),
                           counters=db.counters())


@app.route('/admin/moderation/<int:event_id>/<action>', methods=('POST',))
@admin_required
def moderate(event_id, action):
    if action not in ('publish', 'reject'):
        abort(400)
    if action == 'publish':
        db.set_status(event_id, 'published', g.user['id'])
        flash('Мероприятие опубликовано в каталоге', 'ok')
    else:
        db.set_status(event_id, 'rejected', g.user['id'],
                      request.form.get('reason', 'Не соответствует требованиям'))
        flash('Мероприятие отклонено', 'warn')
    return redirect(request.referrer or url_for('moderation'))


@app.route('/admin/events/new', methods=('GET', 'POST'))
@admin_required
def event_new():
    if request.method == 'POST':
        errors = validate_event(request.form)
        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            eid = save_event(request.form, None, g.user['id'])
            flash('Мероприятие сохранено (№%d)' % eid, 'ok')
            return redirect(url_for('admin'))
    return render_template('event_form.html', event=None)


@app.route('/admin/events/<int:event_id>/edit', methods=('GET', 'POST'))
@admin_required
def event_edit(event_id):
    event = db.get_event(event_id)
    if event is None:
        abort(404)
    if request.method == 'POST':
        errors = validate_event(request.form)
        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            save_event(request.form, event_id, g.user['id'])
            flash('Изменения сохранены', 'ok')
            return redirect(url_for('admin'))
    return render_template('event_form.html', event=event)


def validate_event(form):
    """Серверная проверка данных формы мероприятия."""
    errors = []
    if len(form.get('title', '').strip()) < 5:
        errors.append('Название должно содержать не менее 5 символов')
    if not form.get('venue', '').strip():
        errors.append('Укажите место проведения мероприятия')
    if _parse(form.get('starts_at', '')) is None:
        errors.append('Укажите корректную дату и время начала')
    if not form.get('is_free') and not form.get('price_min', '').isdigit():
        errors.append('Укажите цену билета или отметьте «бесплатное»')
    ends = _parse(form.get('ends_at', '')) if form.get('ends_at') else None
    starts = _parse(form.get('starts_at', ''))
    if ends and starts and ends < starts:
        errors.append('Дата окончания не может быть раньше даты начала')
    return errors


def save_event(form, event_id, admin_id):
    is_free = 1 if form.get('is_free') else 0
    values = (form['title'].strip(), form.get('summary', '').strip(),
              form.get('description', '').strip(), form['category_id'],
              form['city_id'], form['venue'].strip(),
              form.get('address', '').strip(),
              _parse(form['starts_at']).strftime('%Y-%m-%d %H:%M'),
              _parse(form['ends_at']).strftime('%Y-%m-%d %H:%M')
              if form.get('ends_at') else None,
              0 if is_free else int(form['price_min']), is_free,
              int(form.get('age_limit') or 0), form.get('status', 'pending'))
    if event_id:
        db.execute("""UPDATE events SET title=?, summary=?, description=?,
                      category_id=?, city_id=?, venue=?, address=?, starts_at=?,
                      ends_at=?, price_min=?, is_free=?, age_limit=?, status=?
                      WHERE id=?""", values + (event_id,))
        return event_id
    return db.execute("""INSERT INTO events (title, summary, description,
                         category_id, city_id, venue, address, starts_at,
                         ends_at, price_min, is_free, age_limit, status,
                         created_by)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      values + (admin_id,))


@app.route('/admin/events/<int:event_id>/delete', methods=('POST',))
@admin_required
def event_delete(event_id):
    db.execute('DELETE FROM events WHERE id = ?', (event_id,))
    flash('Мероприятие удалено', 'warn')
    return redirect(url_for('admin'))


@app.errorhandler(403)
def err403(e):
    return render_template('error.html', code=403,
                           text='Недостаточно прав для доступа к разделу'), 403


@app.errorhandler(404)
def err404(e):
    return render_template('error.html', code=404,
                           text='Запрашиваемая страница не найдена'), 404


if __name__ == '__main__':
    if not os.path.exists(db.DB_PATH):
        import seed
        seed.run()
    port = int(os.environ.get('AFISHA_PORT', 5000))
    app.run(host='127.0.0.1', port=port, debug=False)
