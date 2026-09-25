import re
import sqlite3
import pytest
from app import create_app
from services import make_draft


@pytest.fixture
def app(tmp_path):
    return create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': str(tmp_path / 'test.sqlite')})


@pytest.fixture
def client(app):
    return app.test_client()


def payload(client, **changes):
    page = client.get('/requests/new').get_data(as_text=True)
    data = {name: re.search(f'name="{name}" value="([^"]+)"', page).group(1) for name in ['csrf', 'submission']}
    data.update(person='Соколовы', region='Саратовская губерния', period='1890-1910',
                details='По семейным воспоминаниям жили в селе. Точное название пока неизвестно.')
    data.update(changes)
    return data


def count(app):
    with sqlite3.connect(app.config['DATABASE']) as db:
        return db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]


def test_create_and_read(client, app):
    result = client.post('/requests/new', data=payload(client))
    assert result.status_code == 303
    page = client.get(result.location).get_data(as_text=True)
    assert 'Соколовы' in page and 'Черновик обращения' in page
    assert count(app) == 1


@pytest.mark.parametrize('field,value', [('person', '   '), ('region', '\t  '), ('details', 'коротко'),
                                        ('person', 'я' * 121), ('period', '1' * 61), ('details', 'я' * 2001)])
def test_invalid_input_preserves_other_fields(client, app, field, value):
    response = client.post('/requests/new', data=payload(client, **{field: value}))
    assert response.status_code == 422
    assert 'Проверьте заполнение' in response.get_data(as_text=True)
    assert 'Саратовская губерния' in response.get_data(as_text=True) or field == 'region'
    assert count(app) == 0


def test_duplicate_post_creates_one_row(client, app):
    data = payload(client)
    first = client.post('/requests/new', data=data)
    second = client.post('/requests/new', data=data)
    assert first.location == second.location
    assert count(app) == 1


def test_csrf_is_required(client, app):
    data = payload(client)
    data['csrf'] = 'incorrect'
    assert client.post('/requests/new', data=data).status_code == 400
    assert count(app) == 0


@pytest.mark.parametrize('token', ['неверный токен', '🔒', ''])
def test_malformed_csrf_is_rejected_without_crash(client, app, token):
    data = payload(client)
    data['csrf'] = token
    assert client.post('/requests/new', data=data).status_code == 400
    assert count(app) == 0


def test_status_and_filter(client):
    data = payload(client)
    location = client.post('/requests/new', data=data).location
    result = client.post(location + '/status', data={'csrf': data['csrf'], 'status': 'in_progress'})
    assert result.status_code == 303
    assert 'Соколовы' in client.get('/?status=in_progress').get_data(as_text=True)
    assert 'Соколовы' not in client.get('/?status=new').get_data(as_text=True)
    assert client.post(location + '/status', data={'csrf': data['csrf'], 'status': 'wrong'}).status_code == 400


def test_other_session_cannot_read_or_change(app, client):
    location = client.post('/requests/new', data=payload(client)).location
    other = app.test_client()
    other_data = payload(other)
    assert other.get(location).status_code == 404
    assert 'Соколовы' not in other.get('/').get_data(as_text=True)
    assert other.post(location + '/status', data={'csrf': other_data['csrf'], 'status': 'done'}).status_code == 404


def test_html_is_escaped(client):
    location = client.post('/requests/new', data=payload(client, person='<script>alert(1)</script>')).location
    page = client.get(location).get_data(as_text=True)
    assert '<script>alert(1)</script>' not in page
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page


def test_sql_like_text_is_data(client, app):
    text = "Соколов'); DROP TABLE requests; --"
    location = client.post('/requests/new', data=payload(client, person=text)).location
    assert client.get(location).status_code == 200
    assert count(app) == 1


def test_unknown_period_is_not_invented(client):
    location = client.post('/requests/new', data=payload(client, period='')).location
    assert 'не указан, требуется уточнение' in client.get(location).get_data(as_text=True)


def test_draft_keeps_source_uncertainty():
    draft = make_draft({'person': 'Соколовы', 'region': 'Неизвестно', 'period': '',
                        'details': 'Возможно, жили рядом с рекой. Источник: семейный рассказ.'})
    assert 'Возможно' in draft and 'семейный рассказ' in draft
    assert 'не указан, требуется уточнение' in draft


def test_unknown_page_and_filter(client):
    assert client.get('/requests/9999').status_code == 404
    assert client.get('/?status=invalid').status_code == 400


def test_bad_submission(client, app):
    assert client.post('/requests/new', data=payload(client, submission='bad')).status_code == 400
    assert count(app) == 0


def test_oversized_body(client):
    assert client.post('/requests/new', data={'details': 'x' * 40000}).status_code == 413


def test_persistence_after_restart(client, app):
    location = client.post('/requests/new', data=payload(client)).location
    cookie = client.get_cookie('session')
    restarted = create_app({'TESTING': True, 'SECRET_KEY': 'test-only', 'DATABASE': app.config['DATABASE']})
    browser = restarted.test_client()
    browser.set_cookie('session', cookie.value)
    assert 'Соколовы' in browser.get(location).get_data(as_text=True)
