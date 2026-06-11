/** Оценка времени массового создания ботов (секунды). Синхронизировано с backend pacing. */
const DEFAULT_PACING = {
  inter_bot_delay_sec: 45,
  op_delay_sec: 4,
  conv_delay_sec: 2,
  batch_size: 5,
  batch_cooldown_sec: 180,
  post_throttle_delay_sec: 30,
};

const PER_BOT_WORK_SEC = 90;

function resolvePacing(pacing) {
  return { ...DEFAULT_PACING, ...(pacing || {}) };
}

export function estimateBulkCreationSec(botCount, pacing) {
  const p = resolvePacing(pacing);
  const n = Math.max(0, Number(botCount) || 0);
  if (n <= 0) return 0;
  const interBot = Math.max(0, n - 1) * p.inter_bot_delay_sec;
  const batchPauses = Math.floor(n / p.batch_size) * p.batch_cooldown_sec;
  const work = n * PER_BOT_WORK_SEC;
  return interBot + batchPauses + work;
}

export function formatPacingSummary(pacing) {
  const p = resolvePacing(pacing);
  const mins = Math.max(1, Math.round(p.batch_cooldown_sec / 60));
  return `~${p.inter_bot_delay_sec} сек между ботами, ~${mins} мин каждые ${p.batch_size} ботов`;
}

export function formatDurationSec(totalSec) {
  const sec = Math.max(0, Math.round(totalSec));
  if (sec < 60) return `~${sec} сек`;
  const m = Math.floor(sec / 60);
  const r = sec % 60;
  if (m < 60) return r > 0 ? `~${m} мин ${r} сек` : `~${m} мин`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return rm > 0 ? `~${h} ч ${rm} мин` : `~${h} ч`;
}

export function formatEtaRemaining(elapsedSec, estimatedSec) {
  const left = Math.max(0, estimatedSec - elapsedSec);
  if (left <= 0) return 'завершаем…';
  return `осталось ${formatDurationSec(left)}`;
}
