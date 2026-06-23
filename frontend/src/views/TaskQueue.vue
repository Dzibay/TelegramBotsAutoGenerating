<template>
  <section class="queue-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Фоновые задачи</p>
        <h1>Единая очередь</h1>
        <p class="muted">
          Создание ботов, массовые партии и синхронизация BotFather выполняются здесь.
        </p>
      </div>
      <button class="btn btn-ghost" type="button" :disabled="store.loading" @click="store.refresh()">
        Обновить
      </button>
    </header>

    <div v-if="store.error" class="alert error">{{ store.error }}</div>

    <div class="summary-grid">
      <div class="summary-card">
        <span>Активно</span>
        <strong>{{ store.activeCount }}</strong>
      </div>
      <div class="summary-card">
        <span>В списке</span>
        <strong>{{ store.tasks.length }}</strong>
      </div>
    </div>

    <div class="task-list">
      <article v-for="task in store.tasks" :key="task.id" class="task-card">
        <div class="task-main">
          <div>
            <div class="task-title">
              <StatusBadge :status="task.status" />
              <strong>{{ taskTitle(task) }}</strong>
              <span class="task-id">#{{ task.id }}</span>
            </div>
            <p class="muted compact">{{ task.progress_message || task.error_message || 'Ожидает обработки' }}</p>
            <p class="task-meta">
              <span v-if="task.campaign_title">{{ task.campaign_title }}</span>
              <span v-if="task.bot_username">@{{ task.bot_username }}</span>
              <span v-if="task.account_ids?.length">{{ accountLabel(task.account_ids) }}</span>
              <span>{{ formatDate(task.created_at) }}</span>
            </p>
          </div>
          <div class="task-actions">
            <RouterLink
              v-if="task.campaign_id"
              class="btn btn-xs btn-ghost"
              :to="{ name: 'campaign-workspace', params: { id: task.campaign_id } }"
            >
              Кампания
            </RouterLink>
            <RouterLink
              v-if="task.bot_id"
              class="btn btn-xs btn-ghost"
              :to="{ name: 'bot-edit', params: { id: task.bot_id } }"
            >
              Бот
            </RouterLink>
            <button class="btn btn-xs btn-ghost" type="button" @click="toggleLogs(task.id)">
              Логи
            </button>
            <button
              v-if="isActive(task)"
              class="btn btn-xs btn-ghost danger"
              type="button"
              :disabled="busyId === task.id"
              @click="cancel(task.id)"
            >
              Стоп
            </button>
            <button
              v-else-if="task.status !== 'completed'"
              class="btn btn-xs btn-ghost"
              type="button"
              :disabled="busyId === task.id"
              @click="retry(task.id)"
            >
              Повторить
            </button>
          </div>
        </div>

        <div v-if="expandedId === task.id" class="logs">
          <div v-if="logsLoading" class="muted">Загрузка логов…</div>
          <div v-else-if="!logs.length" class="muted">Логов пока нет.</div>
          <div v-for="log in logs" :key="log.id" class="log-line" :class="`log-${log.level}`">
            <span>{{ formatDate(log.created_at) }}</span>
            <strong>{{ log.level }}</strong>
            <p>{{ log.message }}</p>
          </div>
        </div>
      </article>

      <div v-if="!store.loading && !store.tasks.length" class="empty">
        Очередь пуста. Новые задачи появятся здесь сразу после запуска.
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import StatusBadge from '../components/StatusBadge.vue';
import { taskService } from '../services/taskService';
import { useTaskQueueStore } from '../stores/taskQueueStore';

const store = useTaskQueueStore();
const expandedId = ref(null);
const logs = ref([]);
const logsLoading = ref(false);
const busyId = ref(null);

onMounted(() => store.startPolling());

function isActive(task) {
  return ['queued', 'running'].includes(task.status);
}

function taskTitle(task) {
  if (task.task_type === 'bot_telegram_sync') return 'Синхронизация BotFather';
  if (task.task_type === 'creation') {
    const mode = task.payload?.mode || 'creation';
    const labels = {
      single: 'Создание бота',
      manual: 'Ручная партия',
      manual_multi: 'Мультиаккаунтная партия',
      batch_create: 'Пакетное создание',
      creation: 'Создание ботов',
    };
    return labels[mode] || 'Создание ботов';
  }
  return task.task_type;
}

function accountLabel(ids = []) {
  if (ids.length === 1) return `Аккаунт #${ids[0]}`;
  return `${ids.length} акк.`;
}

function formatDate(value) {
  if (!value) return '';
  return new Date(value).toLocaleString('ru-RU');
}

async function toggleLogs(taskId) {
  if (expandedId.value === taskId) {
    expandedId.value = null;
    logs.value = [];
    return;
  }
  expandedId.value = taskId;
  logsLoading.value = true;
  try {
    logs.value = await taskService.getLogs(taskId, 0, { minLevel: 'info' });
  } finally {
    logsLoading.value = false;
  }
}

async function cancel(taskId) {
  busyId.value = taskId;
  try {
    await store.cancel(taskId);
  } finally {
    busyId.value = null;
  }
}

async function retry(taskId) {
  busyId.value = taskId;
  try {
    await store.retry(taskId);
  } finally {
    busyId.value = null;
  }
}
</script>

<style scoped>
.queue-page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.page-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 0.25rem;
  color: var(--accent);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.page-head h1 {
  margin: 0;
}

.muted {
  margin: 0;
  color: var(--muted);
}

.compact {
  margin-top: 0.35rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.summary-card,
.task-card,
.empty {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}

.summary-card {
  padding: 1rem;
}

.summary-card span {
  display: block;
  color: var(--muted);
  font-size: 0.8rem;
}

.summary-card strong {
  display: block;
  margin-top: 0.35rem;
  font-size: 1.6rem;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.task-card {
  padding: 1rem;
}

.task-main {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.task-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.task-id,
.task-meta {
  color: var(--muted);
  font-size: 0.8rem;
}

.task-meta {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin: 0.5rem 0 0;
}

.task-actions {
  display: flex;
  gap: 0.4rem;
  align-items: flex-start;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.logs {
  margin-top: 1rem;
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

.log-line {
  display: grid;
  grid-template-columns: 150px 60px 1fr;
  gap: 0.75rem;
  padding: 0.35rem 0;
  color: var(--text);
  font-size: 0.85rem;
}

.log-line span,
.log-line strong {
  color: var(--muted);
}

.log-line p {
  margin: 0;
}

.log-error p,
.log-warn p {
  color: var(--warning);
}

.empty,
.alert {
  padding: 1rem;
}

.alert.error {
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: var(--radius);
  background: rgba(248, 113, 113, 0.08);
  color: #fecaca;
}
</style>
