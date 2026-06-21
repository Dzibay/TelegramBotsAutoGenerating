/** Статус синхронизации профиля бота с BotFather. */
export const TELEGRAM_SYNC = {
  IDLE: 'idle',
  PENDING: 'pending',
  SYNCING: 'syncing',
  SYNCED: 'synced',
  FAILED: 'failed',
};

export function isTelegramSyncInProgress(status) {
  return status === TELEGRAM_SYNC.PENDING || status === TELEGRAM_SYNC.SYNCING;
}
