<template>
  <div class="bulk-create">
    <header class="page-header">
      <h1>Массовое создание</h1>
      <p class="subtitle">
        Таблица ботов: аккаунт, фраза для AI (необязательно), имя и username. Фраза нужна только для генерации
        текстов нейросетью.
      </p>
    </header>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>

    <section v-else class="card block">
      <div
        v-if="campaignResourceUrl && !useCustomUrl"
        class="url-from-campaign card-inner"
      >
        <label>Ссылка на сервис</label>
        <p class="url-value">
          <a :href="campaignResourceUrl" target="_blank" rel="noopener noreferrer">{{ campaignResourceUrl }}</a>
        </p>
        <p class="field-hint">Из настроек кампании — для всей партии.</p>
        <button type="button" class="link-btn" @click="useCustomUrl = true">Другая ссылка для этой партии</button>
      </div>
      <div v-else class="form-group">
        <label>Ссылка на сервис *</label>
        <input v-model="targetUrl" type="url" placeholder="https://example.com" />
        <p class="field-hint">Одна ссылка для всех ботов в этой партии.</p>
        <button v-if="campaignResourceUrl" type="button" class="link-btn" @click="useCampaignUrl">
          ← Вернуть ссылку из кампании
        </button>
      </div>

      <BotLinkModeField v-model="linkMode" :preview-url="linkPreview" />

      <p v-if="rowsWithAccountCount" class="rows-summary muted">
        Строк с аккаунтом: {{ rowsWithAccountCount }} · готово к созданию: {{ rowsReadyCount }}
        <span v-if="rowsAiReadyCount"> · для AI: {{ rowsAiReadyCount }}</span>
      </p>

      <ul v-if="batchValidation.errors.length" class="val-list val-list--err">
        <li v-for="(msg, i) in batchValidation.errors" :key="'e' + i">{{ msg }}</li>
      </ul>
      <ul v-if="batchValidation.warnings.length" class="val-list val-list--warn">
        <li v-for="(msg, i) in batchValidation.warnings" :key="'w' + i">{{ msg }}</li>
      </ul>

      <div class="rows-head">
        <h3>Боты в партии</h3>
        <div class="rows-actions">
          <button type="button" class="btn btn-sm btn-ghost" @click="addRow">+ Строка</button>
          <button type="button" class="btn btn-sm btn-ghost" @click="addRows(5)">+5</button>
        </div>
      </div>

      <div class="bulk-table-scroll">
      <div class="bulk-table">
        <div class="bulk-head bulk-grid">
          <span>#</span>
          <span>Аккаунт *</span>
          <span>Фраза (AI)</span>
          <span>Имя</span>
          <span>Username</span>
          <span>Статус</span>
          <span></span>
        </div>

        <div v-for="(row, i) in rows" :key="row.id" class="bulk-row">
          <div class="bulk-grid bulk-main">
            <span class="row-num">{{ i + 1 }}</span>
            <select v-model.number="row.accountId">
              <option :value="null" disabled>Аккаунт</option>
              <option v-for="a in readyAccounts" :key="a.id" :value="a.id">
                {{ accountLabel(a) }}
              </option>
            </select>
            <input
              v-model="row.keyword"
              type="text"
              placeholder="для AI"
              @keydown.enter.prevent
            />
            <input
              :value="row.draft?.display_name ?? ''"
              type="text"
              placeholder="Имя бота"
              @input="onDraftField(row, 'display_name', $event.target.value)"
            />
            <input
              :value="row.draft?.username ?? ''"
              type="text"
              placeholder="@username"
              @input="onDraftField(row, 'username', $event.target.value)"
            />
            <span class="row-status" :class="statusClass(row)">{{ statusText(row) }}</span>
            <div class="row-btns">
              <button
                type="button"
                class="btn btn-xs btn-ghost"
                aria-label="Заполнить вручную"
                title="Заполнить вручную"
                @click="ensureDraft(row)"
              >
                ✎
              </button>
              <button
                type="button"
                class="btn btn-xs btn-ghost"
                :disabled="!row.accountId || !row.keyword.trim() || generating"
                aria-label="Сгенерировать AI"
                title="Сгенерировать по фразе"
                @click="generateOne(row)"
              >
                AI
              </button>
              <button
                type="button"
                class="btn btn-xs btn-ghost danger"
                :disabled="rows.length <= 1"
                @click="removeRow(i)"
              >
                ×
              </button>
            </div>
          </div>
          <details v-if="row.draft" class="bulk-expand">
            <summary>Тексты и предпросмотр</summary>
            <div class="expand-layout">
              <div class="expand-fields">
                <div class="form-group">
                  <label>Описание (до Start)</label>
                  <textarea v-model="row.draft.description" rows="2" />
                </div>
                <div class="form-group">
                  <label>Приветствие</label>
                  <textarea v-model="row.draft.welcome_message" rows="2" />
                </div>
              </div>
              <BotTelegramPreview
                class="preview-compact"
                :display-name="row.draft.display_name"
                :username="row.draft.username"
                :about-text="row.draft.about_text"
                :description="row.draft.description"
                :welcome-message="row.draft.welcome_message"
                :welcome-button-enabled="row.draft.welcome_button_enabled"
                :welcome-button-text="row.draft.welcome_button_text"
                :public-link="row.draft.public_link || linkPreview"
              />
            </div>
          </details>
          <p v-if="row.error" class="row-err">{{ row.error }}</p>
        </div>
      </div>
      </div>

      <div class="action-bar">
        <button type="button" class="btn-ai" :disabled="!canGenerate || generating || batchValidation.errors.length" @click="generateAll">
          {{ generating ? `Генерация ${genProgress}…` : '✨ Сгенерировать по фразам (AI)' }}
        </button>
        <label class="check">
          <input v-model="autoStart" type="checkbox" />
          Запустить ботов после создания
        </label>
      </div>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <div class="submit-bar">
        <button
          type="button"
          class="btn"
          :disabled="!canCreate || creating || batchValidation.errors.length"
          @click="createAll"
        >
          {{ creating ? `Создание ${createProgress}…` : 'Создать ботов в Telegram' }}
        </button>
        <details class="advanced-queue">
          <summary>Для опытных: очередь без правки (нужны фразы)</summary>
          <p class="field-hint">Фоновая задача по строкам с аккаунтом и фразой, без предпросмотра.</p>
          <button
            type="button"
            class="btn-ghost btn-sm"
            :disabled="creating || !rowsAiReadyCount || batchValidation.errors.length"
            @click="createViaJob"
          >
            Запустить через очередь
          </button>
        </details>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotTelegramPreview from '../components/BotTelegramPreview.vue';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { applyCampaignTextDefaults, campaignTextDefaultsSnapshot } from '../utils/campaignTextDefaults';
import { validateBulkBatch } from '../utils/bulkBatchValidate';

let rowSeq = 0;

function emptyDraft() {
  const snap = campaignTextDefaultsSnapshot(campaign.value);
  return {
    display_name: '',
    username: '',
    description: snap.description,
    about_text: snap.about_text,
    welcome_message: snap.welcome_message,
    welcome_button_enabled: true,
    welcome_button_text: 'Перейти по ссылке',
    redirect_slug: null,
    public_link: null,
  };
}

function newRow() {
  return { id: ++rowSeq, accountId: null, keyword: '', draft: null, error: null };
}

const route = useRoute();
const router = useRouter();
const taskStore = useAsyncTaskStore();
const campaignId = computed(() => Number(route.params.id));

const loadError = ref(null);
const campaign = ref({});
const accounts = ref([]);
const campaignResourceUrl = ref('');
const useCustomUrl = ref(false);
const targetUrl = ref('');
const linkMode = ref('redirect');
const rows = ref([newRow(), newRow(), newRow()]);
const autoStart = ref(true);
const generating = ref(false);
const genProgress = ref('');
const creating = ref(false);
const createProgress = ref('');
const submitError = ref(null);

const readyAccounts = computed(() =>
  accounts.value.filter((a) => a.status === 'ready' && a.can_create_bots !== false)
);

const effectiveTargetUrl = computed(() => {
  if (campaignResourceUrl.value && !useCustomUrl.value) return campaignResourceUrl.value;
  return targetUrl.value;
});

const linkPreview = computed(() => {
  const first = rows.value.find((r) => r.draft?.public_link);
  return first?.draft?.public_link || effectiveTargetUrl.value.trim() || '';
});

const rowsWithAccountCount = computed(() => rows.value.filter((r) => r.accountId).length);

const rowsWithDraft = computed(() =>
  rows.value.filter((r) => r.draft?.display_name?.trim() && r.draft?.username?.trim())
);

const rowsReadyCount = computed(() => rowsWithDraft.value.length);

const rowsAiReadyCount = computed(
  () => rows.value.filter((r) => r.accountId && r.keyword.trim()).length
);

const batchValidation = computed(() => validateBulkBatch(rows.value, readyAccounts.value));

const canGenerate = computed(
  () =>
    effectiveTargetUrl.value.trim() &&
    readyAccounts.value.length &&
    rowsAiReadyCount.value > 0 &&
    !batchValidation.value.errors.length
);

const canCreate = computed(
  () => rowsReadyCount.value > 0 && !batchValidation.value.errors.length
);

function useCampaignUrl() {
  useCustomUrl.value = false;
  targetUrl.value = campaignResourceUrl.value;
}

function ensureDraft(row) {
  if (!row.draft) row.draft = emptyDraft();
  else applyCampaignTextDefaults(row.draft, campaign.value);
}

function onDraftField(row, field, value) {
  ensureDraft(row);
  row.draft[field] = value;
}

function accountLabel(a) {
  return a.label || a.phone || `#${a.id}`;
}

function statusText(row) {
  if (row.error) return 'Ошибка';
  if (row.draft?.display_name?.trim() && row.draft?.username?.trim()) return 'Готово';
  if (row.draft) return 'Черновик';
  if (row.keyword.trim()) return 'Ждёт AI';
  return '—';
}

function statusClass(row) {
  if (row.error) return 'err';
  if (row.draft?.display_name?.trim() && row.draft?.username?.trim()) return 'ok';
  return '';
}

function addRow() {
  rows.value.push(newRow());
}

function addRows(n) {
  for (let i = 0; i < n; i++) addRow();
}

function removeRow(i) {
  rows.value.splice(i, 1);
}

function applyDraftFromApi(row, draft) {
  ensureDraft(row);
  row.draft.display_name = draft.display_name;
  row.draft.username = (draft.username || '').replace(/^@/, '');
  row.draft.description = draft.description || '';
  row.draft.about_text = draft.about_text || '';
  row.draft.welcome_message = draft.welcome_message || '';
  row.draft.welcome_button_enabled = draft.welcome_button_enabled !== false;
  row.draft.welcome_button_text = draft.welcome_button_text || 'Перейти по ссылке';
  row.draft.redirect_slug = draft.redirect_slug;
  row.draft.public_link = draft.public_link;
}

async function generateOne(row) {
  if (!row.keyword.trim()) {
    row.error = 'Укажите фразу для AI';
    return;
  }
  if (!row.accountId) {
    row.error = 'Выберите аккаунт';
    return;
  }
  row.error = null;
  try {
    const draft = await botService.generateDraft({
      campaignId: campaignId.value,
      accountId: row.accountId,
      targetUrl: effectiveTargetUrl.value.trim(),
      keyword: row.keyword.trim(),
      linkMode: linkMode.value,
    });
    applyDraftFromApi(row, draft);
  } catch (e) {
    row.error = e.response?.data?.error || 'Ошибка генерации';
  }
}

async function generateAll() {
  generating.value = true;
  submitError.value = null;
  const valid = rows.value.filter((r) => r.accountId && r.keyword.trim());
  if (!valid.length) {
    submitError.value = 'Для AI укажите аккаунт и фразу хотя бы в одной строке';
    generating.value = false;
    return;
  }
  let done = 0;
  for (const row of valid) {
    done += 1;
    genProgress.value = `${done}/${valid.length}`;
    row.error = null;
    try {
      const draft = await botService.generateDraft({
        campaignId: campaignId.value,
        accountId: row.accountId,
        targetUrl: effectiveTargetUrl.value.trim(),
        keyword: row.keyword.trim(),
        linkMode: linkMode.value,
      });
      applyDraftFromApi(row, draft);
    } catch (e) {
      row.error = e.response?.data?.error || 'Ошибка генерации';
    }
  }
  generating.value = false;
  genProgress.value = '';
}

function buildCreateSpec(row) {
  const d = row.draft;
  return {
    campaign_id: campaignId.value,
    telegram_account_id: row.accountId,
    target_url: effectiveTargetUrl.value.trim(),
    display_name: d.display_name.trim(),
    username: d.username.replace(/^@/, '').trim(),
    description: d.description,
    about_text: d.about_text,
    welcome_message: d.welcome_message,
    welcome_button_enabled: d.welcome_button_enabled,
    welcome_button_text: d.welcome_button_text,
    keyword: row.keyword.trim() || null,
    redirect_slug: d.redirect_slug,
    link_mode: linkMode.value,
    create_via_botfather: true,
    auto_start: autoStart.value,
    generate_avatar: true,
  };
}

async function createAll() {
  if (!canCreate.value) {
    submitError.value = 'Заполните имя и username в строках (вручную или через AI)';
    return;
  }
  creating.value = true;
  submitError.value = null;
  const specs = rowsWithDraft.value.map(buildCreateSpec);
  try {
    await taskStore.run('CREATE_BOT', async () => {
      const result = await botService.batchCreate(specs);
      if (result.failed_count > 0) {
        submitError.value = `Создано: ${result.created_count}, ошибок: ${result.failed_count}`;
      }
      if (result.created_count > 0) {
        router.push({
          name: 'campaign-workspace',
          params: { id: campaignId.value },
          query: { tab: 'list' },
        });
      }
    });
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Ошибка создания';
  } finally {
    creating.value = false;
    createProgress.value = '';
  }
}

async function createViaJob() {
  const plans = rows.value
    .filter((r) => r.accountId && r.keyword.trim())
    .map((r) => ({
      telegram_account_id: r.accountId,
      keyword: r.keyword.trim(),
    }));
  if (!plans.length) {
    submitError.value = 'Для очереди нужны строки с аккаунтом и фразой';
    return;
  }
  if (!effectiveTargetUrl.value.trim()) {
    submitError.value = 'Укажите ссылку на сервис';
    return;
  }
  try {
    await campaignService.update(campaignId.value, { resource_url: effectiveTargetUrl.value.trim() });
    await taskStore.run('START_CAMPAIGN', () => campaignService.startPlanned(campaignId.value, plans));
    router.push({
      name: 'campaign-workspace',
      params: { id: campaignId.value },
      query: { tab: 'list' },
    });
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Не удалось запустить';
  }
}

watch(rows, () => {
  submitError.value = null;
}, { deep: true });

watch(
  () => campaign.value,
  (c) => {
    if (!c) return;
    rows.value.forEach((row) => {
      if (row.draft) applyCampaignTextDefaults(row.draft, c);
    });
  }
);

onMounted(async () => {
  try {
    const data = await campaignService.get(campaignId.value);
    campaign.value = data.campaign;
    campaignResourceUrl.value = data.campaign.resource_url || '';
    if (campaignResourceUrl.value) {
      targetUrl.value = campaignResourceUrl.value;
      useCustomUrl.value = false;
    } else {
      useCustomUrl.value = true;
    }
    accounts.value = await campaignService.getAccounts(campaignId.value);
    const first = readyAccounts.value[0];
    if (first) {
      rows.value.forEach((r) => {
        if (!r.accountId) r.accountId = first.id;
      });
    }
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  }
});
</script>

<style scoped>
.bulk-create {
  max-width: 1100px;
}

.page-header {
  margin-bottom: 1.25rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  max-width: 42rem;
}

.block {
  padding: 1.25rem;
}

.rows-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 1.25rem 0 0.5rem;
}

.rows-head h3 {
  margin: 0;
  font-size: 0.95rem;
}

.bulk-grid {
  display: grid;
  grid-template-columns: 2rem 1.1fr 1fr 1fr 1fr 4.5rem 5.5rem;
  gap: 0.4rem;
  align-items: center;
}

.bulk-head {
  font-size: 0.7rem;
  color: var(--muted);
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border);
}

.bulk-row {
  padding: 0.5rem 0;
  border-bottom: 1px solid rgba(45, 58, 77, 0.45);
}

.bulk-main input,
.bulk-main select {
  font-size: 0.82rem;
  padding: 0.35rem 0.45rem;
}

.row-num {
  color: var(--muted);
  font-size: 0.8rem;
}

.row-btns {
  display: flex;
  gap: 0.15rem;
  justify-content: flex-end;
}

.row-status {
  font-size: 0.68rem;
  color: var(--muted);
}

.row-status.ok {
  color: #4ade80;
}

.row-status.err {
  color: #f87171;
}

.bulk-expand {
  margin: 0.35rem 0 0 2rem;
  font-size: 0.82rem;
}

.bulk-expand summary {
  cursor: pointer;
  color: var(--muted);
}

.expand-fields {
  margin-top: 0.5rem;
  display: grid;
  gap: 0.5rem;
  max-width: 36rem;
}

.row-err {
  margin: 0.25rem 0 0 2rem;
  font-size: 0.75rem;
  color: #f87171;
}

.val-list {
  margin: 0.5rem 0;
  padding-left: 1.1rem;
  font-size: 0.82rem;
}

.val-list--err {
  color: #f87171;
}

.val-list--warn {
  color: #fcd34d;
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

.submit-bar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}

.submit-bar > .btn {
  width: 100%;
}

.rows-summary {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
}

.url-from-campaign {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.advanced-queue {
  padding: 0.65rem 0.75rem;
  border: 1px dashed var(--border);
  border-radius: 8px;
  font-size: 0.85rem;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.check input {
  width: auto;
}

.expand-layout {
  display: grid;
  grid-template-columns: 1fr minmax(240px, 280px);
  gap: 1rem;
  align-items: start;
}

@media (max-width: 900px) {
  .expand-layout {
    grid-template-columns: 1fr;
  }
}

:deep(.preview-compact .tg-preview) {
  position: static;
}

:deep(.preview-compact .tg-phone) {
  min-height: 320px;
  max-width: 280px;
  margin: 0 auto;
}

:deep(.preview-compact .tg-preview-title),
:deep(.preview-compact .tg-map) {
  display: none;
}
</style>
