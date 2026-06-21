/** Нормализация и фильтрация записей журнала процессов. */

const STEP_LABELS = {
  username: 'Подбор username',
  botfather_create: 'BotFather',
  referral_fetch: 'Реферальная ссылка',
  links: 'Ссылки',
  avatar: 'Аватар',
  botfather_texts: 'Тексты в BotFather',
  db_save: 'Сохранение',
};

const STATUS_LABELS = {
  creating: 'создание',
  done: 'готово',
  error: 'ошибка',
  skipped: 'пропущен',
  banned: 'забанен',
};

export function normalizeLogEntry(entry, index = 0) {
  if (!entry) return null;
  const time = entry.time || entry.created_at || null;
  return {
    id: entry.id ?? `log-${index}-${time || index}`,
    message: entry.message || '',
    level: entry.level || 'info',
    time,
    context: entry.context ?? entry.detail ?? null,
    source: entry.source || 'server',
  };
}

export function normalizeLogList(logs) {
  return (logs || []).map((e, i) => normalizeLogEntry(e, i)).filter(Boolean);
}

/** В обычном режиме скрываем debug и «шумные» служебные записи. */
export function filterLogsForMode(logs, verbose) {
  const normalized = normalizeLogList(logs);
  if (verbose) return normalized;
  return normalized.filter((e) => e.level !== 'debug');
}

export function formatLogTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Человекочитаемое описание context вместо сырого JSON. */
export function humanizeContext(ctx) {
  if (ctx == null || ctx === '') return '';
  if (typeof ctx === 'string') return ctx;
  if (typeof ctx !== 'object') return String(ctx);

  const parts = [];
  if (ctx.username) parts.push(`@${String(ctx.username).replace(/^@/, '')}`);
  if (ctx.bot_id != null) parts.push(`бот #${ctx.bot_id}`);
  if (ctx.row_id != null) parts.push(`строка ${ctx.row_id}`);
  if (ctx.account_id != null) parts.push(`акк. #${ctx.account_id}`);
  if (ctx.step && STEP_LABELS[ctx.step]) parts.push(STEP_LABELS[ctx.step]);
  if (ctx.status && STATUS_LABELS[ctx.status]) parts.push(STATUS_LABELS[ctx.status]);
  if (ctx.error) parts.push(String(ctx.error));
  if (ctx.delay_sec != null) parts.push(`пауза ${ctx.delay_sec} сек.`);
  if (ctx.cooldown_sec != null) parts.push(`cooldown ${ctx.cooldown_sec} сек.`);

  if (parts.length) return parts.join(' · ');
  return '';
}

export function formatContext(ctx) {
  const human = humanizeContext(ctx);
  if (human) return human;
  if (ctx == null || ctx === '') return '';
  if (typeof ctx === 'string') return ctx;
  try {
    return JSON.stringify(ctx, null, 2);
  } catch {
    return String(ctx);
  }
}

export function mapApiLog(entry) {
  return normalizeLogEntry({
    id: entry.id,
    created_at: entry.created_at,
    message: entry.message,
    level: entry.level || 'info',
    context: entry.context,
    source: 'server',
  });
}

export function levelLabel(level) {
  const map = {
    info: 'INFO',
    warn: 'WARN',
    error: 'ERR',
    success: 'OK',
    debug: 'DBG',
  };
  return map[level] || String(level || 'info').toUpperCase();
}
