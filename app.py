"""Небольшой локальный сервис для работы с архивными запросами."""
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from services import make_draft, validate_request

STATUSES = {"new": "Новая", "in_progress": "В работе", "done": "Завершена"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    # Один ключ на локальную установку: перезапуск не теряет сессию браузера.
    key_path = Path(app.instance_path) / "secret.key"
    if not key_path.exists():
        key_path.write_text(secrets.token_hex(32), encoding="utf-8")
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or key_path.read_text().strip(),
        DATABASE=str(Path(app.instance_path) / "archive.sqlite"),
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    def connect():
        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        return db

    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY, owner TEXT NOT NULL,
            submission TEXT NOT NULL, person TEXT NOT NULL,
            region TEXT NOT NULL, period TEXT NOT NULL, details TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new', created TEXT NOT NULL,
            UNIQUE(owner, submission)
        )""")

    @app.before_request
    def protect_forms():
        session.setdefault("owner", secrets.token_hex(24))
        session.setdefault("csrf", secrets.token_hex(24))
        if request.method == "POST":
            token = request.form.get("csrf", "")
            if not token.isascii() or not secrets.compare_digest(token, session["csrf"]):
                abort(400, description="Форма устарела. Обновите страницу и повторите действие.")

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def shared():
        return {"statuses": STATUSES}

    def owned_request(request_id):
        with connect() as db:
            row = db.execute("SELECT * FROM requests WHERE id=? AND owner=?",
                             (request_id, session["owner"])).fetchone()
        if row is None:
            abort(404)
        return row

    @app.get("/")
    def index():
        selected = request.args.get("status", "")
        if selected and selected not in STATUSES:
            abort(400, description="Неизвестный статус.")
        with connect() as db:
            rows = db.execute("SELECT * FROM requests WHERE owner=? ORDER BY id DESC",
                              (session["owner"],)).fetchall()
        counts = {status: sum(row["status"] == status for row in rows) for status in STATUSES}
        visible = [row for row in rows if not selected or row["status"] == selected]
        return render_template("index.html", rows=visible, counts=counts,
                               total=len(rows), selected=selected)

    @app.route("/requests/new", methods=["GET", "POST"])
    def new_request():
        values, errors = {}, {}
        submission = request.form.get("submission", "") if request.method == "POST" else secrets.token_hex(16)
        if request.method == "POST":
            values, errors = validate_request(request.form)
            if len(submission) != 32 or any(c not in "0123456789abcdef" for c in submission):
                abort(400, description="Некорректная форма. Откройте её заново.")
            if not errors:
                # UNIQUE защищает от двойного клика и повторной отправки того же POST.
                with connect() as db:
                    db.execute("""INSERT INTO requests
                        (owner, submission, person, region, period, details, created)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(owner, submission) DO NOTHING""",
                        (session["owner"], submission, values["person"], values["region"],
                         values["period"], values["details"], datetime.now().strftime("%d.%m.%Y")))
                    row = db.execute("SELECT id FROM requests WHERE owner=? AND submission=?",
                                     (session["owner"], submission)).fetchone()
                flash("Заявка сохранена. Теперь можно проверить черновик обращения.")
                return redirect(url_for("detail", request_id=row["id"]), code=303)
        return render_template("form.html", values=values, errors=errors,
                               submission=submission), (422 if errors else 200)

    @app.get("/requests/<int:request_id>")
    def detail(request_id):
        row = owned_request(request_id)
        return render_template("detail.html", row=row, draft=make_draft(row))

    @app.post("/requests/<int:request_id>/status")
    def change_status(request_id):
        owned_request(request_id)
        status = request.form.get("status", "")
        if status not in STATUSES:
            abort(400, description="Неизвестный статус.")
        with connect() as db:
            db.execute("UPDATE requests SET status=? WHERE id=? AND owner=?",
                       (status, request_id, session["owner"]))
        flash("Статус обновлён.")
        return redirect(url_for("detail", request_id=request_id), code=303)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        messages = {404: "Заявка не найдена или недоступна в этом браузере.",
                    413: "Слишком много данных. Сократите текст и попробуйте ещё раз."}
        return render_template("error.html", code=error.code,
                               message=messages.get(error.code, error.description)), error.code

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
