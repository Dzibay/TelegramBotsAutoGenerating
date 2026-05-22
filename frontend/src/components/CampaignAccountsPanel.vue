<template>
  <section class="card accounts-panel">
    <div class="panel-head">
      <div>
        <h3>Аккаунты Telegram</h3>
        <p class="panel-desc">
          Добавьте подготовленные аккаунты и нажмите «Проверить», чтобы убедиться, что вход в Telegram работает.
          Для массового создания ботов нужен статус «Готов». Счётчик ботов — как в Telegram.
        </p>
      </div>
      <div v-if="accounts.length" class="head-actions">
        <button
          type="button"
          class="btn btn-sm btn-ghost"
          :disabled="verifyingAll || busy"
          @click="$emit('verify-all')"
        >
          {{ verifyingAll ? 'Проверка…' : 'Проверить все' }}
        </button>
      </div>
    </div>

    <div v-if="summary" class="summary" :class="summaryClass">
      {{ summary }}
    </div>

    <p v-if="!accounts.length" class="muted empty">Нет аккаунтов в кампании</p>

    <ul v-else class="account-list">
      <li
        v-for="a in accounts"
        :key="a.id"
        class="account-card"
        :class="{ 'account-card--ok': a.status === 'ready', 'account-card--err': a.status === 'error' }"
      >
        <div class="acc-top">
          <div class="acc-title">
            <strong>{{ a.label || a.phone || `Аккаунт #${a.id}` }}</strong>
            <span v-if="a.phone" class="phone">{{ a.phone }}</span>
          </div>
          <StatusBadge :status="a.status" />
        </div>

        <p class="acc-meta">
          Ботов на аккаунте: {{ botCountLabel(a) }} / {{ a.max_bots_limit }}
          <span v-if="a.bots_in_db != null && a.bots_in_db !== a.bots_created" class="sub-meta">
            · в этой кампании: {{ a.bots_in_db }}
          </span>
          <span v-if="a.tdata_on_disk === false" class="warn-tag">· нет файлов сессии</span>
          <span v-else-if="a.can_create_bots" class="ok-tag">· можно создавать ботов</span>
        </p>

        <p v-if="a.health_hint" class="health-hint">{{ a.health_hint }}</p>
        <p v-if="a.last_error && a.status === 'error'" class="last-error">{{ a.last_error }}</p>
        <p v-if="a.verify_message" class="verify-msg" :class="a.verified ? 'ok' : 'err'">
          {{ a.verify_message }}
        </p>

        <InlineTaskIndicator
          :account-id="a.id"
          fallback-label="Связь с Telegram…"
        />

        <div class="acc-actions">
          <button
            type="button"
            class="btn btn-sm btn-ghost"
            :disabled="busyId === a.id || busy"
            @click="$emit('verify', a)"
          >
            {{ busyId === a.id ? 'Проверка…' : 'Проверить' }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-ghost"
            :disabled="botsBusyId === a.id || busy"
            @click="toggleBots(a)"
          >
            {{ botsBusyId === a.id ? 'Загрузка…' : botsExpanded[a.id] ? 'Скрыть ботов' : 'Показать ботов' }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-ghost danger"
            :disabled="busyId === a.id || busy"
            @click="$emit('remove', a)"
          >
            Убрать
          </button>
        </div>

        <div v-if="botsExpanded[a.id]" class="bots-block">
          <p v-if="botsError[a.id]" class="bots-err">{{ botsError[a.id] }}</p>
          <p v-else-if="!botsLists[a.id]?.length" class="muted small">
            На этом аккаунте пока нет ботов
          </p>
          <ul v-else class="bot-mini-list">
            <li v-for="b in botsLists[a.id]" :key="b.username" class="bot-mini-item">
              <div class="bot-mini-info">
                <a
                  v-if="b.username"
                  :href="`https://t.me/${b.username}`"
                  target="_blank"
                  rel="noopener"
                  class="bot-link"
                >@{{ b.username }}</a>
                <span v-if="b.in_app" class="tag tag-app">в кампании</span>
                <span v-else class="tag tag-ext">только в Telegram</span>
                <span v-if="!b.in_telegram" class="tag tag-warn">удалён в Telegram</span>
              </div>
              <div class="bot-delete-cell">
                <button
                  type="button"
                  class="btn btn-xs danger"
                  :disabled="deleteBusy === `${a.id}:${b.username}` || busy"
                  @click="$emit('delete-bot', { account: a, bot: b })"
                >
                  {{ deleteBusy === `${a.id}:${b.username}` ? 'Удаление…' : 'Удалить' }}
                </button>
                <InlineTaskIndicator
                  :account-id="a.id"
                  :username="b.username"
                />
              </div>
            </li>
          </ul>
        </div>
      </li>
    </ul>

    <div v-if="canAdd" class="add-prepared">
      <p class="muted small">Добавить подготовленный аккаунт</p>
      <PreparedAccountPicker ref="pickerRef" v-model="selectedIds" />
      <button
        type="button"
        class="btn btn-add"
        :disabled="!selectedIds.length || attaching"
        @click="onAttach"
      >
        {{ attaching ? 'Добавление и проверка…' : 'Добавить и проверить' }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue';
import InlineTaskIndicator from './InlineTaskIndicator.vue';
import PreparedAccountPicker from './PreparedAccountPicker.vue';
import StatusBadge from './StatusBadge.vue';

const props = defineProps({
  accounts: { type: Array, default: () => [] },
  canAdd: { type: Boolean, default: true },
  attaching: { type: Boolean, default: false },
  verifyingAll: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  busyId: { type: Number, default: null },
  botsBusyId: { type: Number, default: null },
  deleteBusy: { type: String, default: null },
  botsLists: { type: Object, default: () => ({}) },
  botsError: { type: Object, default: () => ({}) },
  attachMessage: { type: String, default: null },
});

const emit = defineEmits(['attach', 'verify', 'verify-all', 'remove', 'load-bots', 'delete-bot']);

const selectedIds = ref([]);
const pickerRef = ref(null);
const botsExpanded = reactive({});

const readyCount = computed(() => props.accounts.filter((a) => a.status === 'ready').length);
const errorCount = computed(() => props.accounts.filter((a) => a.status === 'error').length);

const summary = computed(() => {
  if (props.attachMessage) return props.attachMessage;
  if (!props.accounts.length) return null;
  return `Готовых: ${readyCount.value} · с ошибкой: ${errorCount.value} · всего: ${props.accounts.length}`;
});

const summaryClass = computed(() => {
  if (errorCount.value > 0) return 'summary--warn';
  if (readyCount.value > 0) return 'summary--ok';
  return '';
});

function botCountLabel(a) {
  const tg = a.bots_in_telegram ?? a.bots_created;
  return tg ?? 0;
}

function toggleBots(account) {
  const id = account.id;
  if (botsExpanded[id]) {
    botsExpanded[id] = false;
    return;
  }
  botsExpanded[id] = true;
  emit('load-bots', account);
}

function onAttach() {
  if (!selectedIds.value.length) return;
  emit('attach', [...selectedIds.value]);
  selectedIds.value = [];
}

defineExpose({
  reloadPicker: () => pickerRef.value?.reload?.(),
  collapseBots: (accountId) => {
    if (accountId != null) botsExpanded[accountId] = false;
  },
});
</script>

<style scoped>
.accounts-panel {
  padding: 1rem;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.panel-head h3 {
  margin: 0 0 0.25rem;
  font-size: 0.95rem;
}

.panel-desc {
  margin: 0;
  font-size: 0.8rem;
  color: var(--muted);
  max-width: 28rem;
}

.head-actions {
  flex-shrink: 0;
}

.summary {
  margin: 0 0 0.75rem;
  padding: 0.5rem 0.65rem;
  border-radius: 8px;
  font-size: 0.85rem;
}

.summary--ok {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #86efac;
}

.summary--warn {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.35);
  color: #fde047;
}

.empty {
  margin: 0;
}

.account-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.account-card {
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
}

.account-card--ok {
  border-color: rgba(34, 197, 94, 0.35);
}

.account-card--err {
  border-color: rgba(239, 68, 68, 0.4);
}

.acc-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.acc-title strong {
  display: block;
}

.phone {
  font-size: 0.8rem;
  color: var(--muted);
}

.acc-meta {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.sub-meta {
  color: var(--muted);
}

.warn-tag {
  color: #f87171;
}

.ok-tag {
  color: #4ade80;
}

.health-hint,
.last-error,
.verify-msg {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
}

.last-error {
  color: #f87171;
}

.verify-msg.ok {
  color: #4ade80;
}

.verify-msg.err {
  color: #f87171;
}

.acc-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-top: 0.5rem;
}

.bots-block {
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--border);
}

.bots-err {
  margin: 0;
  font-size: 0.78rem;
  color: #f87171;
}

.bot-mini-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.bot-mini-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.8rem;
}

.bot-delete-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 5.5rem;
}

.bot-mini-info {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.bot-link {
  color: #93c5fd;
  text-decoration: none;
}

.bot-link:hover {
  text-decoration: underline;
}

.tag {
  font-size: 0.68rem;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.tag-app {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}

.tag-ext {
  background: rgba(234, 179, 8, 0.15);
  color: #fde047;
}

.tag-warn {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.btn-xs {
  font-size: 0.72rem;
  padding: 0.2rem 0.45rem;
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
</style>
