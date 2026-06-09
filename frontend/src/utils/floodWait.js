/** Секунды ожидания из ответа API (Telegram FloodWait). */
export function getFloodWaitSeconds(err) {
  const details = err?.response?.data?.details;
  if (details?.wait_seconds != null) {
    const n = Number(details.wait_seconds);
    if (Number.isFinite(n) && n > 0) return Math.ceil(n);
  }
  const msg = err?.response?.data?.error || err?.message || '';
  const m = String(msg).match(/(\d+)\s*(?:сек|sec)/i);
  if (m) return Number(m[1]);
  const mMin = String(msg).match(/(\d+)\s*мин/i);
  if (mMin) {
    const secPart = String(msg).match(/(\d+)\s*сек/i);
    return Number(mMin[1]) * 60 + (secPart ? Number(secPart[1]) : 0);
  }
  return null;
}

export function isFloodWaitError(err) {
  if (err?.response?.data?.details?.flood_wait) return true;
  const code = err?.response?.data?.error_code;
  if (code === 'FLOOD_WAIT') return true;
  const msg = (err?.response?.data?.error || '').toLowerCase();
  return (
    msg.includes('лимит telegram') ||
    msg.includes('лимит botfather') ||
    msg.includes('flood') ||
    msg.includes('подождите')
  );
}

export function formatWaitLabel(seconds) {
  const s = Math.max(0, Math.ceil(seconds));
  if (s >= 60) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m} мин. ${r} сек.` : `${m} мин.`;
  }
  return `${s} сек.`;
}
