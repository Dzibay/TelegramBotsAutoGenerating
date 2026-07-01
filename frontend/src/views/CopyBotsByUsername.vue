<template>
  <div class="copy-bots">
    <header class="page-header">
      <RouterLink :to="{ name: 'campaign-workspace', params: { id: campaignId } }" class="back">
        ← Назад в кампанию
      </RouterLink>
      <h1>Копирование ботов по username</h1>
      <p class="subtitle">
        Создаёт новых ботов через BotFather, копируя профиль исходного бота
        (имя, «О боте», описание, аватар и медиа описания). Текст после /start,
        кнопка и реферальная ссылка задаются как в массовом создании — из настроек
        кампании. Одна пара на строку: <code>кого_копируем какого_создаём</code>.
      </p>
    </header>

    <CampaignActiveJobsPanel
      v-if="campaignId"
      ref="jobsPanelRef"
      :campaign-id="campaignId"
      :history-link="{ name: 'campaign-job-history', params: { id: campaignId } }"
    />

    <section class="card block">
      <div class="form-group">
        <label for="account">Аккаунт для создания</label>
        <select id="account" v-model.number="accountId" :disabled="loading || !readyAccounts.length">
          <option v-if="readyAccounts.length >= 1" :value="MULTI_ACCOUNT_MODE">
            Все аккаунты (ротация) — {{ readyAccounts.length }} шт.
          </option>
          <option v-for="a in readyAccounts" :key="a.id" :value="a.id">
            {{ accountOptionLabel(a) }}
          </option>
        </select>
        <p v-if="!readyAccounts.length" class="error-text">
          Нет готовых аккаунтов в кампании.
        </p>
      </div>

      <div class="form-group">
        <label for="pairs">Пары username</label>
        <textarea
          id="pairs"
          v-model="pairsRaw"
          rows="8"
          placeholder="Одна пара на строку: исходный целевой, например:&#10;durov_bot my_new_bot&#10;source_bot target_bot"
          :disabled="loading"
        />
        <p class="field-hint">
          Распознано пар: <strong>{{ parsedPairs.length }}</strong>
          <span v-if="parsedPairs.length > 50" class="error-text"> — максимум 50 за раз</span>
        </p>
        <ul v-if="invalidLines.length" class="error-list">
          <li v-for="(line, i) in invalidLines" :key="i">
            ⚠️ Пропущена строка «{{ line }}» — нужны два username, целевой обязан
            оканчиваться на «bot»
          </li>
        </ul>
      </div>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <p v-if="queuedMessage" class="ok">{{ queuedMessage }}</p>

      <div class="actions">
        <button
          type="button"
          class="btn"
          :disabled="!canSubmit"
          @click="runCopy"
        >
          {{ loading ? 'Постановка в очередь…' : `Скопировать (${parsedPairs.length})` }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';
import { accountDisplayLabel } from '../utils/accountLabel';
import { getAccountFloodRemainingSec, formatWaitLabel } from '../utils/floodWait';
import { formatApiError } from '../utils/apiErrorMessage.js';
import CampaignActiveJobsPanel from '../components/CampaignActiveJobsPanel.vue';

const MULTI_ACCOUNT_MODE = 0;

const route = useRoute();
const campaignId = computed(() => Number(route.params.id));

const accounts = ref([]);
const accountId = ref(MULTI_ACCOUNT_MODE);
const pairsRaw = ref('');
const loading = ref(false);
const submitError = ref('');
const queuedMessage = ref('');
const jobsPanelRef = ref(null);

const readyAccounts = computed(() =>
  accounts.value.filter(
    (a) => a.status === 'ready' && a.can_create_bots !== false && !a.is_banned
  )
);

// Целевой username: 5–32 символа, латиница/цифры/_, начинается с буквы, оканчивается на bot.
const TARGET_USERNAME_RE = /^[a-z][a-z0-9_]{2,28}bot$/;

// Разбор строк: возвращает валидные пары [source, target].
const parsedPairs = computed(() => {
  const seen = new Set();
  const out = [];
  for (const rawLine of pairsRaw.value.split(/\r?\n/)) {
    const tokens = rawLine.trim().split(/[\s,;]+/).filter(Boolean);
    if (tokens.length < 2) continue;
    const source = tokens[0].replace(/^@/, '');
    const target = tokens[1].replace(/^@/, '').toLowerCase();
    if (!source || !TARGET_USERNAME_RE.test(target)) continue;
    if (seen.has(target)) continue;
    seen.add(target);
    out.push([source, target]);
  }
  return out;
});

const invalidLines = computed(() => {
  const bad = [];
  for (const rawLine of pairsRaw.value.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const tokens = line.split(/[\s,;]+/).filter(Boolean);
    if (tokens.length < 2) {
      bad.push(line);
      continue;
    }
    const target = tokens[1].replace(/^@/, '').toLowerCase();
    if (!TARGET_USERNAME_RE.test(target)) bad.push(line);
  }
  return bad;
});

const selectedAccountIds = computed(() => {
  if (accountId.value === MULTI_ACCOUNT_MODE) {
    return readyAccounts.value.map((a) => a.id);
  }
  return [accountId.value];
});

const canSubmit = computed(
  () =>
    !loading.value &&
    parsedPairs.value.length > 0 &&
    parsedPairs.value.length <= 50 &&
    selectedAccountIds.value.length > 0
);

function accountOptionLabel(a) {
  const base = `${accountDisplayLabel(a)} (${a.bots_created}/${a.max_bots_limit})`;
  const flood = getAccountFloodRemainingSec(a);
  if (flood > 0) return `${base} · пауза ${formatWaitLabel(flood)}`;
  return base;
}

async function loadAccounts() {
  try {
    accounts.value = await campaignService.getAccounts(campaignId.value);
  } catch (e) {
    submitError.value = formatApiError(e, 'Не удалось загрузить аккаунты');
  }
}

async function runCopy() {
  if (!canSubmit.value) return;
  loading.value = true;
  submitError.value = '';
  queuedMessage.value = '';
  try {
    const res = await botService.copyByUsername(
      campaignId.value,
      selectedAccountIds.value,
      parsedPairs.value
    );
    const queued = res?.data?.queued ? parsedPairs.value.length : 0;
    queuedMessage.value = res?.message || `Копирование ${queued} ботов поставлено в очередь`;
    pairsRaw.value = '';
    jobsPanelRef.value?.loadJobs?.();
  } catch (e) {
    submitError.value = formatApiError(e, 'Не удалось поставить копирование в очередь');
  } finally {
    loading.value = false;
  }
}

onMounted(loadAccounts);
</script>

<style scoped>
.copy-bots {
  max-width: 720px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1.5rem;
}

.back {
  display: inline-block;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}

.subtitle {
  color: var(--text-muted, #888);
  font-size: 0.9rem;
  line-height: 1.5;
}

.subtitle code,
.field-hint code {
  font-family: monospace;
  font-size: 0.85em;
}

.block {
  margin-bottom: 1.25rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

select,
textarea {
  width: 100%;
}

textarea {
  font-family: monospace;
  resize: vertical;
}

.field-hint {
  font-size: 0.8rem;
  color: var(--text-muted, #888);
}

.actions {
  margin-top: 0.5rem;
}

.ok {
  color: var(--success, #2e9e5b);
  font-size: 0.9rem;
}

.error-list {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0;
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--danger, #d04444);
}
</style>