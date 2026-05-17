<template>
  <div v-if="loading" class="muted">Загрузка кампании…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>

  <div v-else class="detail">
    <header class="detail-header">
      <RouterLink to="/app" class="back">← Кампании</RouterLink>
      <div class="title-row">
        <h1>{{ campaign.title }}</h1>
        <StatusBadge :status="campaign.status" />
        <div class="header-btns">
          <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }" class="btn-ghost btn-sm">
            Изменить
          </RouterLink>
          <button type="button" class="btn-ghost btn-sm btn-danger" @click="onDeleteCampaign">
            Удалить
          </button>
        </div>
      </div>
      <p class="resource">{{ campaign.resource_url }}</p>
      <p class="keywords">{{ campaign.keywords?.join(' · ') }}</p>
    </header>

    <div class="stats">
      <div class="stat card">
        <span class="stat-val">{{ campaign.accounts_count }}</span>
        <span class="stat-label">аккаунтов</span>
      </div>
      <div class="stat card">
        <span class="stat-val">{{ campaign.bots_count }}</span>
        <span class="stat-label">ботов</span>
      </div>
      <div class="stat card">
        <span class="stat-val">{{ campaign.active_bots_count }}</span>
        <span class="stat-label">активных</span>
      </div>
    </div>

    <section v-if="job || canStart" class="progress-section card">
      <div class="progress-top">
        <h2>Процесс создания</h2>
        <StatusBadge v-if="job" :status="job.status" />
        <StatusBadge v-else status="draft" />
      </div>
      <p v-if="job" class="progress-msg">{{ job.progress_message || '—' }}</p>
      <p v-else class="progress-msg muted">Задача ещё не запускалась</p>
      <div v-if="job && job.total_accounts" class="progress-bar-wrap">
        <div
          class="progress-bar"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
      <p v-if="job?.error_message" class="error-text">{{ job.error_message }}</p>
      <div v-if="canStart" class="actions">
        <button type="button" :disabled="starting" @click="onStart">
          {{ starting ? 'Запуск…' : 'Запустить создание ботов' }}
        </button>
      </div>
    </section>

    <div class="grid-2">
      <JobLogPanel :logs="logs" :loading="logsLoading" :polling="isPolling" />

      <div class="side">
        <section class="card section">
          <h3>Аккаунты Telegram</h3>
          <p v-if="!accounts.length" class="muted">Нет загруженных аккаунтов</p>
          <ul v-else class="mini-list">
            <li v-for="a in accounts" :key="a.id">
              <span>{{ a.label || `Аккаунт #${a.id}` }}</span>
              <StatusBadge :status="a.status" />
              <span class="mini-meta">{{ a.bots_created }}/{{ a.max_bots_limit }} ботов</span>
            </li>
          </ul>
          <div v-if="canAddAccounts" class="add-prepared">
            <p class="muted small">Добавить из пула подготовленных:</p>
            <PreparedAccountPicker ref="pickerRef" v-model="selectedPreparedIds" />
            <button
              type="button"
              class="btn-add"
              :disabled="!selectedPreparedIds.length || attaching"
              @click="onAttachPrepared"
            >
              {{ attaching ? 'Добавление…' : 'Добавить выбранные' }}
            </button>
          </div>
        </section>

        <section class="card section">
          <div class="section-head">
            <h3>Боты</h3>
            <RouterLink
              :to="{ name: 'bot-create', query: { campaign_id: campaignId } }"
              class="btn-sm"
            >
              + Создать бота
            </RouterLink>
          </div>
          <p v-if="!bots.length" class="muted">Создайте бота вручную или запустите массовое создание</p>
          <ul v-else class="mini-list bots">
            <li v-for="b in bots" :key="b.id" class="bot-li">
              <div class="bot-li-main">
                <strong>@{{ b.username || '—' }}</strong>
                <span>{{ b.display_name }}</span>
                <StatusBadge :status="b.status" />
              </div>
              <div class="bot-li-actions">
                <button
                  v-if="b.status !== 'active'"
                  type="button"
                  class="link-btn"
                  @click="onBotStart(b)"
                >
                  Запустить
                </button>
                <button v-else type="button" class="link-btn" @click="onBotStop(b)">Стоп</button>
                <RouterLink :to="{ name: 'bot-edit', params: { id: b.id } }" class="link-btn">
                  Изменить
                </RouterLink>
                <button type="button" class="link-btn danger" @click="onBotDelete(b)">Удалить</button>
              </div>
            </li>
          </ul>
          <RouterLink to="/app/bots" class="all-bots-link">Все боты →</RouterLink>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import JobLogPanel from '../components/JobLogPanel.vue';
import PreparedAccountPicker from '../components/PreparedAccountPicker.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { botService } from '../services/botService';
import { campaignService, jobService } from '../services/campaignService';

const route = useRoute();
const router = useRouter();
const campaignId = computed(() => Number(route.params.id));

const loading = ref(true);
const loadError = ref(null);
const campaign = ref({});
const accounts = ref([]);
const bots = ref([]);
const job = ref(null);
const logs = ref([]);
const logsLoading = ref(false);
const lastLogId = ref(0);
const starting = ref(false);
const attaching = ref(false);
const selectedPreparedIds = ref([]);
const pickerRef = ref(null);
let pollTimer = null;

const isPolling = computed(
  () => job.value && ['queued', 'running'].includes(job.value.status)
);

const progressPercent = computed(() => {
  if (!job.value?.total_accounts) return 0;
  return Math.min(
    100,
    Math.round((job.value.processed_accounts / job.value.total_accounts) * 100)
  );
});

const canStart = computed(
  () =>
    campaign.value.accounts_count > 0 &&
    (!job.value || !['queued', 'running'].includes(job.value.status)) &&
    ['draft', 'failed', 'completed'].includes(campaign.value.status)
);

const canAddAccounts = computed(
  () => !job.value || !['running'].includes(job.value.status)
);

async function loadCampaign() {
  const data = await campaignService.get(campaignId.value);
  campaign.value = data.campaign;
  job.value = data.activeJob;
}

async function loadExtras() {
  const [acc, b] = await Promise.all([
    campaignService.getAccounts(campaignId.value),
    campaignService.getBots(campaignId.value),
  ]);
  accounts.value = acc;
  bots.value = b;
}

async function fetchLogs() {
  if (!job.value?.id) return;
  logsLoading.value = true;
  try {
    const batch = await jobService.getLogs(job.value.id, lastLogId.value);
    if (batch.length) {
      logs.value = [...logs.value, ...batch];
      lastLogId.value = batch[batch.length - 1].id;
    }
  } finally {
    logsLoading.value = false;
  }
}

async function refreshJob() {
  if (!job.value?.id) return;
  job.value = await jobService.get(job.value.id);
  if (!['queued', 'running'].includes(job.value.status)) {
    await loadCampaign();
    await loadExtras();
  }
}

async function poll() {
  await refreshJob();
  await fetchLogs();
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

async function onStart() {
  starting.value = true;
  try {
    job.value = await campaignService.start(campaignId.value);
    logs.value = [];
    lastLogId.value = 0;
    await fetchLogs();
    startPolling();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось запустить';
  } finally {
    starting.value = false;
  }
}

async function onDeleteCampaign() {
  if (!confirm(`Удалить кампанию «${campaign.value.title}»?`)) return;
  try {
    await campaignService.remove(campaignId.value);
    router.push({ name: 'dashboard' });
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка удаления';
  }
}

async function onBotStart(b) {
  try {
    await botService.start(b.id);
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка запуска';
  }
}

async function onBotStop(b) {
  try {
    await botService.stop(b.id);
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка остановки';
  }
}

async function onBotDelete(b) {
  if (!confirm(`Удалить @${b.username || b.id}?`)) return;
  try {
    await botService.remove(b.id);
    await loadCampaign();
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка удаления';
  }
}

async function onAttachPrepared() {
  if (!selectedPreparedIds.value.length) return;
  attaching.value = true;
  try {
    await campaignService.attachPreparedAccounts(
      campaignId.value,
      selectedPreparedIds.value
    );
    selectedPreparedIds.value = [];
    await loadCampaign();
    await loadExtras();
    pickerRef.value?.reload?.();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка добавления аккаунтов';
  } finally {
    attaching.value = false;
  }
}

watch(isPolling, (v) => {
  if (v) startPolling();
  else stopPolling();
});

onMounted(async () => {
  try {
    await loadCampaign();
    await loadExtras();
    if (job.value?.id) {
      await fetchLogs();
      if (isPolling.value) startPolling();
    }
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  } finally {
    loading.value = false;
  }
});

onUnmounted(stopPolling);
</script>

<style scoped>
.detail-header {
  margin-bottom: 1.25rem;
}

.back {
  font-size: 0.875rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

.title-row h1 {
  margin: 0;
  font-size: 1.35rem;
}

.resource,
.keywords {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat {
  text-align: center;
  padding: 1rem;
}

.stat-val {
  display: block;
  font-size: 1.5rem;
  font-weight: 700;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--muted);
}

.progress-section h2 {
  margin: 0;
  font-size: 1rem;
}

.progress-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.progress-msg {
  margin: 0 0 0.75rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.progress-bar-wrap {
  height: 6px;
  background: var(--bg);
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s;
}

.progress-section {
  margin-bottom: 1.25rem;
}

.actions {
  margin-top: 1rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 800px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

.section h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.mini-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.mini-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.875rem;
}

.mini-meta {
  width: 100%;
  font-size: 0.75rem;
  color: var(--muted);
}

.bots li {
  flex-direction: column;
  align-items: flex-start;
}

.add-prepared {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.add-prepared .small {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
}

.btn-add {
  width: 100%;
  margin-top: 0.75rem;
}

.upload-more {
  display: block;
  margin-top: 0.75rem;
  padding: 0.5rem;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--muted);
}

.side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.header-btns {
  display: flex;
  gap: 0.35rem;
  margin-left: auto;
}

.btn-sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.75rem;
  width: auto;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.section-head h3 {
  margin: 0;
}

.bot-li {
  flex-direction: column;
  align-items: stretch !important;
  gap: 0.35rem;
}

.bot-li-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.bot-li-actions {
  display: flex;
  gap: 0.5rem;
}

.link-btn.danger {
  color: #f87171;
}

.all-bots-link {
  display: inline-block;
  margin-top: 0.75rem;
  font-size: 0.85rem;
}
</style>
