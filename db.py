# -*- coding: utf-8 -*-
"""Модуль доступа к данным веб-приложения «Афиша мероприятий»."""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'afisha.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')


def connect():
    """Создаёт соединение с базой данных и включает контроль целостности."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def query(sql, params=(), one=False):
    """Выполняет SELECT-запрос и возвращает список строк (или одну строку)."""
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    """Выполняет INSERT/UPDATE/DELETE и возвращает идентификатор записи."""
    with connect() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def init_db():
    """Создаёт структуру базы данных по сценарию schema.sql."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        script = f.read()
    with connect() as conn:
        conn.executescript(script)
        conn.commit()


# --- Выборка мероприятий с многокритериальной фильтрацией --------------------

EVENT_SELECT = """
SELECT e.id, e.title, e.summary, e.venue, e.starts_at, e.ends_at,
       e.price_min, e.is_free, e.age_limit, e.status, e.reject_reason,
       c.name AS category, c.slug AS category_slug, c.accent,
       t.name AS city,
       (SELECT COUNT(*) FROM favorites f WHERE f.event_id = e.id) AS fav_count
  FROM events e
  JOIN categories c ON c.id = e.category_id
  JOIN cities     t ON t.id = e.city_id
"""


def search_events(date_from=None, date_to=None, city=None, category=None,
                  q=None, only_free=False, sort='date', status='published'):
    """Возвращает мероприятия, отобранные по дате, городу и категории."""
    sql = EVENT_SELECT + ' WHERE 1 = 1'
    params = []
    if status:
        sql += ' AND e.status = ?'
        params.append(status)
    if date_from:
        sql += ' AND date(e.starts_at) >= date(?)'
        params.append(date_from)
    if date_to:
        sql += ' AND date(e.starts_at) <= date(?)'
        params.append(date_to)
    if city:
        sql += ' AND t.slug = ?'
        params.append(city)
    if category:
        sql += ' AND c.slug = ?'
        params.append(category)
    if q:
        sql += ' AND (e.title LIKE ? OR e.summary LIKE ? OR e.venue LIKE ?)'
        params += ['%%%s%%' % q] * 3
    if only_free:
        sql += ' AND e.is_free = 1'
    sql += {
        'date': ' ORDER BY e.starts_at',
        'price': ' ORDER BY e.price_min, e.starts_at',
        'popular': ' ORDER BY fav_count DESC, e.starts_at',
    }.get(sort, ' ORDER BY e.starts_at')
    return query(sql, tuple(params))


def get_event(event_id):
    """Возвращает полную карточку мероприятия по его идентификатору."""
    return query("""
        SELECT e.*, c.name AS category, c.slug AS category_slug, c.accent,
               t.name AS city, t.slug AS city_slug,
               (SELECT COUNT(*) FROM favorites f WHERE f.event_id = e.id) AS fav_count
          FROM events e
          JOIN categories c ON c.id = e.category_id
          JOIN cities     t ON t.id = e.city_id
         WHERE e.id = ?""", (event_id,), one=True)


def cities():
    return query('SELECT * FROM cities ORDER BY name')


def categories():
    return query('SELECT * FROM categories ORDER BY id')


# --- «Пойду» и история посещений --------------------------------------------

def favorite_ids(user_id):
    rows = query('SELECT event_id FROM favorites WHERE user_id = ?', (user_id,))
    return {r['event_id'] for r in rows}


def toggle_favorite(user_id, event_id):
    """Добавляет мероприятие в список «Пойду» либо удаляет его оттуда."""
    exists = query('SELECT 1 FROM favorites WHERE user_id = ? AND event_id = ?',
                   (user_id, event_id), one=True)
    if exists:
        execute('DELETE FROM favorites WHERE user_id = ? AND event_id = ?',
                (user_id, event_id))
        return False
    execute('INSERT INTO favorites (user_id, event_id) VALUES (?, ?)',
            (user_id, event_id))
    return True


def user_favorites(user_id):
    return query(EVENT_SELECT + """
        JOIN favorites f ON f.event_id = e.id AND f.user_id = ?
         WHERE e.status = 'published'
         ORDER BY e.starts_at""", (user_id,))


def user_visits(user_id):
    return query("""
        SELECT v.id, v.visited_at, v.rating, v.comment,
               e.id AS event_id, e.title, e.venue, e.starts_at,
               c.name AS category, c.accent, t.name AS city
          FROM visits v
          JOIN events     e ON e.id = v.event_id
          JOIN categories c ON c.id = e.category_id
          JOIN cities     t ON t.id = e.city_id
         WHERE v.user_id = ?
         ORDER BY v.visited_at DESC""", (user_id,))


def visited_ids(user_id):
    rows = query('SELECT event_id FROM visits WHERE user_id = ?', (user_id,))
    return {r['event_id'] for r in rows}


def add_visit(user_id, event_id, rating=None, comment=''):
    execute("""INSERT OR REPLACE INTO visits (user_id, event_id, rating, comment)
               VALUES (?, ?, ?, ?)""", (user_id, event_id, rating, comment))


# --- Администрирование и модерация ------------------------------------------

def admin_events(status=None):
    sql = EVENT_SELECT
    params = ()
    if status:
        sql += ' WHERE e.status = ?'
        params = (status,)
    return query(sql + ' ORDER BY e.created_at DESC', params)


def set_status(event_id, status, admin_id, reason=None):
    """Публикует либо отклоняет мероприятие (операция модерации)."""
    execute("""UPDATE events
                  SET status = ?, reject_reason = ?,
                      moderated_by = ?, moderated_at = datetime('now')
                WHERE id = ?""", (status, reason, admin_id, event_id))


def counters():
    row = query("""
        SELECT (SELECT COUNT(*) FROM events WHERE status = 'published')  AS published,
               (SELECT COUNT(*) FROM events WHERE status = 'pending')    AS pending,
               (SELECT COUNT(*) FROM events WHERE status = 'rejected')   AS rejected,
               (SELECT COUNT(*) FROM users)                              AS users,
               (SELECT COUNT(*) FROM favorites)                          AS favorites,
               (SELECT COUNT(*) FROM visits)                             AS visits
        """, one=True)
    return dict(row)
