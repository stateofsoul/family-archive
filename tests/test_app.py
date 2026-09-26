import re
import sqlite3

import pytest

from app import create_app
from services import make_draft


@pytest.fixture
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test-key",
        "DATABASE": str(tmp_path / "test.sqlite"),
    })


@pytest.fixture
def client(app):
    return app.test_client()


def form_data(client, **changes):
    page = client.get("/requests/new").get_data(as_text=True)
    csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
    submission = re.search(r'name="submission" value="([^"]+)"', page).group(1)

    data = {
        "csrf": csrf,
        "submission": submission,
        "person": "Соколовы",
        "region": "Саратовская губерния",
        "period": "1890-1910",
        "details": "По семейным воспоминаниям жили в селе. Точное название пока неизвестно.",
    }
    data.update(changes)
    return data


def row_count(app):
    with sqlite3.connect(app.config["DATABASE"]) as db:
        return db.execute("SELECT COUNT(*) FROM requests").fetchone()[0]


def test_create_request(client, app):
    response = client.post("/requests/new", data=form_data(client))

    assert response.status_code == 303
    assert row_count(app) == 1

    page = client.get(response.location).get_data(as_text=True)
    assert "Соколовы" in page
    assert "Черновик обращения" in page


def test_validation_keeps_entered_data(client, app):
    response = client.post(
        "/requests/new",
        data=form_data(client, details="коротко"),
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 422
    assert "Проверьте заполнение" in page
    assert "Саратовская губерния" in page
    assert row_count(app) == 0


def test_spaces_do_not_count_as_value(client, app):
    response = client.post(
        "/requests/new",
        data=form_data(client, person="   "),
    )

    assert response.status_code == 422
    assert row_count(app) == 0


def test_duplicate_submit_does_not_create_second_row(client, app):
    data = form_data(client)

    first = client.post("/requests/new", data=data)
    client.get(first.location)
    second = client.post("/requests/new", data=data)

    assert first.location == second.location
    assert row_count(app) == 1
    assert "Эта заявка уже была сохранена." in client.get(second.location).get_data(as_text=True)


def test_csrf_is_required(client, app):
    data = form_data(client)
    data["csrf"] = "wrong"

    response = client.post("/requests/new", data=data)

    assert response.status_code == 400
    assert row_count(app) == 0


def test_unicode_csrf_returns_400(client, app):
    data = form_data(client)
    data["csrf"] = "неверный токен"

    response = client.post("/requests/new", data=data)

    assert response.status_code == 400
    assert row_count(app) == 0


def test_status_change_and_filter(client):
    data = form_data(client)
    location = client.post("/requests/new", data=data).location

    response = client.post(
        location + "/status",
        data={"csrf": data["csrf"], "status": "in_progress"},
    )

    assert response.status_code == 303
    assert "Соколовы" in client.get("/?status=in_progress").get_data(as_text=True)
    assert "Соколовы" not in client.get("/?status=new").get_data(as_text=True)


def test_invalid_status_returns_400(client):
    data = form_data(client)
    location = client.post("/requests/new", data=data).location

    response = client.post(
        location + "/status",
        data={"csrf": data["csrf"], "status": "unknown"},
    )

    assert response.status_code == 400


def test_other_browser_cannot_open_or_change_request(app, client):
    location = client.post("/requests/new", data=form_data(client)).location
    other_client = app.test_client()
    other_data = form_data(other_client)

    assert other_client.get(location).status_code == 404
    assert "Соколовы" not in other_client.get("/").get_data(as_text=True)

    response = other_client.post(
        location + "/status",
        data={"csrf": other_data["csrf"], "status": "done"},
    )
    assert response.status_code == 404


def test_html_is_escaped(client):
    location = client.post(
        "/requests/new",
        data=form_data(client, person="<script>alert(1)</script>"),
    ).location
    page = client.get(location).get_data(as_text=True)

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_empty_period_is_not_invented(client):
    location = client.post(
        "/requests/new",
        data=form_data(client, period=""),
    ).location

    page = client.get(location).get_data(as_text=True)
    assert "не указан, требуется уточнение" in page


def test_unknown_request_and_filter_return_error(client):
    assert client.get("/requests/9999").status_code == 404
    assert client.get("/?status=unknown").status_code == 400


def test_field_limits(client, app):
    response = client.post(
        "/requests/new",
        data=form_data(client, person="я" * 121),
    )

    assert response.status_code == 422
    assert "максимум 120 символов" in response.get_data(as_text=True)
    assert row_count(app) == 0


def test_draft_keeps_source_text():
    draft = make_draft({
        "person": "Соколовы",
        "region": "Неизвестно",
        "period": "",
        "details": "Возможно, жили рядом с рекой. Источник: семейный рассказ.",
    })

    assert "Возможно, жили рядом с рекой" in draft
    assert "Источник: семейный рассказ" in draft
    assert "не указан, требуется уточнение" in draft


@pytest.mark.parametrize("field,maximum", [
    ("person", 120), ("region", 120), ("period", 60), ("details", 2000),
])
def test_each_field_boundary(client, app, field, maximum):
    accepted = client.post("/requests/new", data=form_data(client, **{field: "я" * maximum}))
    rejected = client.post("/requests/new", data=form_data(client, **{field: "я" * (maximum + 1)}))
    assert accepted.status_code == 303
    assert rejected.status_code == 422
    assert row_count(app) == 1


def test_invalid_status_does_not_change_saved_value(client):
    data = form_data(client)
    location = client.post("/requests/new", data=data).location
    client.post(location + "/status", data={"csrf": data["csrf"], "status": "unknown"})
    assert "Соколовы" in client.get("/?status=new").get_data(as_text=True)


def test_database_is_closed_after_requests(client, monkeypatch):
    real_connect = sqlite3.connect
    connections = []

    def tracked_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
    location = client.post("/requests/new", data=form_data(client)).location
    client.get(location)
    client.get("/")
    assert connections
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def test_oversized_body_is_rejected(client, app):
    response = client.post("/requests/new", data=form_data(client, details="я" * 40000))
    assert response.status_code == 413
    assert row_count(app) == 0


def test_pages_are_not_cached(client):
    response = client.get("/")
    assert response.headers["Cache-Control"] == "no-store"
