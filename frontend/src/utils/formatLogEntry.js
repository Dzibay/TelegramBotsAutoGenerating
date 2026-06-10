/** Нормализация и фильтрация записей журнала процессов. */

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

export function formatContext(ctx) {
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
