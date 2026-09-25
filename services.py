"""Проверка полей и сборка письма. Здесь нет обращения к внешнему AI API."""
LIMITS = {"person": (2, 120), "region": (2, 120), "period": (0, 60), "details": (20, 2000)}
LABELS = {"person": "Имя или фамилия", "region": "Место поиска", "period": "Период", "details": "Что уже известно"}


def validate_request(form):
    values, errors = {}, {}
    for field, (minimum, maximum) in LIMITS.items():
        text = form.get(field, "").strip()
        if field != "details":
            text = " ".join(text.split())
        values[field] = text
        if len(text) < minimum:
            errors[field] = f"{LABELS[field]}: нужно не меньше {minimum} символов."
        elif len(text) > maximum:
            errors[field] = f"{LABELS[field]}: максимум {maximum} символов."
    return values, errors


def make_draft(data):
    period = data["period"] or "не указан, требуется уточнение"
    return (
        "Здравствуйте!\n\n"
        "Прошу уточнить, есть ли в вашем архиве документы для исследования семейной истории.\n\n"
        f"Человек или семья: {data['person']}\n"
        f"Место поиска: {data['region']}\n"
        f"Период: {period}\n\n"
        f"Исходные сведения со слов заявителя:\n{data['details']}\n\n"
        "Подскажите, пожалуйста, возможен ли поиск по этим сведениям и какие уточнения потребуются.\n\n"
        "Спасибо!"
    )
