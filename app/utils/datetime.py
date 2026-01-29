from datetime import datetime


def human_delta(dt1: datetime, dt2: datetime) -> str:
    """
    Возвращает разницу между dt1 и dt2 в виде строки в формате "когда":
    прошедшее -> "21 день назад"
    будущее -> "через 12 недель"
    """
    delta_seconds = int((dt2 - dt1).total_seconds())
    past = delta_seconds > 0
    delta_seconds = abs(delta_seconds)

    intervals = [
        ("год", 365 * 24 * 60 * 60),
        ("месяц", 30 * 24 * 60 * 60),
        ("неделя", 7 * 24 * 60 * 60),
        ("день", 24 * 60 * 60),
        ("час", 60 * 60),
        ("минута", 60),
        ("секунда", 1),
    ]

    for name, seconds_in_unit in intervals:
        if delta_seconds >= seconds_in_unit:
            value = delta_seconds // seconds_in_unit

            # Функция для выбора падежа
            def choose_word(name, value, past):
                # прошедшее -> родительный, будущее -> винительный
                if name == "год":
                    return (
                        (
                            "год"
                            if value % 10 == 1 and value % 100 != 11
                            else "года" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "лет"
                        )
                        if past
                        else "год" if value == 1 else "года" if 2 <= value <= 4 else "лет"
                    )
                if name == "месяц":
                    return (
                        (
                            "месяц"
                            if value % 10 == 1 and value % 100 != 11
                            else "месяца" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "месяцев"
                        )
                        if past
                        else "месяц" if value == 1 else "месяца" if 2 <= value <= 4 else "месяцев"
                    )
                if name == "неделя":
                    return (
                        (
                            "неделя"
                            if value % 10 == 1 and value % 100 != 11
                            else "недели" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "недель"
                        )
                        if past
                        else (
                            "неделю"
                            if value % 10 == 1 and value % 100 != 11
                            else "недели" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "недель"
                        )
                    )
                if name == "день":
                    return (
                        (
                            "день"
                            if value % 10 == 1 and value % 100 != 11
                            else "дня" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "дней"
                        )
                        if past
                        else (
                            "день"
                            if value % 10 == 1 and value % 100 != 11
                            else "дня" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "дней"
                        )
                    )
                if name == "час":
                    return (
                        (
                            "час"
                            if value % 10 == 1 and value % 100 != 11
                            else "часа" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "часов"
                        )
                        if past
                        else "час" if value == 1 else "часа" if 2 <= value <= 4 else "часов"
                    )
                if name == "минута":
                    return (
                        (
                            "минута"
                            if value % 10 == 1 and value % 100 != 11
                            else "минуты" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "минут"
                        )
                        if past
                        else (
                            "минуту"
                            if value % 10 == 1 and value % 100 != 11
                            else "минуты" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "минут"
                        )
                    )
                if name == "секунда":
                    return (
                        (
                            "секунда"
                            if value % 10 == 1 and value % 100 != 11
                            else "секунды" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "секунд"
                        )
                        if past
                        else (
                            "секунду"
                            if value % 10 == 1 and value % 100 != 11
                            else "секунды" if 2 <= value % 10 <= 4 and not 12 <= value % 100 <= 14 else "секунд"
                        )
                    )

            word = choose_word(name, value, past)
            return f"{value} {word} назад" if past else f"через {value} {word}"

    return "только что"
