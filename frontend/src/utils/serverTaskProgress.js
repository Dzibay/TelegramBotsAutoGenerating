import { jobService } from '../services/campaignService';
import { botService } from '../services/botService';
import { prepService } from '../services/prepService';
import { isTelegramSyncInProgress } from './telegramSyncStatus';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Ожидание завершения creation_job с логами и прогрессом с сервера.
 */
export async function pollCreationJob(
  jobId,
  {
    logStep = null,
    onProgress = null,
    intervalMs = 2000,
    includeSnapshots = true,
  } = {}
) {
  let lastLogId = 0;
  while (true) {
    const job = await jobService.get(jobId, { includeSnapshots });
    onProgress?.(job.progress_message || '', job.status || '');
    if (logStep) {
      const logs = await jobService.getLogs(jobId, lastLogId, { minLevel: 'info' });
      for (const entry of logs) {
        if (entry.id != null) lastLogId = Math.max(lastLogId, entry.id);
        logStep(entry.message, entry.level || 'info', entry.context);
      }
    }
    if (job.status === 'completed') {
      return job;
    }
    if (job.status === 'failed' || job.status === 'cancelled') {
      const err = new Error(job.error_message || 'Задача завершилась с ошибкой');
      err.job = job;
      throw err;
    }
    await sleep(intervalMs);
  }
}

/** Дождаться завершения BotFather sync по статусу бота в БД. */
export async function pollBotTelegramSync(
  botId,
  {
    onProgress = null,
    intervalMs = 2500,
    timeoutMs = 600000,
  } = {}
) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const bot = await botService.get(botId);
    const status = bot.telegram_sync_status;
    onProgress?.(bot.botfather_error || status, status);
    if (!isTelegramSyncInProgress(status)) {
      if (status === 'failed') {
        const err = new Error(bot.botfather_error || 'Синхронизация с Telegram не удалась');
        err.bot = bot;
        throw err;
      }
      return bot;
    }
    await sleep(intervalMs);
  }
  throw new Error('Таймаут ожидания синхронизации с Telegram');
}

/** Ожидание завершения account-prep job с логами и прогрессом с сервера. */
export async function pollPrepJob(
  jobId,
  {
    logStep = null,
    onProgress = null,
    intervalMs = 2000,
  } = {}
) {
  let lastLogId = 0;
  while (true) {
    const { job } = await prepService.getJob(jobId);
    onProgress?.(job.progress_message || '', job.status || '');
    if (logStep) {
      const logs = await prepService.getLogs(jobId, lastLogId);
      for (const entry of logs) {
        if (entry.id != null) lastLogId = Math.max(lastLogId, entry.id);
        logStep(entry.message, entry.level || 'info', entry.context);
      }
    }
    if (job.status === 'completed') {
      return job;
    }
    if (job.status === 'failed' || job.status === 'cancelled') {
      const err = new Error(job.error_message || 'Подготовка завершилась с ошибкой');
      err.job = job;
      throw err;
    }
    await sleep(intervalMs);
  }
}
