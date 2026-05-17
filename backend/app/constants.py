"""Константы приложения."""


class HTTPStatus:
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500


class ErrorMessages:
    INVALID_CREDENTIALS = "Неверный пароль"
    UNAUTHORIZED = "Требуется аутентификация"
    FORBIDDEN = "Доступ запрещен"
    VALIDATION_ERROR = "Ошибка валидации данных"
    INTERNAL_ERROR = "Внутренняя ошибка сервера"
    CAMPAIGN_NOT_FOUND = "Кампания не найдена"
    JOB_NOT_FOUND = "Задача не найдена"
    BOT_NOT_FOUND = "Бот не найден"
    ACCOUNT_NOT_FOUND = "Аккаунт не найден"


class SuccessMessages:
    LOGIN_SUCCESS = "Успешный вход"
    CAMPAIGN_CREATED = "Кампания создана"
    CAMPAIGN_UPDATED = "Кампания обновлена"
    CAMPAIGN_DELETED = "Кампания удалена"
    JOB_STARTED = "Задача создания ботов поставлена в очередь"
    ACCOUNT_UPLOADED = "Аккаунт загружен"
    BOT_CREATED = "Бот создан"
    BOT_UPDATED = "Бот обновлён"
    BOT_DELETED = "Бот удалён"
