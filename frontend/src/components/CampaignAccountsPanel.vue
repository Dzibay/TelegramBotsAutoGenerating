<template>
  <section class="card accounts-panel">
    <div class="panel-head">
      <div>
        <h3>Аккаунты Telegram</h3>
        <p class="panel-desc">
          Добавьте подготовленные аккаунты и нажмите «Проверить все». Для создания ботов нужен статус «Готов».
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

    <p v-if="!accounts.length" class="empty">
      <EmptyState
        icon="📱"
        title="Нет аккаунтов в кампании"
        description="Добавьте подготовленные Telegram-аккаунты из пула — они нужны для создания ботов через BotFather."
        compact
      />
    </p>

    <ul v-else class="account-list">
      <li
        v-for="a in accounts"
        :key="a.id"
        class="account-card"
        :class="{
          'account-card--ok': a.status === 'ready' && !a.is_banned,
          'account-card--err': a.status === 'error',
          'account-card--banned': a.is_banned,
        }"
      >
        <div class="acc-top">
          <div class="acc-title">
            <div v-if="editingId === a.id" class="label-edit">
              <input
                v-model="editLabel"
                type="text"
                maxlength="200"
                placeholder="Название аккаунта"
                @keydown.enter="saveLabel(a)"
                @keydown.esc="cancelEdit"
              />
              <button
                type="button"
                class="btn btn-xs"
                :disabled="labelSavingId === a.id"
                @click="saveLabel(a)"
              >
                {{ labelSavingId === a.id ? '…' : 'OK' }}
              </button>
              <button type="button" class="btn btn-xs btn-ghost" @click="cancelEdit">×</button>
            </div>
            <template v-else>
              <strong>{{ displayLabel(a) }}</strong>
              <button
                type="button"
                class="btn-edit-name"
                title="Изменить название"
                :disabled="busy"
                @click="startEdit(a)"
              >
                ✎
              </button>
              <span v-if="a.is_banned" class="ban-tag">Забанен</span>
            </template>
          </div>
          <StatusBadge :status="a.status" />
        </div>

        <label v-if="editingId !== a.id" class="ban-toggle">
          <input
            type="checkbox"
            :checked="!!a.is_banned"
            :disabled="busy || labelSavingId === a.id || busyId === a.id"
            @change="toggleBanned(a, $event.target.checked)"
          />
          Аккаунт забанен (нельзя выбирать при создании ботов)
        </label>

        <p class="acc-meta">
          Ботов: {{ botCountLabel(a) }} / {{ a.max_bots_limit }}
          <span v-if="a.bots_in_db != null && a.bots_in_db !== a.bots_created" class="sub-meta">
            · в кампании: {{ a.bots_in_db }}
          </span>
          <span v-if="a.tdata_on_disk === false" class="warn-tag">· нет экспорта</span>
          <span v-else-if="floodRemainingSec(a) > 0" class="flood-tag">
            · пауза BotFather: {{ formatWaitLabel(floodRemainingSec(a)) }}
          </span>
          <span v-else-if="a.can_create_bots" class="ok-tag">· можно создавать</span>
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
            :aria-expanded="!!botsExpanded[a.id]"
            @click="toggleBots(a)"
          >
            {{ botsBusyId === a.id ? 'Загрузка…' : botsExpanded[a.id] ? 'Скрыть список' : 'Боты на аккаунте' }}
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
                <span v-if="!b.in_telegram" class="tag tag-warn">нет в /mybots</span>
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
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue';
import InlineTaskIndicator from './InlineTaskIndicator.vue';
import EmptyState from './EmptyState.vue';
import PreparedAccountPicker from './PreparedAccountPicker.vue';
import StatusBadge from './StatusBadge.vue';
import { accountDisplayLabel } from '../utils/accountLabel';
import { formatWaitLabel, getAccountFloodRemainingSec } from '../utils/floodWait';

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

const emit = defineEmits(['attach', 'verify', 'verify-all', 'remove', 'load-bots', 'delete-bot', 'update-label', 'update-banned']);

const selectedIds = ref([]);
const pickerRef = ref(null);
const botsExpanded = reactive({});
const editingId = ref(null);
const editLabel = ref('');
const labelSavingId = ref(null);
const nowTick = ref(Date.now());
let floodTickTimer = null;

onMounted(() => {
  floodTickTimer = setInterval(() => {
    nowTick.value = Date.now();
  }, 1000);
});

onUnmounted(() => {
  if (floodTickTimer) clearInterval(floodTickTimer);
});

function floodRemainingSec(account) {
  return getAccountFloodRemainingSec(account, nowTick.value);
}

function displayLabel(a) {
  return accountDisplayLabel(a);
}

function startEdit(account) {
  editingId.value = account.id;
  editLabel.value = account.label || '';
  nextTick(() => {
    const el = document.querySelector('.label-edit input');
    el?.focus();
  });
}

function cancelEdit() {
  editingId.value = null;
  editLabel.value = '';
}

function saveLabel(account) {
  const next = editLabel.value.trim();
  if (next === (account.label || '').trim()) {
    cancelEdit();
    return;
  }
  labelSavingId.value = account.id;
  emit('update-label', { account, label: next || null });
  cancelEdit();
  labelSavingId.value = null;
}

function toggleBanned(account, checked) {
  if (!!account.is_banned === checked) return;
  emit('update-banned', { account, is_banned: checked });
}

const readyCount = computed(() => props.accounts.filter((a) => a.status === 'ready' && !a.is_banned).length);
const errorCount = computed(() => props.accounts.filter((a) => a.status === 'error').length);
const bannedCount = computed(() => props.accounts.filter((a) => a.is_banned).length);

const summary = computed(() => {
  if (props.attachMessage) return props.attachMessage;
  if (!props.accounts.length) return null;
  return `Готовых: ${readyCount.value} · с ошибкой: ${errorCount.value}${bannedCount.value ? ` · забанено: ${bannedCount.value}` : ''} · всего: ${props.accounts.length}`;
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
  padding: 1.25rem;
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
  padding: 0.6rem 0.8rem;
  border-radius: var(--radius-sm);
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
  padding: 0.9rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: rgba(8, 12, 20, 0.45);
  transition: border-color 0.15s;
}

.account-card--ok {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.04);
}

.account-card--err {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.04);
}

.account-card--banned {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.06);
  opacity: 0.92;
}

.acc-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.acc-title strong {
  display: inline;
}

.label-edit {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.label-edit input {
  flex: 1;
  min-width: 8rem;
  font-size: 0.85rem;
}

.btn-edit-name {
  margin-left: 0.35rem;
  padding: 0.1rem 0.35rem;
  border: none;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1;
  border-radius: 4px;
}

.btn-edit-name:hover:not(:disabled) {
  color: var(--accent);
  background: var(--accent-soft);
}

.ban-tag {
  display: inline-block;
  margin-top: 0.25rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 600;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.ban-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  margin-top: 0.45rem;
  font-size: 0.78rem;
  color: var(--muted);
  cursor: pointer;
}

.ban-toggle input {
  width: auto;
  margin-top: 0.15rem;
  flex-shrink: 0;
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

.flood-tag {
  color: #fbbf24;
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
