/** Нормализация и фильтрация записей журнала процессов. */

const STEP_LABELS = {
  username: 'Подбор username',
  botfather_create: 'Создание в BotFather',
  referral_fetch: 'Реферальная ссылка',
  links: 'Ссылки',
  avatar: 'Аватар',
  description_picture: 'Картинка плаката',
  botfather_texts: 'Тексты в BotFather',
  db_save: 'Сохранение в БД',
  botfather_wait: 'Ожидание BotFather',
  botfather_sync: 'Синхронизация BotFather',
  prep: 'Подготовка',
  verify: 'Проверка',
};

const STATUS_LABELS = {
  creating: 'создание',
  done: 'готово',
  error: 'ошибка',
  skipped: 'пропущен',
  banned: 'забанен',
  waiting: 'ожидание',
  queued: 'в очереди',
  running: 'выполняется',
  cancelled: 'отменено',
};

/** Ключи context, которые показываются как бейджи в строке лога. */
const TAG_CONTEXT_KEYS = new Set([
  'username',
  'step',
  'status',
  'row_id',
  'plan_index',
  'account_id',
  'bot_id',
  'wait_seconds',
  'delay_sec',
  'cooldown_sec',
  'batch_size',
  'processed',
  'total',
  'job_id',
  'task_id',
]);

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

/** В обычном режиме скрываем только debug; info/warn/error/success всегда видны. */
export function filterLogsForMode(logs, verbose) {
  const normalized = normalizeLogList(logs);
  if (verbose) return normalized;
  return normalized.filter((e) => e.level !== 'debug');
}

/** Разделители между ботами/строками в массовом создании. */
export function withLogRowBreaks(logs) {
  let lastRow = null;
  return logs.map((entry) => {
    const rowId = entry.context?.row_id;
    const rowBreak = rowId != null && lastRow != null && rowId !== lastRow;
    if (rowId != null) lastRow = rowId;
    return { ...entry, _rowBreak: rowBreak };
  });
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

function stepLabel(step) {
  if (!step) return '';
  return STEP_LABELS[step] || String(step).replace(/_/g, ' ');
}

function statusLabel(status) {
  if (!status) return '';
  return STATUS_LABELS[status] || String(status);
}

/** Бейджи для отображения в строке лога (всегда видны). */
export function extractLogTags(ctx) {
  if (ctx == null || typeof ctx !== 'object') return [];

  const tags = [];

  if (ctx.username) {
    tags.push({
      kind: 'user',
      text: `@${String(ctx.username).replace(/^@/, '')}`,
    });
  }

  if (ctx.step) {
    tags.push({ kind: 'step', text: stepLabel(ctx.step) });
  }

  if (ctx.status) {
    tags.push({ kind: 'status', text: statusLabel(ctx.status) });
  }

  if (ctx.row_id != null) {
    tags.push({ kind: 'row', text: `строка ${ctx.row_id}` });
  }

  if (ctx.plan_index != null) {
    tags.push({ kind: 'index', text: `план ${Number(ctx.plan_index) + 1}` });
  }

  if (ctx.account_id != null) {
    tags.push({ kind: 'account', text: `акк. #${ctx.account_id}` });
  }

  if (ctx.bot_id != null) {
    tags.push({ kind: 'bot', text: `бот #${ctx.bot_id}` });
  }

  if (ctx.wait_seconds != null) {
    tags.push({ kind: 'wait', text: `ожидание ${ctx.wait_seconds} с` });
  }

  if (ctx.delay_sec != null) {
    tags.push({ kind: 'wait', text: `пауза ${ctx.delay_sec} с` });
  }

  if (ctx.cooldown_sec != null) {
    tags.push({ kind: 'wait', text: `cooldown ${ctx.cooldown_sec} с` });
  }

  if (ctx.batch_size != null) {
    tags.push({ kind: 'meta', text: `батч ${ctx.batch_size}` });
  }

  if (ctx.processed != null && ctx.total != null) {
    tags.push({ kind: 'meta', text: `${ctx.processed}/${ctx.total}` });
  }

  if (ctx.task_id != null) {
    tags.push({ kind: 'meta', text: `задача #${ctx.task_id}` });
  }

  if (ctx.job_id != null) {
    tags.push({ kind: 'meta', text: `job #${ctx.job_id}` });
  }

  return tags;
}

/** Есть ли в context поля, не показанные бейджами (для блока «техн. детали»). */
export function hasExtraContext(ctx) {
  if (ctx == null || ctx === '') return false;
  if (typeof ctx !== 'object') return true;
  return Object.keys(ctx).some((key) => !TAG_CONTEXT_KEYS.has(key));
}

/** Текст сообщения с дополнением ошибкой из context. */
export function enrichLogMessage(entry) {
  let msg = entry?.message || '';
  const err = entry?.context?.error;
  if (err && !msg.includes(String(err))) {
    msg = msg ? `${msg} — ${err}` : String(err);
  }
  return msg;
}

/** Человекочитаемое описание context (для сводки в details). */
export function humanizeContext(ctx) {
  if (ctx == null || ctx === '') return '';
  if (typeof ctx === 'string') return ctx;
  if (typeof ctx !== 'object') return String(ctx);

  const parts = [];
  for (const tag of extractLogTags(ctx)) {
    parts.push(tag.text);
  }
  if (ctx.error) parts.push(String(ctx.error));
  if (ctx.botfather_created) parts.push('создан в BotFather');

  if (parts.length) return parts.join(' · ');
  return '';
}

export function formatContext(ctx) {
  const human = humanizeContext(ctx);
  if (human && hasExtraContext(ctx)) {
    const extra = {};
    for (const [key, value] of Object.entries(ctx)) {
      if (!TAG_CONTEXT_KEYS.has(key) && key !== 'error') {
        extra[key] = value;
      }
    }
    if (Object.keys(extra).length) {
      try {
        return `${human}\n\n${JSON.stringify(extra, null, 2)}`;
      } catch {
        return human;
      }
    }
  }
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
