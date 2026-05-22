<template>
  <div class="bulk-create">
    <header class="page-header">
      <RouterLink :to="{ name: 'campaign-workspace', params: { id: campaignId }, query: { tab: 'create' } }" class="back">
        ← Создание ботов
      </RouterLink>
      <h1>Массовое создание</h1>
      <p class="subtitle">
        Добавьте строки: для каждого бота — аккаунт и своя ключевая фраза. Сгенерируйте тексты, при необходимости
        отредактируйте и создайте ботов в Telegram.
      </p>
    </header>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>

    <section v-else class="card block">
      <div class="form-group">
        <label>Ссылка на сервис *</label>
        <input v-model="targetUrl" type="url" placeholder="https://example.com" />
        <p class="field-hint">Одна ссылка для всех ботов в этой партии.</p>
      </div>

      <BotLinkModeField v-model="linkMode" :preview-url="linkPreview" />

      <div class="rows-head">
        <h3>Боты в партии</h3>
        <div class="rows-actions">
          <button type="button" class="btn btn-sm btn-ghost" @click="addRow">+ Строка</button>
          <button type="button" class="btn btn-sm btn-ghost" @click="addRows(5)">+5</button>
        </div>
      </div>

      <div class="rows-table">
        <div class="row-head row-grid">
          <span>#</span>
          <span>Аккаунт</span>
          <span>Ключевая фраза *</span>
          <span>Статус</span>
          <span></span>
        </div>
        <div v-for="(row, i) in rows" :key="row.id" class="row-grid row-item">
          <span class="row-num">{{ i + 1 }}</span>
          <select v-model.number="row.accountId" required>
            <option :value="null" disabled>Аккаунт</option>
            <option v-for="a in readyAccounts" :key="a.id" :value="a.id">
              {{ accountLabel(a) }}
            </option>
          </select>
          <input
            v-model="row.keyword"
            type="text"
            placeholder="например: vpn бот telegram"
            @keydown.enter.prevent
          />
          <span class="row-status" :class="statusClass(row)">{{ statusText(row) }}</span>
          <button type="button" class="btn btn-xs btn-ghost danger" :disabled="rows.length <= 1" @click="removeRow(i)">
            ×
          </button>
        </div>
      </div>

      <div class="action-bar">
        <button
          type="button"
          class="btn-ai"
          :disabled="!canGenerate || generating"
          @click="generateAll"
        >
          {{ generating ? `Генерация ${genProgress}…` : '✨ Сгенерировать тексты для всех' }}
        </button>
        <label class="check">
          <input v-model="autoStart" type="checkbox" />
          Запустить ботов после создания
        </label>
      </div>

      <div v-if="rows.some((r) => r.draft)" class="preview-block">
        <h3>Предпросмотр и правка</h3>
        <details v-for="(row, i) in rowsWithDraft" :key="row.id" class="preview-card" open>
          <summary>
            <strong>#{{ i + 1 }}</strong> «{{ row.keyword }}» — @{{ row.draft?.username || '…' }}
          </summary>
          <div class="preview-fields">
            <div class="form-group">
              <label>Имя</label>
              <input v-model="row.draft.display_name" />
            </div>
            <div class="form-group">
              <label>Username</label>
              <input v-model="row.draft.username" />
            </div>
            <div class="form-group">
              <label>Описание</label>
              <textarea v-model="row.draft.description" rows="3" />
            </div>
            <div class="form-group">
              <label>Приветствие</label>
              <textarea v-model="row.draft.welcome_message" rows="3" />
            </div>
          </div>
        </details>
      </div>

      <p v-if="submitError" class="error-text">{{ submitError }}</p>
      <div class="submit-bar">
        <button type="button" class="btn-ghost" :disabled="creating" @click="createViaJob">
          Быстро через очередь (без правки текстов)
        </button>
        <button type="button" class="btn" :disabled="!canCreate || creating" @click="createAll">
          {{ creating ? `Создание ${createProgress}…` : 'Создать ботов в Telegram' }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';

let rowSeq = 0;
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

const linkPreview = computed(() => {
  const first = rows.value.find((r) => r.draft?.public_link);
  return first?.draft?.public_link || targetUrl.value.trim() || '';
});

const canGenerate = computed(
  () =>
    targetUrl.value.trim() &&
    readyAccounts.value.length &&
    rows.value.some((r) => r.accountId && r.keyword.trim())
);

const rowsWithDraft = computed(() => rows.value.filter((r) => r.draft));

const canCreate = computed(() =>
  rowsWithDraft.value.length > 0 && rowsWithDraft.value.every((r) => r.draft?.username)
);

function accountLabel(a) {
  return a.label || a.phone || `#${a.id}`;
}

function statusText(row) {
  if (row.error) return 'Ошибка';
  if (row.draft) return 'Готово';
  if (row.keyword.trim()) return 'Черновик';
  return '—';
}

function statusClass(row) {
  if (row.error) return 'err';
  if (row.draft) return 'ok';
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

async function generateAll() {
  generating.value = true;
  submitError.value = null;
  const valid = rows.value.filter((r) => r.accountId && r.keyword.trim());
  let done = 0;
  for (const row of valid) {
    done += 1;
    genProgress.value = `${done}/${valid.length}`;
    row.error = null;
    try {
      const draft = await botService.generateDraft({
        campaignId: campaignId.value,
        accountId: row.accountId,
        targetUrl: targetUrl.value.trim(),
        keyword: row.keyword.trim(),
        linkMode: linkMode.value,
      });
      row.draft = {
        display_name: draft.display_name,
        username: (draft.username || '').replace(/^@/, ''),
        description: draft.description || '',
        about_text: draft.about_text || '',
        welcome_message: draft.welcome_message || '',
        welcome_button_enabled: draft.welcome_button_enabled !== false,
        welcome_button_text: draft.welcome_button_text || 'Перейти по ссылке',
        redirect_slug: draft.redirect_slug,
        public_link: draft.public_link,
      };
    } catch (e) {
      row.error = e.response?.data?.error || 'Ошибка генерации';
      row.draft = null;
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
    target_url: targetUrl.value.trim(),
    display_name: d.display_name,
    username: d.username.replace(/^@/, ''),
    description: d.description,
    about_text: d.about_text,
    welcome_message: d.welcome_message,
    welcome_button_enabled: d.welcome_button_enabled,
    welcome_button_text: d.welcome_button_text,
    keyword: row.keyword.trim(),
    redirect_slug: d.redirect_slug,
    link_mode: linkMode.value,
    create_via_botfather: true,
    auto_start: autoStart.value,
    generate_avatar: true,
  };
}

async function createAll() {
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
    submitError.value = 'Заполните хотя бы одну строку с аккаунтом и фразой';
    return;
  }
  if (!targetUrl.value.trim()) {
    submitError.value = 'Укажите ссылку на сервис';
    return;
  }
  try {
    await campaignService.update(campaignId.value, { resource_url: targetUrl.value.trim() });
    await taskStore.run('START_CAMPAIGN', () =>
      campaignService.startPlanned(campaignId.value, plans)
    );
    router.push({
      name: 'campaign-workspace',
      params: { id: campaignId.value },
      query: { tab: 'list' },
    });
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Не удалось запустить';
  }
}

onMounted(async () => {
  try {
    const data = await campaignService.get(campaignId.value);
    campaign.value = data.campaign;
    targetUrl.value = data.campaign.resource_url || '';
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
  max-width: 920px;
}

.page-header {
  margin-bottom: 1.25rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  max-width: 40rem;
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

.rows-actions {
  display: flex;
  gap: 0.35rem;
}

.row-grid {
  display: grid;
  grid-template-columns: 2rem 1fr 1.4fr 5rem 2rem;
  gap: 0.5rem;
  align-items: center;
}

.row-head {
  font-size: 0.72rem;
  color: var(--muted);
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border);
}

.row-item {
  padding: 0.45rem 0;
  border-bottom: 1px solid rgba(45, 58, 77, 0.5);
}

.row-num {
  color: var(--muted);
  font-size: 0.8rem;
}

.row-status {
  font-size: 0.72rem;
  color: var(--muted);
}

.row-status.ok {
  color: #4ade80;
}

.row-status.err {
  color: #f87171;
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
  margin-top: 1rem;
}

.preview-block {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.preview-block h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.preview-card {
  margin-bottom: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
}

.preview-card summary {
  cursor: pointer;
  font-size: 0.85rem;
}

.preview-fields {
  margin-top: 0.75rem;
  display: grid;
  gap: 0.5rem;
}

.submit-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
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
</style>
