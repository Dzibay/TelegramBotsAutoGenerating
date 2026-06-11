<template>
  <div class="job-history-page">
    <header class="page-header">
      <div class="title-row">
        <div>
          <RouterLink :to="campaignLink" class="back-link">← К кампании</RouterLink>
          <h1>История задач</h1>
          <p v-if="campaignTitle" class="subtitle">{{ campaignTitle }}</p>
        </div>
      </div>
    </header>

    <CampaignActiveJobsPanel
      v-if="campaignId"
      :campaign-id="campaignId"
      :bulk-link="bulkLink"
      :history-link="null"
      @update:jobs="onActiveJobsUpdate"
    />

    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <InlineTaskIndicator v-else-if="loading" fallback-label="Загрузка истории…" />

    <template v-else>
      <section class="card block">
        <h2 class="block-title">Завершённые задачи</h2>
        <p class="field-hint block-hint">
          Сохраняются настройки и аватары. Неудачные боты из ручных партий можно перезапустить.
        </p>

        <p v-if="!pastJobs.length" class="muted empty-hint">Пока нет завершённых задач.</p>

        <ul v-else class="job-history-list">
          <li v-for="j in pastJobs" :key="j.id" class="job-history-item">
            <div class="job-history-main">
              <button type="button" class="link-btn" @click="openJob(j)">
                #{{ j.id }}
                <span v-if="j.retried_from_job_id" class="muted">
                  ← из #{{ j.retried_from_job_id }}
                </span>
                · {{ jobStatusLabel(j.status) }}
                <span v-if="j.account_label"> · {{ j.account_label }}</span>
                · {{ j.total_bots_created }}/{{ j.total_accounts }} ботов
                <span v-if="j.total_failed" class="history-failed">({{ j.total_failed }} ошибок)</span>
              </button>
              <span class="muted job-history-date">
                {{ formatJobDate(j.finished_at || j.created_at) }}
              </span>
            </div>
            <div class="job-history-actions">
              <RouterLink
                v-if="j.job_mode === 'manual'"
                :to="bulkRestoreLink(j)"
                class="btn btn-xs btn-ghost"
              >
                В форму
              </RouterLink>
              <button
                v-if="j.retry_available"
                type="button"
                class="btn btn-xs"
                :disabled="retryBusy || accountBusy(j)"
                @click="retryJob(j)"
              >
                Повторить ({{ j.retry_count }})
              </button>
            </div>
          </li>
        </ul>
      </section>

      <section v-if="viewJob" class="card block">
        <div class="history-view-head">
          <h2 class="block-title">Задача #{{ viewJob.id }}</h2>
          <button type="button" class="btn btn-xs btn-ghost" @click="viewJob = null">Закрыть</button>
        </div>
        <p class="muted history-view-meta">
          {{ jobStatusLabel(viewJob.status) }}
          <span v-if="viewJob.account_label"> · {{ viewJob.account_label }}</span>
          · создано {{ viewJob.total_bots_created }}/{{ viewJob.total_accounts }}
          <span v-if="viewJob.error_message"> · {{ viewJob.error_message }}</span>
        </p>
        <JobLogPanel :logs="viewLogs" :loading="viewLogsLoading" />
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import CampaignActiveJobsPanel from '../components/CampaignActiveJobsPanel.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import JobLogPanel from '../components/JobLogPanel.vue';
import { campaignService, jobService } from '../services/campaignService';
import { useUiPrefsStore } from '../stores/uiPrefsStore';
import { useWorkflowStore } from '../stores/workflowStore';
import { mapApiLog } from '../utils/formatLogEntry';

const route = useRoute();
const router = useRouter();
const workflow = useWorkflowStore();
const uiPrefs = useUiPrefsStore();

const campaignId = computed(() => Number(route.params.id));
const loading = ref(true);
const loadError = ref(null);
const campaignTitle = ref('');
const pastJobs = ref([]);
const activeJobs = ref([]);
const viewJob = ref(null);
const viewLogs = ref([]);
const viewLogsLoading = ref(false);
const retryBusy = ref(false);

const campaignLink = computed(() => ({
  name: 'campaign-workspace',
  params: { id: campaignId.value },
}));

const bulkLink = computed(() => ({
  name: 'bulk-bot-create',
  params: { id: campaignId.value },
  query: { step: 3 },
}));

function jobStatusLabel(status) {
  const map = {
    queued: 'В очереди',
    running: 'Выполняется',
    completed: 'Завершена',
    failed: 'Ошибка',
    cancelled: 'Отменена',
  };
  return map[status] || status;
}

function formatJobDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function accountBusy(job) {
  const ids = new Set(job.account_ids || []);
  if (job.telegram_account_id) ids.add(job.telegram_account_id);
  return activeJobs.value.some((active) => {
    if (!['queued', 'running'].includes(active.status)) return false;
    const activeIds = new Set(active.account_ids || []);
    if (active.telegram_account_id) activeIds.add(active.telegram_account_id);
    if (active.job_mode === 'auto') return true;
    for (const id of ids) {
      if (activeIds.has(id)) return true;
    }
    return false;
  });
}

function bulkRestoreLink(job) {
  return {
    name: 'bulk-bot-create',
    params: { id: campaignId.value },
    query: { restoreJob: job.id },
  };
}

function onActiveJobsUpdate(jobs) {
  activeJobs.value = jobs;
}

async function loadHistory() {
  const items = await campaignService.listJobs(campaignId.value);
  pastJobs.value = items.filter((j) =>
    ['completed', 'failed', 'cancelled'].includes(j.status)
  );
}

async function openJob(job) {
  viewJob.value = job;
  viewLogs.value = [];
  viewLogsLoading.value = true;
  try {
    const full = await jobService.get(job.id, { includeSnapshots: true });
    viewJob.value = full;
    viewLogs.value = (await jobService.getLogs(job.id, 0, {
      minLevel: uiPrefs.verboseLogs ? 'debug' : 'info',
    })).map(mapApiLog);
  } finally {
    viewLogsLoading.value = false;
  }
}

async function retryJob(job) {
  retryBusy.value = true;
  loadError.value = null;
  try {
    const newJob = await jobService.retry(job.id);
    await loadHistory();
    router.push({
      name: 'bulk-bot-create',
      params: { id: campaignId.value },
      query: { step: 3, jobId: newJob.id },
    });
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось перезапустить задачу';
  } finally {
    retryBusy.value = false;
  }
}

onMounted(async () => {
  try {
    const data = await campaignService.get(campaignId.value);
    campaignTitle.value = data.campaign?.title || '';
    workflow.setCampaign(campaignId.value, campaignTitle.value);
    activeJobs.value = data.activeJobs ?? [];
    await loadHistory();
    const openId = Number(route.query.job);
    if (openId) {
      const job = pastJobs.value.find((j) => j.id === openId);
      if (job) await openJob(job);
    }
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось загрузить историю';
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.job-history-page {
  max-width: 960px;
}

.page-header {
  margin-bottom: 1.25rem;
}

.back-link {
  display: inline-block;
  margin-bottom: 0.35rem;
  font-size: 0.85rem;
  color: var(--muted);
  text-decoration: none;
}

.back-link:hover {
  color: var(--accent);
}

.title-row h1 {
  margin: 0 0 0.25rem;
}

.subtitle {
  margin: 0;
  color: var(--muted);
}

.block {
  margin-bottom: 1.25rem;
  padding: 1.15rem 1.25rem;
}

.block-title {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}

.block-hint {
  margin: 0 0 1rem;
}

.empty-hint {
  margin: 0;
}

.job-history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.job-history-item {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: center;
  padding: 0.65rem 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.job-history-item:last-child {
  border-bottom: none;
}

.job-history-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  min-width: 0;
}

.link-btn {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
  padding: 0;
  font: inherit;
}

.link-btn:hover {
  color: var(--accent);
}

.history-failed {
  color: #f87171;
}

.job-history-date {
  font-size: 0.82rem;
}

.job-history-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.history-view-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.history-view-meta {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
}
</style>
