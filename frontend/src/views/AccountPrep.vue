<template>
  <div class="prep-page">
    <header class="page-header">
      <RouterLink to="/app" class="back">← Кампании</RouterLink>
      <h1>Подготовка аккаунтов</h1>
      <p class="subtitle">
        Загрузите tdata, завершите чужие сессии, смените облачный пароль и ужесточите приватность перед кампаниями.
      </p>
    </header>

    <div class="grid">
      <section class="card form-section">
        <h2>Новая задача</h2>

        <AccountDropzone v-model="files" />
        <p class="field-hint">
          Каждый ZIP — отдельный аккаунт. Внутри должна быть папка <code>tdata</code> из Telegram Desktop.
        </p>

        <div class="options-block">
          <h3>Меры безопасности</h3>
          <label class="check">
            <input v-model="options.terminate_sessions" type="checkbox" />
            Завершить все другие сессии (кроме текущей из tdata)
          </label>
          <label class="check">
            <input v-model="options.change_password" type="checkbox" />
            Сменить облачный пароль (2FA)
          </label>
          <label class="check">
            <input v-model="options.privacy_restrictions" type="checkbox" />
            Приватность: скрыть номер, «был в сети», инвайты
          </label>
        </div>

        <div v-if="options.change_password" class="password-block">
          <h3>Пароли</h3>
          <p class="hint">
            Пароли не сохраняются в БД — только передаются worker'у на время задачи.
            После смены обновите tdata в Telegram Desktop или загрузите новый экспорт.
          </p>
          <div class="form-group">
            <label>Новый облачный пароль</label>
            <input v-model="newPassword" type="password" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label>Текущий пароль (если 2FA уже включена)</label>
            <input v-model="currentPassword" type="password" autocomplete="current-password" />
          </div>
          <div class="form-group">
            <label>Подсказка к паролю</label>
            <input v-model="passwordHint" type="text" placeholder="Необязательно" />
          </div>
        </div>

        <label class="check">
          <input v-model="autoStart" type="checkbox" />
          Запустить сразу после загрузки
        </label>

        <p v-if="submitError" class="error-text">{{ submitError }}</p>
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
          <ul v-if="accounts.length" class="acc-list">
            <li v-for="a in accounts" :key="a.id">
              <span>{{ a.label || a.phone || `#${a.id}` }}</span>
              <StatusBadge :status="a.status" />
            </li>
          </ul>
        </div>

        <div class="card pool-card">
          <h3>Пул для кампаний</h3>
          <p class="hint">После успешной подготовки аккаунты появляются здесь и доступны при создании кампании.</p>
          <p v-if="poolLoading" class="muted">Загрузка…</p>
          <ul v-else-if="poolAccounts.length" class="pool-list">
            <li v-for="a in poolAccounts" :key="a.id">
              <span>{{ a.label || a.phone || `#${a.id}` }}</span>
              <StatusBadge :status="a.status" />
            </li>
          </ul>
          <p v-else class="muted">Пока нет подготовленных аккаунтов.</p>
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
import AccountDropzone from '../components/AccountDropzone.vue';
import JobLogPanel from '../components/JobLogPanel.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { preparedAccountService } from '../services/preparedAccountService';
import { prepService } from '../services/prepService';

const files = ref([]);
const submitting = ref(false);
const submitError = ref(null);
const autoStart = ref(true);
const newPassword = ref('');
const currentPassword = ref('');
const passwordHint = ref('');
const options = ref({
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
    const job = await prepService.createJob({
      files: files.value,
      options: options.value,
      newPassword: newPassword.value || null,
      currentPassword: currentPassword.value || null,
      passwordHint: passwordHint.value,
      autoStart: autoStart.value,
    });
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

.page-header {
  margin-bottom: 1.5rem;
}

.back {
  display: inline-block;
  font-size: 0.875rem;
  color: var(--muted);
  margin-bottom: 0.5rem;
}

.page-header h1 {
  margin: 0;
  font-size: 1.4rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
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

.form-section h2 {
  margin: 0 0 1rem;
  font-size: 1.05rem;
}

.field-hint {
  font-size: 0.8rem;
  color: var(--muted);
  margin: 0.5rem 0 0;
}

.options-block h3,
.password-block h3 {
  margin: 1rem 0 0.5rem;
  font-size: 0.95rem;
}

.check {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.check input {
  width: auto;
  margin-top: 0.2rem;
}

.hint {
  font-size: 0.8rem;
  color: var(--muted);
  margin: 0 0 0.75rem;
}

.password-block {
  padding: 0.75rem;
  background: var(--bg);
  border-radius: 8px;
  border: 1px solid var(--border);
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
  font-size: 0.9rem;
}

.job-summary h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
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

.acc-list,
.history {
  list-style: none;
  margin: 0.75rem 0 0;
  padding: 0;
}

.acc-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--border);
}

.link-btn {
  background: none;
  border: none;
  color: var(--accent);
  padding: 0.35rem 0;
  text-align: left;
  width: 100%;
  font-size: 0.85rem;
}

.link-btn:hover {
  background: none;
  text-decoration: underline;
}

.pool-card h3 {
  margin: 0 0 0.35rem;
  font-size: 0.95rem;
}

.pool-list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}

.pool-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.35rem 0;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--border);
}
</style>
