import { formatWaitLabel, getFloodWaitSeconds, isFloodWaitError } from './floodWait';

/** Человекочитаемые названия полей API (body.*). */
const FIELD_LABELS = {
  password: 'Пароль',
  target_url: 'Ссылка на сервис',
  display_name: 'Название бота',
  username: 'Username бота',
  description: 'Описание бота',
  about_text: 'Текст «О боте»',
  welcome_message: 'Приветственное сообщение',
  welcome_button_text: 'Текст кнопки',
  welcome_button_enabled: 'Кнопка в приветствии',
  link_mode: 'Тип ссылки',
  keyword: 'Ключевая фраза',
  title: 'Название кампании',
  resource_url: 'URL ресурса',
  referral_endpoint_url: 'URL referral API',
  referral_api_key: 'Ключ referral API',
  niche_description: 'Описание ниши',
  campaign_id: 'Кампания',
  telegram_account_id: 'Telegram-аккаунт',
  new_password: 'Новый пароль',
  current_password: 'Текущий пароль',
  label: 'Название аккаунта',
  bots: 'Список ботов',
};

const TYPE_HINTS = {
  missing: 'поле обязательно',
  string_type: 'ожидается текст',
  string_too_short: 'слишком короткое значение',
  string_too_long: 'слишком длинное значение',
  value_error: 'некорректное значение',
  url_parsing: 'некорректный URL',
  int_parsing: 'ожидается число',
  bool_parsing: 'ожидается да/нет',
  enum: 'недопустимое значение',
  greater_than_equal: 'значение слишком мало',
  less_than_equal: 'значение слишком велико',
};

const STATUS_FALLBACKS = {
  400: 'Некорректный запрос',
  401: 'Требуется вход в систему',
  403: 'Доступ запрещён',
  404: 'Не найдено',
  409: 'Конфликт данных',
  422: 'Ошибка проверки данных',
  429: 'Слишком много запросов',
  500: 'Внутренняя ошибка сервера',
  502: 'Сервер временно недоступен',
  503: 'Сервис перегружен',
  504: 'Превышено время ожидания ответа сервера',
};

function fieldLabel(loc) {
  if (!Array.isArray(loc) || !loc.length) return '';
  const path = loc.filter((part) => part !== 'body' && typeof part === 'string');
  const key = path[path.length - 1];
  if (key == null) return '';
  if (typeof key === 'number') return `элемент #${key + 1}`;
  return FIELD_LABELS[key] || key.replace(/_/g, ' ');
}

function validationDetailMessage(detail) {
  if (!detail || typeof detail !== 'object') return '';
  const label = fieldLabel(detail.loc);
  const typeHint = TYPE_HINTS[detail.type] || '';
  let msg = String(detail.msg || '').trim();

  if (msg.includes('String should have at least')) {
    msg = 'слишком короткое значение';
  } else if (msg.includes('String should have at most')) {
    msg = 'слишком длинное значение';
  } else if (msg.includes('Field required')) {
    msg = 'поле обязательно';
  } else if (msg.includes('Input should be a valid URL')) {
    msg = 'некорректный URL';
  }

  const text = typeHint && !msg.toLowerCase().includes(typeHint) ? typeHint : msg || typeHint;
  if (label && text) return `${label}: ${text}`;
  return label || text;
}

function formatValidationErrors(data) {
  const details = data?.details;
  if (!Array.isArray(details) || !details.length) return '';
  const messages = details
    .map(validationDetailMessage)
    .filter(Boolean);
  if (!messages.length) return '';
  const unique = [...new Set(messages)];
  const shown = unique.slice(0, 3);
  const suffix = unique.length > 3 ? ` (и ещё ${unique.length - 3})` : '';
  return shown.join('; ') + suffix;
}

function formatFloodWait(err, data) {
  const seconds = getFloodWaitSeconds(err);
  const base = data?.error || 'Лимит Telegram / BotFather';
  if (seconds != null) {
    return `${base}. Подождите ${formatWaitLabel(seconds)} и повторите.`;
  }
  return base;
}

function formatDetailsObject(data) {
  const details = data?.details;
  if (!details || Array.isArray(details)) return '';
  const parts = [];
  if (details.bots_limit_reached) {
    parts.push('достигнут лимит ботов на аккаунте');
  }
  if (details.botfather_blocked) {
    parts.push('BotFather временно недоступен для этого аккаунта');
  }
  if (details.step) {
    parts.push(`этап: ${details.step}`);
  }
  if (!parts.length) return '';
  const base = data?.error || 'Ошибка';
  return `${base} (${parts.join('; ')})`;
}

/**
 * Преобразует ошибку API (axios) в понятное сообщение для пользователя.
 * @param {unknown} err
 * @param {string} [fallback='Ошибка']
 */
export function formatApiError(err, fallback = 'Ошибка') {
  if (!err) return fallback;

  const data = err?.response?.data;
  const status = err?.response?.status;

  if (isFloodWaitError(err)) {
    return formatFloodWait(err, data);
  }

  const detailsObjectText = formatDetailsObject(data);
  if (detailsObjectText) {
    return detailsObjectText;
  }

  const validationText = formatValidationErrors(data);
  if (validationText) {
    const prefix = data?.error && data.error !== 'Ошибка валидации данных'
      ? `${data.error}: `
      : '';
    return `${prefix}${validationText}`;
  }

  if (data?.error) {
    return String(data.error);
  }

  if (data?.message) {
    return String(data.message);
  }

  if (err?.code === 'ERR_CANCELED') {
    return 'Запрос отменён.';
  }

  if (err?.code === 'ECONNABORTED') {
    return 'Превышено время ожидания ответа сервера. Данные могли сохраниться — обновите страницу.';
  }

  if (err?.code === 'ERR_NETWORK' || err?.message === 'Network Error') {
    return 'Соединение с сервером прервано. Данные могли сохраниться — обновите страницу.';
  }

  if (!err?.response) {
    if (err?.message && !String(err.message).includes('Network Error')) {
      return String(err.message);
    }
    return 'Нет ответа от сервера. Проверьте интернет или обновите страницу.';
  }

  if (status && STATUS_FALLBACKS[status]) {
    return STATUS_FALLBACKS[status];
  }

  if (err?.message) {
    return String(err.message);
  }

  return fallback;
}
