import re

ALLOWED_PWD_PATTERN = re.compile(r'^[a-zA-Zа-яА-ЯёЁ0-9 !"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]+$')
ALLOWED_LOGIN_PATTERN = re.compile(r"^(?:[A-Za-z][A-Za-z0-9_]*|[А-Яа-яЁё][А-Яа-яЁё0-9_]*)$")


def validate_confirmation_password(password: str, confirm_password: str) -> bool:
    """Проверяет совпадение паролей"""
    return password == confirm_password


def validate_correct_password(password: str) -> None | str:
    """
    Проверяет валидность пароля

    Args:
        password (str): Пароль

    Returns:
        None | str: None, если пароль валиден, иначе текст ошибки
    """
    # Проверка длины пароля
    if len(password) < 6 or len(password) > 20:
        return "Длина пароля должна быть от 6 до 20 символов"

    # Проверка на содержание корректных символов
    if not ALLOWED_PWD_PATTERN.match(password):
        return "Пароль содержит недопустимые символы"

    # Все проверки прошли успешно
    return None


def validate_corrent_login(login: str) -> None | str:
    """
    Проверяет валидность логина

    Args:
        login (str): Логин

    Returns:
        None | str: None, если логин валиден, иначе текст ошибки
    """
    # Проверка длины логина
    if len(login) < 3 or len(login) > 32:
        return "Длина логина должна быть от 3 до 32 символов"

    # Проверка на содержание корректных символов
    if not ALLOWED_LOGIN_PATTERN.match(login):
        return "Логин содержит недопустимые символы"

    # Все проверки прошли успешно
    return None


def validate_correct_model_name(model_name: str) -> None | str:
    """
    Проверяет валидность названия модели

    Args:
        model_name (str): Название модели

    Returns:
        None | str: None, если название модели валидно, иначе текст ошибки
    """
    # Проверка длины названия модели
    if len(model_name) < 3 or len(model_name) > 120:
        return "Длина названия модели должна быть от 3 до 120 символов"

    # Все проверки прошли успешно
    return None
