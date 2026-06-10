<template>
  <div class="prep-page">
    <header class="page-header">
      <h1>Аккаунты</h1>
      <p class="subtitle">
        Загрузите экспорт аккаунтов из Telegram Desktop, настройте безопасность и очистите старых ботов перед кампаниями.
      </p>
    </header>

    <div class="grid">
      <section class="card form-section">
        <h2>Новая задача</h2>

        <AccountDropzone v-model="files" />
        <p class="field-hint">
          Один ZIP-архив — один аккаунт. Экспортируйте данные из Telegram Desktop (папка с сессией внутри архива).
        </p>

        <div class="options-block">
          <h3>Что сделать с аккаунтом</h3>
          <label class="check">
            <input v-model="options.delete_bots" type="checkbox" />
            Удалить всех ботов на аккаунте
          </label>
          <label class="check">
            <input v-model="options.terminate_sessions" type="checkbox" />
            Завершить все другие входы в Telegram
          </label>
          <label class="check">
            <input v-model="options.change_password" type="checkbox" />
            Сменить облачный пароль
          </label>
          <label class="check">
            <input v-model="options.privacy_restrictions" type="checkbox" />
            Ужесточить приватность (номер, «был в сети», приглашения)
          </label>
        </div>

        <div v-if="options.change_password" class="password-block">
          <h3>Облачный пароль</h3>
          <p class="hint">
            Пароль используется только для этой задачи и нигде не сохраняется.
            После смены при необходимости заново экспортируйте аккаунт из Telegram Desktop.
          </p>
          <div class="form-group">
            <label>Новый пароль</label>
            <input
              v-model="newPassword"
              type="password"
              autocomplete="new-password"
              placeholder="Придумайте новый пароль"
            />
          </div>
          <div class="form-group">
            <label>Текущий пароль</label>
            <input
              v-model="currentPassword"
              type="password"
              autocomplete="current-password"
              placeholder="Если пароль уже был включён"
            />
          </div>
          <div class="form-group">
            <label>Подсказка (необязательно)</label>
            <input v-model="passwordHint" type="text" placeholder="Текст подсказки в Telegram" />
          </div>
        </div>

        <label class="check">
          <input v-model="autoStart" type="checkbox" />
          Запустить сразу после загрузки
        </label>

        <p v-if="submitError" class="error-text">{{ submitError }}</p>
        <InlineTaskIndicator v-if="submitting" fallback-label="Запуск подготовки…" />
        <button type="button" :disabled="submitting || !files.length" @click="onSubmit">
          {{ submitting ? 'Отправка…' : 'Запустить подготовку' }}
        </button>
      </section>

      <section class="side">
        <JobLogPanel
          v-if="activeJob"
          :logs="logs"
          :loading="logsLoading"
          :polling="isPolling"
        />
        <div v-else class="card hint-card">
          <p>Журнал появится после запуска задачи.</p>
        </div>

        <div v-if="activeJob" class="card job-summary">
          <h3>Задача #{{ activeJob.id }}</h3>
          <StatusBadge :status="activeJob.status" />
          <p class="progress">{{ activeJob.progress_message }}</p>
          <p class="meta">
            {{ activeJob.succeeded_accounts }}/{{ activeJob.total_accounts }} успешно
          </p>
          <ul v-if="accounts.length" class="data-list acc-list">
            <li v-for="a in accounts" :key="a.id">
              <span>{{ a.label || a.phone || `#${a.id}` }}</span>
              <StatusBadge :status="a.status" />
            </li>
          </ul>
        </div>

        <div class="card pool-card">
          <h3>Готовые аккаунты</h3>
          <p class="hint">После успешной подготовки добавьте их в кампанию.</p>
          <p v-if="poolLoading" class="muted">Загрузка…</p>
          <ul v-else-if="poolAccounts.length" class="data-list pool-list">
            <li v-for="a in poolAccounts" :key="a.id">
              <span>{{ a.label || a.phone || `#${a.id}` }}</span>
              <StatusBadge :status="a.status" />
            </li>
          </ul>
          <p v-else class="muted">Пока нет подготовленных аккаунтов.</p>

          <div v-if="readyPoolCount" class="add-campaign-cta">
            <p class="cta-text">
              {{ readyPoolCount }} {{ readyPoolLabel }} готовы к добавлению в кампанию.
            </p>
            <RouterLink
              v-if="workflow.activeCampaignId"
              :to="{
                name: 'campaign-workspace',
                params: { id: workflow.activeCampaignId },
                query: { tab: 'accounts' },
              }"
              class="btn btn-sm"
            >
              Добавить в «{{ workflow.activeCampaignTitle || 'кампанию' }}»
            </RouterLink>
            <template v-else>
              <RouterLink to="/app" class="btn btn-sm">Выбрать кампанию</RouterLink>
              <RouterLink to="/app/campaigns/new" class="btn btn-sm btn-ghost">Создать кампанию</RouterLink>
            </template>
          </div>
        </div>

        <div v-if="pastJobs.length" class="card">
          <h3>История</h3>
          <ul class="history">
            <li v-for="j in pastJobs" :key="j.id">
              <button type="button" class="link-btn" @click="loadJob(j.id)">
                #{{ j.id }} — {{ j.status }} ({{ j.succeeded_accounts }}/{{ j.total_accounts }})
              </button>
            </li>
          </ul>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { useWorkflowStore } from '../stores/workflowStore';
import AccountDropzone from '../components/AccountDropzone.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import JobLogPanel from '../components/JobLogPanel.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { preparedAccountService } from '../services/preparedAccountService';
import { prepService } from '../services/prepService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';

const taskStore = useAsyncTaskStore();
const workflow = useWorkflowStore();

const files = ref([]);
const submitting = ref(false);
const submitError = ref(null);
const autoStart = ref(true);
const newPassword = ref('');
const currentPassword = ref('');
const passwordHint = ref('');
const options = ref({
  delete_bots: true,
  terminate_sessions: true,
  change_password: true,
  privacy_restrictions: true,
});

const activeJob = ref(null);
const accounts = ref([]);
const logs = ref([]);
const logsLoading = ref(false);
const lastLogId = ref(0);
const pastJobs = ref([]);
const poolAccounts = ref([]);
const poolLoading = ref(false);
let pollTimer = null;

const isPolling = computed(
  () => activeJob.value && ['queued', 'running'].includes(activeJob.value.status)
);

const readyPoolCount = computed(
  () => poolAccounts.value.filter((a) => a.status === 'available').length
);

const readyPoolLabel = computed(() => {
  const n = readyPoolCount.value;
  if (n === 1) return 'аккаунт';
  if (n >= 2 && n <= 4) return 'аккаунта';
  return 'аккаунтов';
});

watch(isPolling, (on) => {
  if (on) startPolling();
  else stopPolling();
});

async function loadHistory() {
  pastJobs.value = await prepService.listJobs();
}

async function loadPool() {
  poolLoading.value = true;
  try {
    poolAccounts.value = await preparedAccountService.listAll();
  } finally {
    poolLoading.value = false;
  }
}

async function loadJob(jobId) {
  stopPolling();
  const data = await prepService.getJob(jobId);
  activeJob.value = data.job;
  accounts.value = data.accounts;
  logs.value = [];
  lastLogId.value = 0;
  await fetchLogs();
  if (isPolling.value) startPolling();
}

async function fetchLogs() {
  if (!activeJob.value?.id) return;
  logsLoading.value = true;
  try {
    const batch = await prepService.getLogs(activeJob.value.id, lastLogId.value);
    if (batch.length) {
      logs.value = [...logs.value, ...batch];
      lastLogId.value = batch[batch.length - 1].id;
    }
  } finally {
    logsLoading.value = false;
  }
}

async function refreshJob() {
  if (!activeJob.value?.id) return;
  const data = await prepService.getJob(activeJob.value.id);
  activeJob.value = data.job;
  accounts.value = data.accounts;
}

async function poll() {
  await refreshJob();
  await fetchLogs();
  if (activeJob.value && !['queued', 'running'].includes(activeJob.value.status)) {
    await loadPool();
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(poll, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function onSubmit() {
  if (!files.value.length) return;
  if (options.value.change_password && !newPassword.value) {
    submitError.value = 'Укажите новый облачный пароль';
    return;
  }
  submitting.value = true;
  submitError.value = null;
  try {
    const job = await taskStore.run(
      'PREP_ACCOUNTS',
      async ({ logStep }) => {
        logStep(`Upload ${files.value.length} archive(s)`, 'debug', { options: options.value });
        const j = await prepService.createJob({
          files: files.value,
          options: options.value,
          newPassword: newPassword.value || null,
          currentPassword: currentPassword.value || null,
          passwordHint: passwordHint.value,
          autoStart: autoStart.value,
        });
        logStep(`Job #${j.id} queued`, 'info', j);
        return j;
      },
      { count: files.value.length }
    );
    files.value = [];
    await loadJob(job.id);
    await loadHistory();
    await loadPool();
  } catch (e) {
    submitError.value = e.response?.data?.error || e.response?.data?.message || 'Ошибка запуска';
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  await loadHistory();
  await loadPool();
});
onUnmounted(stopPolling);
</script>

<style scoped>
.prep-page {
  max-width: 1100px;
}

.subtitle {
  max-width: 640px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
  align-items: start;
}

@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }
}

.password-block h3 {
  margin: 0 0 0.65rem;
  font-size: 0.875rem;
  font-weight: 600;
}

.form-section > button {
  width: 100%;
  margin-top: 1rem;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hint-card {
  color: var(--muted);
  font-size: 0.875rem;
  text-align: center;
  padding: 1.5rem 1rem;
}

.job-summary h3,
.pool-card h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.progress {
  margin: 0.5rem 0;
  font-size: 0.875rem;
  color: var(--muted);
}

.meta {
  font-size: 0.8rem;
  color: var(--muted);
}

.history {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
}

.add-campaign-cta {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.cta-text {
  margin: 0;
  font-size: 0.85rem;
  color: #4ade80;
}

.add-campaign-cta .btn {
  align-self: flex-start;
}
</style>
