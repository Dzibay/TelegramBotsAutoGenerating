<template>
  <div class="bulk-create">
    <header class="page-header">
      <h1>Массовое создание</h1>
      <p class="subtitle">
        Ручной режим: общие тексты для всех ботов, затем список с аватаром, именем, username и ссылкой.
        Создание идёт в фоне на сервере — вкладку можно закрыть.
      </p>
    </header>

    <div class="mode-tabs">
      <button
        type="button"
        class="mode-tab"
        :class="{ active: mode === 'manual' }"
        @click="mode = 'manual'"
      >
        Вручную
      </button>
      <button
        type="button"
        class="mode-tab"
        :class="{ active: mode === 'ai' }"
        @click="mode = 'ai'"
      >
        С нейросетью (AI)
      </button>
    </div>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>

    <!-- ─── РУЧНОЙ РЕЖИМ ─── -->
    <template v-else-if="mode === 'manual'">
      <div class="wizard-steps">
        <span :class="{ active: wizardStep >= 1, done: wizardStep > 1 }">1. Тексты и аккаунт</span>
        <span :class="{ active: wizardStep >= 2, done: wizardStep > 2 }">2. Список ботов</span>
        <span :class="{ active: wizardStep >= 3 }">3. Создание</span>
      </div>

      <!-- Шаг 1 -->
      <section v-show="wizardStep === 1" class="card block">
        <h3 class="block-title">Общие тексты для всех ботов</h3>
        <p class="field-hint block-hint">
          Эти тексты будут одинаковыми у каждого бота в партии. Ссылку можно задать общую или отдельную для каждого бота на следующем шаге.
        </p>

        <div class="form-group">
          <label>Аккаунт Telegram *</label>
          <select v-model.number="accountId" :disabled="!readyAccounts.length">
            <option :value="null" disabled>Выберите аккаунт</option>
            <option v-for="a in readyAccounts" :key="a.id" :value="a.id">
              {{ accountLabel(a) }} ({{ a.bots_created }}/{{ a.max_bots_limit }})
            </option>
          </select>
          <p v-if="selectedAccount" class="field-hint slots-hint">
            Свободно слотов: <strong>{{ freeSlots }}</strong> из {{ selectedAccount.max_bots_limit }}
          </p>
          <p v-else-if="!readyAccounts.length" class="error-text">
            Нет готовых аккаунтов с доступными слотами.
          </p>
        </div>

        <div
          v-if="campaignResourceUrl && !useCustomUrl"
          class="url-from-campaign card-inner"
        >
          <label>Ссылка на сервис по умолчанию</label>
          <p class="url-value">
            <a :href="campaignResourceUrl" target="_blank" rel="noopener noreferrer">{{ campaignResourceUrl }}</a>
          </p>
          <button type="button" class="link-btn" @click="useCustomUrl = true">Другая ссылка для партии</button>
        </div>
        <div v-else class="form-group">
          <label>Ссылка на сервис по умолчанию *</label>
          <input v-model="targetUrl" type="url" placeholder="https://example.com" />
          <p class="field-hint">Используется, если у бота не указана своя ссылка.</p>
          <button v-if="campaignResourceUrl" type="button" class="link-btn" @click="useCampaignUrl">
            ← Вернуть ссылку из кампании
          </button>
        </div>

        <BotLinkModeField v-model="linkMode" :preview-url="defaultLinkPreview" />

        <div class="form-group">
          <label>Описание в чате до Start (плакат) *</label>
          <textarea v-model="sharedTexts.description" rows="4" maxlength="512" placeholder="Текст до нажатия Start" />
        </div>

        <div class="form-group">
          <label>Сообщение после Start *</label>
          <textarea v-model="sharedTexts.welcome_message" rows="4" maxlength="2000" placeholder="Первое сообщение в чате" />
        </div>

        <details class="field-details">
          <summary>О боте в профиле (опционально, до 120 символов)</summary>
          <div class="form-group">
            <textarea v-model="sharedTexts.about_text" rows="2" maxlength="120" />
          </div>
        </details>

        <label class="check">
          <input v-model="sharedTexts.welcome_button_enabled" type="checkbox" />
          Кнопка «Перейти» в приветствии
        </label>
        <div v-if="sharedTexts.welcome_button_enabled" class="form-group">
          <label>Текст кнопки</label>
          <input v-model="sharedTexts.welcome_button_text" type="text" maxlength="64" />
        </div>

        <label class="check">
          <input v-model="autoStart" type="checkbox" />
          Запустить ботов после создания
        </label>

        <button type="button" class="btn btn-next" :disabled="!canGoStep2" @click="goToBotsStep">
          Далее: список ботов →
        </button>
      </section>

      <!-- Шаг 2 -->
      <section v-show="wizardStep === 2" class="card block">
        <div class="rows-head">
          <div>
            <h3 class="block-title">Боты в партии</h3>
            <p v-if="selectedAccount" class="rows-summary muted">
              Аккаунт: {{ accountLabel(selectedAccount) }} · свободно {{ freeSlots }} слот(ов) ·
              готово: {{ readyRowsCount }}
            </p>
          </div>
          <div class="rows-actions">
            <button type="button" class="btn btn-sm btn-ghost" :disabled="!canAddRow" @click="addRow">+ Строка</button>
            <button type="button" class="btn btn-sm btn-ghost" :disabled="!canAddRow" @click="addRows(5)">+5</button>
          </div>
        </div>

        <ul v-if="manualValidation.errors.length" class="val-list val-list--err">
          <li v-for="(msg, i) in manualValidation.errors" :key="'e' + i">{{ msg }}</li>
        </ul>
        <ul v-if="manualValidation.warnings.length" class="val-list val-list--warn">
          <li v-for="(msg, i) in manualValidation.warnings" :key="'w' + i">{{ msg }}</li>
        </ul>

        <div class="bulk-table-scroll">
          <div class="bulk-table manual-table">
            <div class="bulk-head manual-grid">
              <span>#</span>
              <span>Аватар</span>
              <span>Имя *</span>
              <span>Username *</span>
              <span>Ссылка</span>
              <span></span>
            </div>

            <div v-for="(row, i) in manualRows" :key="row.id" class="bulk-row">
              <div class="manual-grid bulk-main">
                <span class="row-num">{{ i + 1 }}</span>
                <BulkAvatarCell
                  @update:file="row.avatarFile = $event"
                  @update:preview="row.avatarPreview = $event"
                />
                <input v-model="row.displayName" type="text" placeholder="Имя бота" />
                <input
                  :value="row.username"
                  type="text"
                  placeholder="@username"
                  @input="row.username = $event.target.value.replace(/^@/, '')"
                />
                <input
                  v-model="row.targetUrl"
                  type="url"
                  :placeholder="effectiveTargetUrl || 'Своя ссылка'"
                />
                <button
                  type="button"
                  class="btn btn-xs btn-ghost danger"
                  :disabled="manualRows.length <= 1"
                  @click="removeManualRow(i)"
                >
                  ×
                </button>
              </div>
              <p v-if="row.error" class="row-err">{{ row.error }}</p>
            </div>
          </div>
        </div>

        <div class="wizard-nav">
          <button type="button" class="btn-ghost" @click="wizardStep = 1">← Назад</button>
          <button type="button" class="btn btn-next" :disabled="!canGoStep3" @click="goToCreateStep">
            Далее: создание →
          </button>
        </div>
      </section>

      <!-- Шаг 3 -->
      <section v-show="wizardStep === 3" class="card block">
        <h3 class="block-title">Создание ботов</h3>
        <p v-if="isJobActive" class="info-banner">
          Задача выполняется на сервере. Можно закрыть или обновить вкладку — прогресс сохранится.
          Вернитесь на эту страницу или откройте кампанию → журнал задачи.
        </p>
        <p v-else-if="!creationFinished" class="field-hint block-hint">
          После старта боты создаются в фоне с паузами между запросами к BotFather
          (~45 сек между ботами, ~3 мин каждые 5 ботов) — так снижается риск блокировки.
          При лимите Telegram сервер подождёт и продолжит автоматически.
        </p>

        <BulkCreationQueue
          :items="queueItems"
          :logs="creationLogs"
          :creating="isJobActive"
          :active="isJobActive || creationFinished"
          :current-username="currentCreatingUsername"
          :current-label="currentCreatingLabel"
          :flood-wait-remaining="floodWaitRemaining"
          :job-done="activeJob?.processed_accounts ?? 0"
          :job-total="activeJob?.total_accounts ?? 0"
          :job-created="activeJob?.total_bots_created ?? null"
          :job-message="activeJob?.progress_message ?? ''"
        />

        <p v-if="submitError" class="error-text">{{ submitError }}</p>
        <p v-if="creationSummary" class="summary-text">{{ creationSummary }}</p>

        <div class="wizard-nav">
          <button
            type="button"
            class="btn-ghost"
            :disabled="startingJob || cancellingJob"
            @click="wizardStep = 2"
          >
            ← К списку
          </button>
          <button
            v-if="isJobActive"
            type="button"
            class="btn-ghost danger"
            :disabled="cancellingJob"
            @click="cancelActiveJob"
          >
            {{ cancellingJob ? 'Останавливаем…' : 'Остановить' }}
          </button>
          <button
            v-if="!isJobActive && !creationFinished"
            type="button"
            class="btn"
            :disabled="!canCreateManual || startingJob"
            @click="startManualCreation"
          >
            {{ startingJob ? 'Запуск…' : 'Создать ботов в Telegram' }}
          </button>
          <template v-else-if="creationFinished && retryRowsCount > 0">
            <button
              type="button"
              class="btn-ghost"
              :disabled="startingJob || cancellingJob"
              @click="resetQueueRows"
            >
              Сбросить очередь
            </button>
            <button
              type="button"
              class="btn"
              :disabled="startingJob || cancellingJob || !canCreateManual"
              @click="resetAndRestartQueue"
            >
              {{ startingJob ? 'Запуск…' : `Перезапустить (${retryRowsCount})` }}
            </button>
          </template>
          <button
            v-else-if="creationFinished"
            type="button"
            class="btn"
            @click="goToCampaignList"
          >
            К списку ботов кампании
          </button>
        </div>
      </section>
    </template>

    <!-- ─── AI РЕЖИМ (прежняя логика) ─── -->
    <section v-else class="card block">
      <p class="field-hint block-hint">
        Таблица ботов: аккаунт, фраза для AI, имя и username. Фраза нужна только для генерации текстов нейросетью.
      </p>

      <div
        v-if="campaignResourceUrl && !useCustomUrl"
        class="url-from-campaign card-inner"
      >
        <label>Ссылка на сервис</label>
        <p class="url-value">
          <a :href="campaignResourceUrl" target="_blank" rel="noopener noreferrer">{{ campaignResourceUrl }}</a>
        </p>
        <button type="button" class="link-btn" @click="useCustomUrl = true">Другая ссылка для этой партии</button>
      </div>
      <div v-else class="form-group">
        <label>Ссылка на сервис *</label>
        <input v-model="targetUrl" type="url" placeholder="https://example.com" />
        <button v-if="campaignResourceUrl" type="button" class="link-btn" @click="useCampaignUrl">
          ← Вернуть ссылку из кампании
        </button>
      </div>

      <BotLinkModeField v-model="linkMode" :preview-url="aiLinkPreview" />

      <p v-if="rowsWithAccountCount" class="rows-summary muted">
        Строк с аккаунтом: {{ rowsWithAccountCount }} · готово: {{ rowsReadyCount }}
        <span v-if="rowsAiReadyCount"> · для AI: {{ rowsAiReadyCount }}</span>
      </p>

      <ul v-if="aiValidation.errors.length" class="val-list val-list--err">
        <li v-for="(msg, i) in aiValidation.errors" :key="'e' + i">{{ msg }}</li>
      </ul>
      <ul v-if="aiValidation.warnings.length" class="val-list val-list--warn">
        <li v-for="(msg, i) in aiValidation.warnings" :key="'w' + i">{{ msg }}</li>
      </ul>

      <div class="rows-head">
        <h3>Боты в партии</h3>
        <div class="rows-actions">
          <button type="button" class="btn btn-sm btn-ghost" @click="addAiRow">+ Строка</button>
          <button type="button" class="btn btn-sm btn-ghost" @click="addAiRows(5)">+5</button>
        </div>
      </div>

      <div class="bulk-table-scroll">
        <div class="bulk-table">
          <div class="bulk-head ai-grid">
            <span>#</span>
            <span>Аккаунт *</span>
            <span>Фраза (AI)</span>
            <span>Имя</span>
            <span>Username</span>
            <span>Статус</span>
            <span></span>
          </div>

          <div v-for="(row, i) in aiRows" :key="row.id" class="bulk-row">
            <div class="ai-grid bulk-main">
              <span class="row-num">{{ i + 1 }}</span>
              <select v-model.number="row.accountId">
                <option :value="null" disabled>Аккаунт</option>
                <option v-for="a in readyAccounts" :key="a.id" :value="a.id">
                  {{ accountLabel(a) }}
                </option>
              </select>
              <input v-model="row.keyword" type="text" placeholder="для AI" />
              <input
                :value="row.draft?.display_name ?? ''"
                type="text"
                placeholder="Имя"
                @input="onAiDraftField(row, 'display_name', $event.target.value)"
              />
              <input
                :value="row.draft?.username ?? ''"
                type="text"
                placeholder="@username"
                @input="onAiDraftField(row, 'username', $event.target.value)"
              />
              <span class="row-status" :class="aiStatusClass(row)">{{ aiStatusText(row) }}</span>
              <div class="row-btns">
                <button type="button" class="btn btn-xs btn-ghost" title="Заполнить вручную" @click="ensureAiDraft(row)">✎</button>
                <button
                  type="button"
                  class="btn btn-xs btn-ghost"
                  :disabled="!row.accountId || !row.keyword.trim() || generating"
                  title="Сгенерировать по фразе"
                  @click="generateOne(row)"
                >
                  AI
                </button>
                <button
                  type="button"
                  class="btn btn-xs btn-ghost danger"
                  :disabled="aiRows.length <= 1"
                  @click="removeAiRow(i)"
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
                  :public-link="row.draft.public_link || aiLinkPreview"
                />
              </div>
            </details>
            <p v-if="row.error" class="row-err">{{ row.error }}</p>
          </div>
        </div>
      </div>

      <div class="action-bar">
        <button
          type="button"
          class="btn-ai"
          :disabled="!canGenerate || generating || aiValidation.errors.length"
          @click="generateAll"
        >
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
          :disabled="!canCreateAi || creating || aiValidation.errors.length"
          @click="createAllAi"
        >
          {{ creating ? `Создание ${createProgress}…` : 'Создать ботов в Telegram' }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BulkAvatarCell from '../components/BulkAvatarCell.vue';
import BulkCreationQueue from '../components/BulkCreationQueue.vue';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotTelegramPreview from '../components/BotTelegramPreview.vue';
import { botService } from '../services/botService';
import { campaignService, jobService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { applyCampaignTextDefaults, campaignTextDefaultsSnapshot } from '../utils/campaignTextDefaults';
import {
  rowTargetUrl,
  validateBulkBatch,
  validateManualBulkBatch,
} from '../utils/bulkBatchValidate';
const JOB_SNAPSHOT_KEY = (id) => `bulk_manual_job_${id}`;

let rowSeq = 0;

function newManualRow() {
  return {
    id: ++rowSeq,
    displayName: '',
    username: '',
    targetUrl: '',
    avatarFile: null,
    avatarPreview: null,
    queueStatus: 'pending',
    error: null,
    createdBotId: null,
  };
}

function emptyAiDraft() {
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

function newAiRow() {
  return { id: ++rowSeq, accountId: null, keyword: '', draft: null, error: null };
}

const route = useRoute();
const router = useRouter();
const taskStore = useAsyncTaskStore();
const campaignId = computed(() => Number(route.params.id));

const mode = ref('manual');
const wizardStep = ref(1);
const loadError = ref(null);
const campaign = ref({});
const accounts = ref([]);
const campaignResourceUrl = ref('');
const useCustomUrl = ref(false);
const targetUrl = ref('');
const linkMode = ref('redirect');
const accountId = ref(null);
const autoStart = ref(true);

const sharedTexts = ref({
  description: '',
  about_text: '',
  welcome_message: '',
  welcome_button_enabled: true,
  welcome_button_text: 'Перейти по ссылке',
});

const manualRows = ref([newManualRow(), newManualRow(), newManualRow()]);
const aiRows = ref([newAiRow(), newAiRow(), newAiRow()]);

const generating = ref(false);
const genProgress = ref('');
const creating = ref(false);
const createProgress = ref('');
const submitError = ref(null);
const creationLogs = ref([]);
const creationFinished = ref(false);
const creationSummary = ref('');
const currentCreatingUsername = ref('');
const currentCreatingLabel = ref('');
const floodWaitRemaining = ref(0);
const activeJob = ref(null);
const startingJob = ref(false);
const cancellingJob = ref(false);
const lastLogId = ref(0);
let pollTimer = null;

const isJobActive = computed(
  () => activeJob.value && ['queued', 'running'].includes(activeJob.value.status)
);

const readyAccounts = computed(() =>
  accounts.value.filter((a) => a.status === 'ready' && a.can_create_bots !== false)
);

const selectedAccount = computed(() =>
  readyAccounts.value.find((a) => a.id === accountId.value) ?? null
);

const freeSlots = computed(() => {
  if (!selectedAccount.value) return 0;
  return Math.max(0, selectedAccount.value.max_bots_limit - selectedAccount.value.bots_created);
});

const effectiveTargetUrl = computed(() => {
  if (campaignResourceUrl.value && !useCustomUrl.value) return campaignResourceUrl.value;
  return targetUrl.value;
});

const defaultLinkPreview = computed(() => {
  if (linkMode.value === 'direct' && effectiveTargetUrl.value.trim()) {
    return effectiveTargetUrl.value.trim();
  }
  return '';
});

const manualValidation = computed(() =>
  validateManualBulkBatch(
    manualRows.value,
    selectedAccount.value,
    sharedTexts.value,
    effectiveTargetUrl.value
  )
);

const readyRowsCount = computed(
  () => manualRows.value.filter((r) => r.displayName?.trim() && r.username?.trim()).length
);

const canGoStep2 = computed(
  () =>
    accountId.value &&
    selectedAccount.value &&
    sharedTexts.value.description?.trim() &&
    sharedTexts.value.welcome_message?.trim() &&
    (effectiveTargetUrl.value.trim() || campaignResourceUrl.value)
);

const canGoStep3 = computed(
  () => readyRowsCount.value > 0 && !manualValidation.value.errors.length
);

const canAddRow = computed(() => freeSlots.value > 0 && manualRows.value.length < freeSlots.value);

const canCreateManual = computed(
  () =>
    readyRowsCount.value > 0 &&
    retryRowsCount.value > 0 &&
    !manualValidation.value.errors.length &&
    !isJobActive.value &&
    !startingJob.value
);

const retryRowsCount = computed(
  () =>
    manualRows.value.filter(
      (r) => r.displayName?.trim() && r.username?.trim() && r.queueStatus !== 'done'
    ).length
);

const queueItems = computed(() =>
  manualRows.value
    .filter((r) => r.displayName?.trim() && r.username?.trim())
    .map((r) => ({
      id: r.id,
      displayName: r.displayName,
      username: r.username,
      queueStatus: r.queueStatus,
    }))
);

const aiValidation = computed(() => validateBulkBatch(aiRows.value, readyAccounts.value));

const rowsWithAccountCount = computed(() => aiRows.value.filter((r) => r.accountId).length);
const rowsWithDraft = computed(() =>
  aiRows.value.filter((r) => r.draft?.display_name?.trim() && r.draft?.username?.trim())
);
const rowsReadyCount = computed(() => rowsWithDraft.value.length);
const rowsAiReadyCount = computed(
  () => aiRows.value.filter((r) => r.accountId && r.keyword.trim()).length
);

const aiLinkPreview = computed(() => {
  const first = aiRows.value.find((r) => r.draft?.public_link);
  return first?.draft?.public_link || effectiveTargetUrl.value.trim() || '';
});

const canGenerate = computed(
  () =>
    effectiveTargetUrl.value.trim() &&
    readyAccounts.value.length &&
    rowsAiReadyCount.value > 0 &&
    !aiValidation.value.errors.length
);

const canCreateAi = computed(
  () => rowsReadyCount.value > 0 && !aiValidation.value.errors.length
);

function accountLabel(a) {
  return a.label || a.phone || `#${a.id}`;
}

function useCampaignUrl() {
  useCustomUrl.value = false;
  targetUrl.value = campaignResourceUrl.value;
}

function formatLogTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function mapApiLog(entry) {
  return {
    id: entry.id,
    time: formatLogTime(entry.created_at),
    created_at: entry.created_at,
    message: entry.message,
    level: entry.level === 'error' ? 'error' : entry.level === 'warn' ? 'warn' : entry.level || 'info',
    context: entry.context,
    source: 'server',
  };
}

function applyLogContext(entry) {
  const ctx = entry.context;
  if (!ctx) return;
  if (ctx.username) {
    currentCreatingUsername.value = String(ctx.username).replace(/^@/, '');
  }
  if (ctx.status === 'waiting' && ctx.wait_seconds) {
    floodWaitRemaining.value = Number(ctx.wait_seconds);
  } else if (ctx.status === 'creating' || ctx.status === 'done' || ctx.status === 'error') {
    floodWaitRemaining.value = 0;
  }
  if (ctx.row_id != null) {
    const row = manualRows.value.find((r) => r.id === ctx.row_id);
    if (row && ctx.status) row.queueStatus = ctx.status;
    if (row && ctx.error) row.error = ctx.error;
  }
  if (ctx.status === 'creating' && ctx.username) {
    currentCreatingLabel.value = `@${ctx.username.replace(/^@/, '')}`;
  }
}

function saveJobSnapshot(jobId) {
  const rows = manualRows.value
    .filter((r) => r.displayName?.trim() && r.username?.trim())
    .map((r) => ({
      id: r.id,
      displayName: r.displayName,
      username: r.username,
      targetUrl: r.targetUrl || '',
      queueStatus: r.queueStatus || 'pending',
      error: r.error || null,
    }));
  sessionStorage.setItem(
    JOB_SNAPSHOT_KEY(campaignId.value),
    JSON.stringify({ jobId, accountId: accountId.value, rows })
  );
}

function loadJobSnapshot() {
  try {
    const raw = sessionStorage.getItem(JOB_SNAPSHOT_KEY(campaignId.value));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function restoreRowsFromSnapshot(snap) {
  if (!snap?.rows?.length) return;
  const maxId = Math.max(...snap.rows.map((s) => s.id || 0), 0);
  rowSeq = Math.max(rowSeq, maxId);
  manualRows.value = snap.rows.map((s) => ({
    id: s.id,
    displayName: s.displayName || '',
    username: s.username || '',
    targetUrl: s.targetUrl || '',
    avatarFile: null,
    avatarPreview: null,
    queueStatus: s.queueStatus || 'pending',
    error: s.error || null,
    createdBotId: null,
  }));
  if (snap.accountId) accountId.value = snap.accountId;
}

function clearJobSnapshot() {
  sessionStorage.removeItem(JOB_SNAPSHOT_KEY(campaignId.value));
}

async function fetchJobLogs() {
  if (!activeJob.value?.id) return;
  const batch = await jobService.getLogs(activeJob.value.id, lastLogId.value);
  if (!batch.length) return;
  for (const entry of batch) {
    applyLogContext(entry);
    creationLogs.value.push(mapApiLog(entry));
  }
  lastLogId.value = batch[batch.length - 1].id;
}

async function refreshActiveJob() {
  if (!activeJob.value?.id) return;
  activeJob.value = await jobService.get(activeJob.value.id);
  if (['completed', 'failed', 'cancelled'].includes(activeJob.value.status)) {
    stopJobPolling();
    creationFinished.value = true;
    const created = activeJob.value.total_bots_created ?? 0;
    if (activeJob.value.status === 'cancelled') {
      creationSummary.value =
        activeJob.value.progress_message || `Остановлено. Создано: ${created}.`;
    } else {
      creationSummary.value = activeJob.value.progress_message || `Готово: создано ${created}.`;
    }
    if (activeJob.value.status === 'failed' && created === 0) {
      submitError.value = activeJob.value.error_message || 'Задача завершилась с ошибкой';
    }
    clearJobSnapshot();
    try {
      accounts.value = await campaignService.getAccounts(campaignId.value);
    } catch {
      /* ignore */
    }
  }
}

async function pollJob() {
  await refreshActiveJob();
  await fetchJobLogs();
}

function startJobPolling() {
  stopJobPolling();
  pollTimer = setInterval(pollJob, 2000);
}

function stopJobPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function tryResumeActiveJob() {
  const data = await campaignService.get(campaignId.value);
  const job = data.activeJob;
  if (!job || !['queued', 'running'].includes(job.status)) return;

  const snap = loadJobSnapshot();
  if (snap?.jobId === job.id) {
    restoreRowsFromSnapshot(snap);
  }

  activeJob.value = job;
  wizardStep.value = 3;
  creationFinished.value = false;
  lastLogId.value = 0;
  creationLogs.value = [];
  await fetchJobLogs();
  startJobPolling();
}

function goToBotsStep() {
  if (campaign.value) {
    if (!sharedTexts.value.description?.trim()) {
      sharedTexts.value.description = campaign.value.default_description || '';
    }
    if (!sharedTexts.value.welcome_message?.trim()) {
      sharedTexts.value.welcome_message = campaign.value.default_welcome_message || '';
    }
    if (!sharedTexts.value.about_text?.trim()) {
      sharedTexts.value.about_text = campaign.value.default_about_text || '';
    }
  }
  wizardStep.value = 2;
}

function goToCreateStep() {
  manualRows.value.forEach((r) => {
    if (r.displayName?.trim() && r.username?.trim()) {
      r.queueStatus = 'pending';
      r.error = null;
    }
  });
  creationFinished.value = false;
  creationSummary.value = '';
  creationLogs.value = [];
  wizardStep.value = 3;
}

function addRow() {
  if (manualRows.value.length >= freeSlots.value && freeSlots.value > 0) return;
  manualRows.value.push(newManualRow());
}

function addRows(n) {
  for (let i = 0; i < n; i++) addRow();
}

function removeManualRow(i) {
  manualRows.value.splice(i, 1);
}

function resetQueueRows() {
  manualRows.value.forEach((r) => {
    if (!r.displayName?.trim() || !r.username?.trim()) return;
    if (r.queueStatus !== 'done') {
      r.queueStatus = 'pending';
      r.error = null;
    }
  });
  creationFinished.value = false;
  creationSummary.value = '';
  creationLogs.value = [];
  submitError.value = null;
  activeJob.value = null;
  lastLogId.value = 0;
  currentCreatingUsername.value = '';
  currentCreatingLabel.value = '';
  floodWaitRemaining.value = 0;
  clearJobSnapshot();
  stopJobPolling();
}

async function cancelActiveJob() {
  if (!activeJob.value?.id || !isJobActive.value) return;
  cancellingJob.value = true;
  submitError.value = null;
  try {
    activeJob.value = await jobService.cancel(activeJob.value.id);
    await pollJob();
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Не удалось остановить задачу';
  } finally {
    cancellingJob.value = false;
  }
}

async function resetAndRestartQueue() {
  if (isJobActive.value) {
    await cancelActiveJob();
    if (isJobActive.value) return;
  }
  resetQueueRows();
  wizardStep.value = 3;
  await startManualCreation();
}

async function startManualCreation() {
  if (!canCreateManual.value) return;

  const rowsToCreate = manualRows.value.filter(
    (r) =>
      r.displayName?.trim() &&
      r.username?.trim() &&
      r.queueStatus !== 'done'
  );
  if (!rowsToCreate.length) return;

  startingJob.value = true;
  submitError.value = null;
  creationFinished.value = false;
  creationSummary.value = '';
  creationLogs.value = [];
  lastLogId.value = 0;
  floodWaitRemaining.value = 0;

  rowsToCreate.forEach((r) => {
    r.queueStatus = 'pending';
    r.error = null;
  });

  const form = new FormData();
  form.append(
    'data',
    JSON.stringify({
      telegram_account_id: accountId.value,
      default_target_url: effectiveTargetUrl.value.trim(),
      link_mode: linkMode.value,
      auto_start: autoStart.value,
      shared_texts: sharedTexts.value,
      bots: rowsToCreate.map((r) => ({
        row_id: r.id,
        display_name: r.displayName.trim(),
        username: r.username.replace(/^@/, '').trim(),
        target_url: r.targetUrl?.trim() || null,
      })),
    })
  );
  for (const row of rowsToCreate) {
    if (row.avatarFile) {
      form.append(`avatar_${row.id}`, row.avatarFile);
    }
  }

  try {
    const job = await campaignService.startManualBulk(campaignId.value, form);
    activeJob.value = job;
    saveJobSnapshot(job.id);
    startJobPolling();
    await pollJob();
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Не удалось запустить задачу';
  } finally {
    startingJob.value = false;
  }
}

function goToCampaignList() {
  router.push({
    name: 'campaign-workspace',
    params: { id: campaignId.value },
    query: { tab: 'list' },
  });
}

/* ─── AI mode helpers ─── */

function ensureAiDraft(row) {
  if (!row.draft) row.draft = emptyAiDraft();
  else applyCampaignTextDefaults(row.draft, campaign.value);
}

function onAiDraftField(row, field, value) {
  ensureAiDraft(row);
  row.draft[field] = value;
}

function aiStatusText(row) {
  if (row.error) return 'Ошибка';
  if (row.draft?.display_name?.trim() && row.draft?.username?.trim()) return 'Готово';
  if (row.draft) return 'Черновик';
  if (row.keyword.trim()) return 'Ждёт AI';
  return '—';
}

function aiStatusClass(row) {
  if (row.error) return 'err';
  if (row.draft?.display_name?.trim() && row.draft?.username?.trim()) return 'ok';
  return '';
}

function addAiRow() {
  aiRows.value.push(newAiRow());
}

function addAiRows(n) {
  for (let i = 0; i < n; i++) addAiRow();
}

function removeAiRow(i) {
  aiRows.value.splice(i, 1);
}

function applyDraftFromApi(row, draft) {
  ensureAiDraft(row);
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
  if (!row.keyword.trim() || !row.accountId) return;
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
  const valid = aiRows.value.filter((r) => r.accountId && r.keyword.trim());
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

function buildAiCreateSpec(row) {
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

async function createAllAi() {
  if (!canCreateAi.value) return;
  creating.value = true;
  submitError.value = null;
  const specs = rowsWithDraft.value.map(buildAiCreateSpec);
  let done = 0;
  try {
    for (const row of rowsWithDraft.value) {
      done += 1;
      createProgress.value = `${done}/${rowsWithDraft.value.length}`;
      const spec = buildAiCreateSpec(row);
      try {
        await taskStore.run(
          'CREATE_BOT',
          async ({ logStep }) => {
            logStep(`[${done}/${rowsWithDraft.value.length}] @${spec.username}`, 'info');
            try {
              const b = await botService.create(spec);
              logStep(`@${spec.username} OK`, 'success', { id: b.id });
              return b;
            } catch (e) {
              logStep(`@${spec.username}: ${e.response?.data?.error || e.message}`, 'error');
              throw e;
            }
          },
          { username: spec.username }
        );
      } catch (e) {
        row.error = e.response?.data?.error || 'Ошибка';
      }
    }
    router.push({
      name: 'campaign-workspace',
      params: { id: campaignId.value },
      query: { tab: 'list' },
    });
  } catch (e) {
    submitError.value = e.response?.data?.error || 'Ошибка создания';
  } finally {
    creating.value = false;
    createProgress.value = '';
  }
}

watch([manualRows, sharedTexts, accountId], () => {
  if (wizardStep.value < 3) submitError.value = null;
}, { deep: true });

watch(
  () => campaign.value,
  (c) => {
    if (!c) return;
    if (!sharedTexts.value.description?.trim()) {
      sharedTexts.value.description = c.default_description || '';
    }
    if (!sharedTexts.value.welcome_message?.trim()) {
      sharedTexts.value.welcome_message = c.default_welcome_message || '';
    }
    if (!sharedTexts.value.about_text?.trim()) {
      sharedTexts.value.about_text = c.default_about_text || '';
    }
    aiRows.value.forEach((row) => {
      if (row.draft) applyCampaignTextDefaults(row.draft, c);
    });
  }
);

watch(freeSlots, (slots) => {
  while (manualRows.value.length > slots && slots > 0) {
    manualRows.value.pop();
  }
});

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
    sharedTexts.value.description = data.campaign.default_description || '';
    sharedTexts.value.welcome_message = data.campaign.default_welcome_message || '';
    sharedTexts.value.about_text = data.campaign.default_about_text || '';

    accounts.value = await campaignService.getAccounts(campaignId.value);
    const first = readyAccounts.value[0];
    if (first) accountId.value = first.id;

    await tryResumeActiveJob();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  }
});

onUnmounted(() => {
  stopJobPolling();
});
</script>

<style scoped>
.bulk-create {
  max-width: 1100px;
}

.page-header {
  margin-bottom: 1rem;
}

.subtitle {
  margin: 0.35rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  max-width: 44rem;
}

.mode-tabs {
  display: flex;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.mode-tab {
  padding: 0.45rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.85rem;
}

.mode-tab.active {
  border-color: var(--accent);
  color: var(--text);
  background: rgba(59, 130, 246, 0.12);
}

.wizard-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.wizard-steps span {
  flex: 1;
  min-width: 6rem;
  text-align: center;
  padding: 0.4rem 0.5rem;
  font-size: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  color: var(--muted);
}

.wizard-steps span.active {
  border-color: var(--accent);
  color: var(--text);
  background: rgba(59, 130, 246, 0.1);
}

.wizard-steps span.done {
  color: #86efac;
  border-color: rgba(34, 197, 94, 0.35);
}

.block {
  padding: 1.25rem;
}

.block-title {
  margin: 0 0 0.35rem;
  font-size: 1rem;
}

.block-hint {
  margin: 0 0 1rem;
}

.slots-hint strong {
  color: #4ade80;
}

.field-details {
  margin: 0.75rem 0;
  font-size: 0.88rem;
}

.field-details summary {
  cursor: pointer;
  color: var(--muted);
}

.btn-ghost.danger {
  color: #f87171;
  border-color: rgba(248, 113, 113, 0.35);
}

.btn-ghost.danger:hover:not(:disabled) {
  background: rgba(248, 113, 113, 0.12);
}

.wizard-nav {
  display: flex;
  gap: 0.5rem;
  margin-top: 1.25rem;
}

.wizard-nav .btn-next,
.btn-next {
  flex: 1;
}

.rows-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.rows-head h3 {
  margin: 0;
  font-size: 0.95rem;
}

.manual-grid {
  display: grid;
  grid-template-columns: 2rem 3rem 1.2fr 1.1fr 1.3fr 2rem;
  gap: 0.4rem;
  align-items: center;
}

.ai-grid {
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
  margin-top: 1rem;
}

.submit-bar > .btn {
  width: 100%;
}

.rows-summary {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
}

.summary-text {
  margin: 0.75rem 0 0;
  font-size: 0.9rem;
  color: #86efac;
}

.info-banner {
  margin: 0 0 1rem;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border: 1px solid rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.1);
  font-size: 0.85rem;
  color: #93c5fd;
  line-height: 1.45;
}

.url-from-campaign {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.url-value {
  margin: 0.35rem 0;
  font-size: 0.85rem;
  word-break: break-all;
}

.url-value a {
  color: var(--accent);
}

.check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  cursor: pointer;
  margin: 0.5rem 0;
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
