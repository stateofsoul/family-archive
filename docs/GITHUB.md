# Как загрузить проект на GitHub

Автоматическая загрузка из чата не выполнена: GitHub вернул 403 Resource not accessible by integration при создании ветки. Это ограничение подключённой интеграции, а не ошибка проекта.

## Через браузер

1. Войдите в свой аккаунт GitHub и откройте https://github.com/new.
2. Назовите репозиторий `family-archive`.
3. Описание: `Учебный сервис архивных запросов на Flask: формы, SQLite и тесты`.
4. Выберите Public, если хотите показывать проект работодателю. Не добавляйте автоматически README, лицензию или .gitignore: README и .gitignore уже есть в проекте.
5. Нажмите Create repository.
6. На странице нового репозитория выберите uploading an existing file.
7. Перетащите содержимое распакованной папки проекта: app.py, services.py, README.md, requirements.txt, requirements-dev.txt, START_WINDOWS.bat, .gitignore и папки templates, static, tests, docs.
8. Не загружайте .venv, instance, __pycache__ или .pytest_cache. Они появятся при локальном запуске, но в подготовленном ZIP их нет.
9. Сообщение коммита: `Добавлен сервис архивных запросов`.
10. Нажмите Commit changes. Проверьте, что README виден на главной странице, а файлы проекта находятся рядом с ним.

GitHub хранит код. Flask-приложение после загрузки не становится работающим сайтом на GitHub Pages. Для показа запускайте его локально по README.
