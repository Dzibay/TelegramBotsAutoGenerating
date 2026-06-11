<template>
  <section v-if="jobs.length" class="active-jobs card">
    <div class="active-jobs-head">
      <div>
        <h3>Активные задачи</h3>
        <p class="muted">{{ jobs.length }} в очереди или выполняется</p>
      </div>
      <RouterLink v-if="historyLink" :to="historyLink" class="btn btn-sm btn-ghost">
        История
      </RouterLink>
    </div>

    <ul class="active-jobs-list">
      <li v-for="job in jobs" :key="job.id" class="active-job-item">
        <div class="active-job-row">
          <button
            type="button"
            class="active-job-toggle"
            @click="toggleExpand(job.id)"
          >
            <span class="job-id">#{{ job.id }}</span>
            <StatusBadge :status="job.status" />
            <span v-if="job.account_label" class="job-account">{{ job.account_label }}</span>
            <span v-if="job.job_mode" class="job-mode">{{ jobModeLabel(job.job_mode) }}</span>
            <span v-if="job.total_accounts" class="job-progress">
              {{ job.processed_accounts ?? 0 }}/{{ job.total_accounts }}
              · создано {{ job.total_bots_created ?? 0 }}
            </span>
          </button>
          <div class="active-job-actions">
            <RouterLink
              v-if="bulkLink"
              :to="bulkLink"
              class="btn btn-xs btn-ghost"
            >
              Очередь
            </RouterLink>
            <button
              type="button"
              class="btn btn-xs btn-ghost danger"
              :disabled="cancellingId === job.id"
              @click="cancelJob(job.id)"
            >
              {{ cancellingId === job.id ? '…' : 'Стоп' }}
            </button>
          </div>
        </div>
        <p v-if="job.progress_message" class="job-msg">{{ job.progress_message }}</p>
        <div
          v-if="job.total_accounts"
          class="job-track"
          role="progressbar"
          :aria-valuenow="progressPercent(job)"
        >
          <div class="job-fill" :style="{ width: `${progressPercent(job)}%` }" />
        </div>
        <JobLogPanel
          v-if="expandedId === job.id"
          :logs="logsFor(job.id)"
          :loading="logsLoadingId === job.id"
          :polling="isActive(job)"
        />
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import JobLogPanel from './JobLogPanel.vue';
import StatusBadge from './StatusBadge.vue';
import { campaignService, jobService } from '../services/campaignService';
import { useUiPrefsStore } from '../stores/uiPrefsStore';

const props = defineProps({
  campaignId: { type: Number, required: true },
  bulkLink: { type: Object, default: null },
  historyLink: { type: Object, default: null },
  autoLoad: { type: Boolean, default: true },
});

const emit = defineEmits(['update:jobs']);

const uiPrefs = useUiPrefsStore();
const jobs = ref([]);
const expandedId = ref(null);
const logsByJob = ref({});
const lastLogIdByJob = ref({});
const logsLoadingId = ref(null);
const cancellingId = ref(null);
let pollTimer = null;

const historyLink = computed(
  () =>
    props.historyLink ?? {
      name: 'campaign-job-history',
      params: { id: props.campaignId },
    }
);

function isActive(job) {
  return ['queued', 'running'].includes(job.status);
}

function progressPercent(job) {
  if (!job?.total_accounts) return 0;
  return Math.min(100, Math.round(((job.processed_accounts ?? 0) / job.total_accounts) * 100));
}

function jobModeLabel(mode) {
  const map = { manual: 'ручная', planned: 'план', auto: 'авто' };
  return map[mode] || mode;
}

function logsFor(jobId) {
  return logsByJob.value[jobId] ?? [];
}

function toggleExpand(jobId) {
  expandedId.value = expandedId.value === jobId ? null : jobId;
  if (expandedId.value === jobId && !logsByJob.value[jobId]?.length) {
    fetchLogs(jobId, true);
  }
}

async function loadJobs() {
  const items = await campaignService.listActiveJobs(props.campaignId);
  jobs.value = items;
  emit('update:jobs', items);
  if (expandedId.value && !items.some((j) => j.id === expandedId.value)) {
    expandedId.value = items[0]?.id ?? null;
  }
  return items;
}

async function refreshJob(jobId) {
  const updated = await jobService.get(jobId);
  jobs.value = jobs.value.map((j) => (j.id === jobId ? updated : j));
  emit('update:jobs', jobs.value);
  return updated;
}

async function fetchLogs(jobId, reset = false) {
  if (reset) {
    logsByJob.value = { ...logsByJob.value, [jobId]: [] };
    lastLogIdByJob.value = { ...lastLogIdByJob.value, [jobId]: 0 };
  }
  logsLoadingId.value = jobId;
  try {
    const afterId = lastLogIdByJob.value[jobId] ?? 0;
    const batch = await jobService.getLogs(jobId, afterId, {
      minLevel: uiPrefs.verboseLogs ? 'debug' : 'info',
    });
    if (batch.length) {
      logsByJob.value = {
        ...logsByJob.value,
        [jobId]: [...(logsByJob.value[jobId] ?? []), ...batch],
      };
      lastLogIdByJob.value = {
        ...lastLogIdByJob.value,
        [jobId]: batch[batch.length - 1].id,
      };
    }
  } finally {
    logsLoadingId.value = null;
  }
}

async function poll() {
  const prev = jobs.value;
  await loadJobs();
  const activeIds = jobs.value.filter(isActive).map((j) => j.id);
  for (const id of activeIds) {
    await refreshJob(id);
    if (expandedId.value === id) {
      await fetchLogs(id);
    }
  }
  if (!activeIds.length && prev.some(isActive)) {
    emit('update:jobs', jobs.value);
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(poll, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function cancelJob(jobId) {
  cancellingId.value = jobId;
  try {
    await jobService.cancel(jobId);
    await poll();
  } finally {
    cancellingId.value = null;
  }
}

watch(
  () => uiPrefs.verboseLogs,
  async () => {
    for (const job of jobs.value) {
      if (expandedId.value === job.id) {
        await fetchLogs(job.id, true);
      }
    }
  }
);

watch(
  () => jobs.value.some(isActive),
  (active) => {
    if (active) startPolling();
    else stopPolling();
  }
);

onMounted(async () => {
  if (!props.autoLoad) return;
  await loadJobs();
  if (jobs.value.length && !expandedId.value) {
    expandedId.value = jobs.value[jobs.value.length - 1].id;
    await fetchLogs(expandedId.value, true);
  }
  if (jobs.value.some(isActive)) startPolling();
});

onUnmounted(stopPolling);

defineExpose({ loadJobs, poll });
</script>

<style scoped>
.active-jobs {
  margin-bottom: 1.25rem;
  padding: 1.15rem 1.25rem;
  border-color: rgba(59, 130, 246, 0.3);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08), rgba(139, 92, 246, 0.04));
}

.active-jobs-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}

.active-jobs-head h3 {
  margin: 0 0 0.2rem;
  font-size: 0.95rem;
}

.active-jobs-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.active-job-item {
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 10px;
  padding: 0.75rem 0.85rem;
  background: rgba(15, 23, 42, 0.35);
}

.active-job-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: center;
}

.active-job-toggle {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
  padding: 0;
  font: inherit;
}

.job-id {
  font-weight: 600;
}

.job-account,
.job-mode,
.job-progress {
  font-size: 0.82rem;
  color: var(--muted);
}

.active-job-actions {
  display: flex;
  gap: 0.35rem;
}

.job-msg {
  margin: 0.35rem 0 0;
  font-size: 0.82rem;
  color: #93c5fd;
}

.job-track {
  height: 4px;
  border-radius: 99px;
  background: rgba(59, 130, 246, 0.15);
  overflow: hidden;
  margin: 0.5rem 0 0.65rem;
}

.job-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), #60a5fa);
  transition: width 0.4s ease;
}
</style>
