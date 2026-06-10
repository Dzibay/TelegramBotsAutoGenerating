/** Оценка времени массового создания ботов (секунды). Синхронизировано с backend pacing. */
const INTER_BOT_SEC = 45;
const BATCH_SIZE = 5;
const BATCH_COOLDOWN_SEC = 180;
const PER_BOT_WORK_SEC = 90;

export function estimateBulkCreationSec(botCount) {
  const n = Math.max(0, Number(botCount) || 0);
  if (n <= 0) return 0;
  const interBot = Math.max(0, n - 1) * INTER_BOT_SEC;
  const batchPauses = Math.floor(n / BATCH_SIZE) * BATCH_COOLDOWN_SEC;
  const work = n * PER_BOT_WORK_SEC;
  return interBot + batchPauses + work;
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
