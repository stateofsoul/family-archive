"""Локальный сервис для работы с архивными заявками."""

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from services import make_draft, validate_request


STATUSES = {
    "new": "Новая",
    "in_progress": "В работе",
    "done": "Завершена",
}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    secret_key = (test_config or {}).get("SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not secret_key:
        key_path = Path(app.instance_path) / "secret.key"
        if not key_path.exists():
            key_path.write_text(secrets.token_hex(32), encoding="utf-8")
        secret_key = key_path.read_text(encoding="utf-8").strip()

    app.config.update(
        SECRET_KEY=secret_key,
        DATABASE=str(Path(app.instance_path) / "archive.sqlite"),
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config:
        app.config.update(test_config)

    @contextmanager
    def connect():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    with connect() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY,
                owner TEXT NOT NULL,
                submission TEXT NOT NULL,
                person TEXT NOT NULL,
                region TEXT NOT NULL,
                period TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created TEXT NOT NULL,
                UNIQUE(owner, submission)
            )"""
        )

    @app.before_request
    def prepare_session():
        session.setdefault("owner", secrets.token_hex(24))
        session.setdefault("csrf", secrets.token_hex(24))

        if request.method == "POST":
            token = request.form.get("csrf", "")
            if not token.isascii() or not secrets.compare_digest(token, session["csrf"]):
                abort(400, description="Форма устарела. Обновите страницу и повторите действие.")

    @app.after_request
    def prevent_page_cache(response):
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def shared_values():
        return {"statuses": STATUSES}

    def get_owned_request(request_id):
        with connect() as db:
            row = db.execute(
                "SELECT * FROM requests WHERE id=? AND owner=?",
                (request_id, session["owner"]),
            ).fetchone()

        if row is None:
            abort(404)
        return row

    @app.get("/")
    def index():
        selected = request.args.get("status", "")
        if selected and selected not in STATUSES:
            abort(400, description="Неизвестный статус.")

        with connect() as db:
            rows = db.execute(
                "SELECT * FROM requests WHERE owner=? ORDER BY id DESC",
                (session["owner"],),
            ).fetchall()

        counts = {
            status: sum(row["status"] == status for row in rows)
            for status in STATUSES
        }
        visible_rows = [
            row for row in rows
            if not selected or row["status"] == selected
        ]

        return render_template(
            "index.html",
            rows=visible_rows,
            counts=counts,
            total=len(rows),
            selected=selected,
        )

    @app.route("/requests/new", methods=["GET", "POST"])
    def new_request():
        values = {}
        errors = {}
        submission = (
            request.form.get("submission", "")
            if request.method == "POST"
            else secrets.token_hex(16)
        )

        if request.method == "POST":
            values, errors = validate_request(request.form)

            if len(submission) != 32 or any(
                char not in "0123456789abcdef" for char in submission
            ):
                abort(400, description="Некорректная форма. Откройте её заново.")

            if not errors:
                with connect() as db:
                    cursor = db.execute(
                        """INSERT INTO requests
                            (owner, submission, person, region, period, details, created)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(owner, submission) DO NOTHING""",
                        (
                            session["owner"],
                            submission,
                            values["person"],
                            values["region"],
                            values["period"],
                            values["details"],
                            datetime.now().strftime("%d.%m.%Y"),
                        ),
                    )
                    row = db.execute(
                        "SELECT id FROM requests WHERE owner=? AND submission=?",
                        (session["owner"], submission),
                    ).fetchone()

                if cursor.rowcount == 1:
                    flash("Заявка сохранена.")
                else:
                    flash("Эта заявка уже была сохранена.")

                return redirect(url_for("detail", request_id=row["id"]), code=303)

        return (
            render_template(
                "form.html",
                values=values,
                errors=errors,
                submission=submission,
            ),
            422 if errors else 200,
        )

    @app.get("/requests/<int:request_id>")
    def detail(request_id):
        row = get_owned_request(request_id)
        return render_template("detail.html", row=row, draft=make_draft(row))

    @app.post("/requests/<int:request_id>/status")
    def change_status(request_id):
        get_owned_request(request_id)
        status = request.form.get("status", "")

        if status not in STATUSES:
            abort(400, description="Неизвестный статус.")

        with connect() as db:
            db.execute(
                "UPDATE requests SET status=? WHERE id=? AND owner=?",
                (status, request_id, session["owner"]),
            )

        flash("Статус сохранён.")
        return redirect(url_for("detail", request_id=request_id), code=303)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        messages = {
            404: "Заявка не найдена или недоступна в этом браузере.",
            413: "Слишком много данных. Сократите текст и попробуйте ещё раз.",
        }
        return (
            render_template(
                "error.html",
                code=error.code,
                message=messages.get(error.code, error.description),
            ),
            error.code,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
