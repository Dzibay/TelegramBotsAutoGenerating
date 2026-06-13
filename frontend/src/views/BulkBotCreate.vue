<template>
  <div class="bulk-create">
    <header class="page-header">
      <h1>Массовое создание</h1>
      <p class="subtitle">
        Ручной режим: общие тексты для всех ботов, затем список с аватаром, именем, username и ссылкой.
        Создание идёт в фоне на сервере — вкладку можно закрыть.
      </p>
    </header>

    <CampaignActiveJobsPanel
      v-if="campaignId"
      ref="activeJobsPanelRef"
      :campaign-id="campaignId"
      :history-link="{ name: 'campaign-job-history', params: { id: campaignId } }"
      @update:jobs="onActiveJobsUpdate"
    />

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
      <WizardSteps
        :steps="manualWizardSteps"
        :current="wizardStep"
        :clickable="!isSelectedAccountBusy && !creationFinished"
        @go="wizardStep = $event"
      />

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
          <p v-else-if="isSelectedAccountBusy && !isJobActive" class="info-banner">
            На этом аккаунте уже выполняется задача. Выберите другой аккаунт или дождитесь завершения.
          </p>
        </div>

        <BulkLinkSourceField
          v-model:link-source="linkSource"
          v-model:batch-url="targetUrl"
          v-model:track-clicks="trackClicks"
          :uses-referral-api="usesReferralApi"
          :campaign-resource-url="campaignResourceUrl"
          :link-preview="linkPreviewUrl"
        />

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

        <details class="paste-block">
          <summary>Вставить список (имя, username)</summary>
          <p class="field-hint block-hint">
            Одна строка — один бот. Формат: <code>имя,username</code> или <code>имя, username</code>
            (пробел после запятой необязателен). Пустые строки и <code>#</code> игнорируются.
          </p>
          <textarea
            v-model="pasteText"
            class="paste-input"
            rows="5"
            placeholder="VPN Bot, vpn_free_bot&#10;Music Bot, music_helper_bot"
          />
          <div class="paste-actions">
            <button
              type="button"
              class="btn btn-sm"
              :disabled="!pasteText.trim()"
              @click="applyPasteList"
            >
              Заполнить таблицу
            </button>
            <button
              type="button"
              class="btn btn-sm btn-ghost"
              :disabled="!pasteText.trim()"
              @click="clearPaste"
            >
              Очистить
            </button>
          </div>
          <p v-if="pasteMessage" class="paste-msg ok">{{ pasteMessage }}</p>
          <ul v-if="pasteErrors.length" class="val-list val-list--warn paste-errors">
            <li v-for="(msg, i) in pasteErrors" :key="'p' + i">{{ msg }}</li>
          </ul>
        </details>

        <p class="field-hint avatar-hint">
          Загрузите аватарку в колонке слева и потяните нижний край — одна картинка применится на несколько ботов в группе.
        </p>

        <div class="bulk-table-scroll">
          <div class="bulk-table manual-table">
            <div class="manual-table-header">
              <span class="manual-head-avatar">Аватар</span>
              <div class="bulk-head manual-grid-no-avatar manual-head-cols">
                <span>#</span>
                <span>Имя *</span>
                <span>Username *</span>
                <span>{{ linkSource === 'per_bot' ? 'Ссылка *' : 'Ссылка' }}</span>
                <span></span>
              </div>
            </div>

            <div
              v-for="group in avatarAnchorGroups"
              :key="`g-${group.row.id}`"
              class="manual-group"
            >
              <div class="manual-group-avatar">
                <BulkAvatarStretchCell
                  :preview-url="group.row.avatarPreview"
                  :span="group.span"
                  :max-span="manualRows.length - group.index"
                  @update:file="onAnchorAvatarFile(group.index, $event)"
                  @update:preview="onAnchorAvatarPreview(group.index, $event)"
                  @update:span="setAnchorSpan(group.index, $event)"
                />
              </div>
              <div class="manual-group-rows">
                <div
                  v-for="(row, j) in manualRows.slice(group.index, group.index + group.span)"
                  :key="row.id"
                  class="bulk-row"
                >
                  <div class="manual-grid-no-avatar bulk-main">
                    <span class="row-num">{{ group.index + j + 1 }}</span>
                    <input v-model="row.displayName" type="text" placeholder="Имя бота" />
                    <input
                      :value="row.username"
                      type="text"
                      placeholder="@username"
                      @input="row.username = $event.target.value.replace(/^@/, '')"
                    />
                    <input
                      v-if="linkSource === 'per_bot'"
                      v-model="row.targetUrl"
                      type="url"
                      placeholder="https://..."
                    />
                    <span v-else-if="linkSource === 'referral'" class="muted link-api-hint">через API</span>
                    <span v-else class="muted link-api-hint">{{ sharedBatchUrl || 'общая' }}</span>
                    <button
                      type="button"
                      class="btn btn-xs btn-ghost danger"
                      :disabled="manualRows.length <= 1"
                      @click="removeManualRow(group.index + j)"
                    >
                      ×
                    </button>
                  </div>
                  <p v-if="row.error" class="row-err row-err--inline">{{ row.error }}</p>
                </div>
              </div>
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
          ({{ pacingSummary }}) — так снижается риск блокировки.
          Оценка времени для {{ pendingBotCount }} бот(ов): <strong>{{ creationEta }}</strong>.
          <RouterLink :to="{ name: 'settings' }" class="inline-link">Изменить интервалы</RouterLink>.
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

      <section class="card block history-link-block">
        <RouterLink
          :to="{ name: 'campaign-job-history', params: { id: campaignId } }"
          class="history-page-link"
        >
          История задач кампании →
        </RouterLink>
      </section>
    </template>

    <!-- ─── AI РЕЖИМ (прежняя логика) ─── -->
    <section v-else class="card block">
      <p class="field-hint block-hint">
        Таблица ботов: аккаунт, фраза для AI, имя и username. Фраза нужна только для генерации текстов нейросетью.
      </p>

      <BulkLinkSourceField
        v-model:link-source="linkSource"
        v-model:batch-url="targetUrl"
        v-model:track-clicks="trackClicks"
        :uses-referral-api="usesReferralApi"
        :campaign-resource-url="campaignResourceUrl"
        :show-per-bot-option="false"
        :link-preview="linkPreviewUrl"
      />

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
import { RouterLink, useRoute, useRouter } from 'vue-router';
import CampaignActiveJobsPanel from '../components/CampaignActiveJobsPanel.vue';
import BulkAvatarStretchCell from '../components/BulkAvatarStretchCell.vue';
import BulkCreationQueue from '../components/BulkCreationQueue.vue';
import BulkLinkSourceField from '../components/BulkLinkSourceField.vue';
import BotTelegramPreview from '../components/BotTelegramPreview.vue';
import JobLogPanel from '../components/JobLogPanel.vue';
import WizardSteps from '../components/WizardSteps.vue';
import { botService } from '../services/botService';
import { campaignService, jobService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { useSettingsStore } from '../stores/settingsStore';
import { useUiPrefsStore } from '../stores/uiPrefsStore';
import { applyCampaignTextDefaults, applyCampaignButtonDefaults, campaignTextDefaultsSnapshot } from '../utils/campaignTextDefaults';
import { accountDisplayLabel } from '../utils/accountLabel';
import {
  estimateBulkCreationSec,
  formatDurationSec,
  formatPacingSummary,
} from '../utils/estimateJobTime';
import { mapApiLog } from '../utils/formatLogEntry';
import {
  effectiveLinkMode,
  isLinkStepValid,
  pickDefaultLinkSource,
  sharedLinkUrl,
  usesReferralLinks as isReferralLinkSource,
  LINK_SOURCE,
} from '../utils/bulkLinkSource';
import {
  getAvatarAnchorGroups,
  normalizeAvatarSpans,
  resolveRowAvatar,
  findAnchorForRowIndex,
} from '../utils/bulkBotAvatars';
import { parseBulkBotPaste } from '../utils/bulkBotPasteParse';
import {
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
    avatarSpan: 1,
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
const settingsStore = useSettingsStore();
const uiPrefs = useUiPrefsStore();

const manualWizardSteps = [
  { id: 'texts', label: 'Тексты и аккаунт' },
  { id: 'list', label: 'Список ботов' },
  { id: 'create', label: 'Создание' },
];
const campaignId = computed(() => Number(route.params.id));

const mode = ref('manual');
const wizardStep = ref(1);
const loadError = ref(null);
const campaign = ref({});
const accounts = ref([]);
const campaignResourceUrl = ref('');
const targetUrl = ref('');
const linkSource = ref(LINK_SOURCE.BATCH);
const trackClicks = ref(true);
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
const pasteText = ref('');
const pasteErrors = ref([]);
const pasteMessage = ref(null);
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
const activeJobs = ref([]);
const activeJobsPanelRef = ref(null);
const startingJob = ref(false);
const cancellingJob = ref(false);
const lastLogId = ref(0);
let pollTimer = null;

const isJobActive = computed(
  () => activeJob.value && ['queued', 'running'].includes(activeJob.value.status)
);

function jobUsesAccount(job, accId) {
  if (!job || !accId) return false;
  if (job.job_mode === 'auto') return true;
  const ids = new Set(job.account_ids || []);
  if (job.telegram_account_id) ids.add(job.telegram_account_id);
  return ids.has(accId);
}

const isSelectedAccountBusy = computed(() =>
  activeJobs.value.some(
    (j) => ['queued', 'running'].includes(j.status) && jobUsesAccount(j, accountId.value)
  )
);

function onActiveJobsUpdate(jobs) {
  activeJobs.value = jobs;
}

const avatarAnchorGroups = computed(() => getAvatarAnchorGroups(manualRows.value));

function setAnchorSpan(anchorIndex, span) {
  manualRows.value[anchorIndex].avatarSpan = span;
  normalizeAvatarSpans(manualRows.value);
}

function onAnchorAvatarFile(anchorIndex, file) {
  manualRows.value[anchorIndex].avatarFile = file;
}

function onAnchorAvatarPreview(anchorIndex, preview) {
  const row = manualRows.value[anchorIndex];
  if (row.avatarPreview && row.avatarPreview !== preview) {
    URL.revokeObjectURL(row.avatarPreview);
  }
  row.avatarPreview = preview;
  if (!preview) row.avatarFile = null;
}

const readyAccounts = computed(() =>
  accounts.value.filter(
    (a) => a.status === 'ready' && a.can_create_bots !== false && !a.is_banned
  )
);

const selectedAccount = computed(() =>
  readyAccounts.value.find((a) => a.id === accountId.value) ?? null
);

const freeSlots = computed(() => {
  if (!selectedAccount.value) return 0;
  return Math.max(0, selectedAccount.value.max_bots_limit - selectedAccount.value.bots_created);
});

const usesReferralApi = computed(
  () =>
    !!(campaign.value?.referral_endpoint_url?.trim() && campaign.value?.referral_api_key?.trim())
);

const useReferralLinks = computed(() => isReferralLinkSource(linkSource.value));

const sharedBatchUrl = computed(() =>
  sharedLinkUrl(linkSource.value, {
    campaignResourceUrl: campaignResourceUrl.value,
    batchUrl: targetUrl.value,
  })
);

const resolvedLinkMode = computed(() => effectiveLinkMode(linkSource.value, trackClicks.value));

const linkPreviewUrl = computed(() => {
  if (useReferralLinks.value || trackClicks.value) return '';
  if (linkSource.value === LINK_SOURCE.PER_BOT) return '';
  return sharedBatchUrl.value;
});

const manualValidation = computed(() =>
  validateManualBulkBatch(manualRows.value, selectedAccount.value, sharedTexts.value, {
    linkSource: linkSource.value,
    campaignResourceUrl: campaignResourceUrl.value,
    batchUrl: targetUrl.value,
  })
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
    isLinkStepValid(linkSource.value, {
      usesReferralApi: usesReferralApi.value,
      campaignResourceUrl: campaignResourceUrl.value,
      batchUrl: targetUrl.value,
    })
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
    !isSelectedAccountBusy.value &&
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

const pendingBotCount = computed(() => {
  const pending = queueItems.value.filter((i) => i.queueStatus !== 'done').length;
  return pending || readyRowsCount.value;
});

const pacingSummary = computed(() => formatPacingSummary(settingsStore.botfatherPacing));

const creationEta = computed(() =>
  formatDurationSec(
    estimateBulkCreationSec(pendingBotCount.value, settingsStore.botfatherPacing)
  )
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
  return first?.draft?.public_link || linkPreviewUrl.value || sharedBatchUrl.value || '';
});

const canGenerate = computed(
  () =>
    isLinkStepValid(linkSource.value, {
      usesReferralApi: usesReferralApi.value,
      campaignResourceUrl: campaignResourceUrl.value,
      batchUrl: targetUrl.value,
    }) &&
    readyAccounts.value.length &&
    rowsAiReadyCount.value > 0 &&
    !aiValidation.value.errors.length
);

const canCreateAi = computed(
  () => rowsReadyCount.value > 0 && !aiValidation.value.errors.length
);

function applySnapshotToForm(payload, sourceJobId) {
  if (!payload || payload.mode !== 'manual') return false;

  accountId.value = payload.telegram_account_id;
  linkSource.value = payload.link_source || LINK_SOURCE.BATCH;
  if (payload.link_source === LINK_SOURCE.BATCH && payload.default_target_url) {
    targetUrl.value = payload.default_target_url;
  }
  trackClicks.value = (payload.link_mode || 'redirect') === 'redirect';
  autoStart.value = payload.auto_start !== false;
  if (payload.shared_texts) {
    sharedTexts.value = {
      description: payload.shared_texts.description || '',
      welcome_message: payload.shared_texts.welcome_message || '',
      about_text: payload.shared_texts.about_text || '',
      welcome_button_enabled: payload.shared_texts.welcome_button_enabled !== false,
      welcome_button_text: payload.shared_texts.welcome_button_text || 'Перейти по ссылке',
    };
  }

  const bots = payload.bots || [];
  const maxId = Math.max(...bots.map((b) => b.row_id || 0), 0);
  rowSeq = Math.max(rowSeq, maxId);
  manualRows.value = bots.map((bot) => ({
    id: bot.row_id,
    displayName: bot.display_name || '',
    username: (bot.username || '').replace(/^@/, ''),
    targetUrl: bot.target_url || '',
    avatarFile: null,
    avatarPreview: null,
    avatarSpan: 1,
    queueStatus: 'pending',
    error: null,
    createdBotId: null,
    _snapshotJobId: sourceJobId,
    _hasSnapshotAvatar: !!bot.avatar_storage_path,
  }));
  return true;
}

async function hydrateSnapshotAvatars(sourceJobId) {
  await Promise.all(
    manualRows.value.map(async (row) => {
      if (!row._hasSnapshotAvatar || !sourceJobId) return;
      try {
        const blob = await jobService.fetchSnapshotAvatarBlob(sourceJobId, row.id);
        row.avatarPreview = URL.createObjectURL(blob);
        row.avatarFile = jobService.snapshotAvatarToFile(blob, row.id);
      } catch {
        /* avatar missing on disk */
      }
    })
  );
}

async function restoreFromHistory(job) {
  submitError.value = null;
  const full = job.input_snapshot
    ? job
    : await jobService.get(job.id, { includeSnapshots: true });
  const payload = full.result_snapshot?.retry_payload || full.input_snapshot;
  if (!applySnapshotToForm(payload, job.id)) {
    submitError.value = 'Восстановление доступно только для ручных партий';
    return;
  }
  await hydrateSnapshotAvatars(job.id);
  manualRows.value.forEach((r) => {
    if (r.displayName?.trim() && r.username?.trim()) {
      r.queueStatus = 'pending';
      r.error = null;
    }
  });
  creationFinished.value = false;
  creationSummary.value = '';
  creationLogs.value = [];
  activeJob.value = null;
  wizardStep.value = 2;
}

function accountLabel(a) {
  return accountDisplayLabel(a);
}

function targetUrlForDraft() {
  if (useReferralLinks.value) {
    return sharedBatchUrl.value || 'https://referral.pending';
  }
  return sharedBatchUrl.value;
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
  const batch = await jobService.getLogs(activeJob.value.id, lastLogId.value, {
    minLevel: uiPrefs.verboseLogs ? 'debug' : 'info',
  });
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
    await activeJobsPanelRef.value?.loadJobs?.();
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
  activeJobs.value = data.activeJobs?.length
    ? data.activeJobs
    : data.activeJob
      ? [data.activeJob]
      : [];

  const queryJobId = Number(route.query.jobId);
  let job = null;
  if (queryJobId) {
    job =
      activeJobs.value.find((j) => j.id === queryJobId) ||
      (await jobService.get(queryJobId));
  } else {
    job = activeJobs.value.find(
      (j) => ['queued', 'running'].includes(j.status) && jobUsesAccount(j, accountId.value)
    );
  }
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
    applyCampaignButtonDefaults(sharedTexts.value, campaign.value);
  }
  normalizeAvatarSpans(manualRows.value);
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
  normalizeAvatarSpans(manualRows.value);
}

function addRows(n) {
  for (let i = 0; i < n; i++) addRow();
}

function clearPaste() {
  pasteText.value = '';
  pasteErrors.value = [];
  pasteMessage.value = null;
}

function applyPasteList() {
  pasteMessage.value = null;
  const { entries, errors } = parseBulkBotPaste(pasteText.value);
  pasteErrors.value = errors;

  if (!entries.length) {
    pasteMessage.value = errors.length ? null : 'Не найдено строк для импорта';
    return;
  }

  const limit = Math.max(1, freeSlots.value || entries.length);
  const slice = entries.slice(0, limit);

  manualRows.value.forEach((r) => {
    if (r.avatarPreview) URL.revokeObjectURL(r.avatarPreview);
  });

  manualRows.value = slice.map((e) => {
    const row = newManualRow();
    row.displayName = e.displayName;
    row.username = e.username;
    return row;
  });
  normalizeAvatarSpans(manualRows.value);

  const skipped = entries.length - slice.length;
  pasteMessage.value =
    `Загружено ${slice.length} бот(ов) в таблицу` +
    (skipped > 0 ? ` (ещё ${skipped} не вошли — лимит слотов на аккаунте)` : '');
}

function removeManualRow(i) {
  const anchor = findAnchorForRowIndex(manualRows.value, i);
  if (anchor && i === anchor.index && anchor.span > 1) {
    const next = manualRows.value[i + 1];
    if (next) {
      next.avatarFile = manualRows.value[i].avatarFile;
      next.avatarPreview = manualRows.value[i].avatarPreview;
      next.avatarSpan = anchor.span - 1;
    }
  } else if (anchor && i > anchor.index) {
    manualRows.value[anchor.index].avatarSpan = anchor.span - 1;
  }
  const removed = manualRows.value[i];
  if (removed?.avatarPreview) URL.revokeObjectURL(removed.avatarPreview);
  manualRows.value.splice(i, 1);
  normalizeAvatarSpans(manualRows.value);
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
      default_target_url: linkSource.value === LINK_SOURCE.PER_BOT ? '' : sharedBatchUrl.value,
      link_mode: resolvedLinkMode.value,
      auto_start: autoStart.value,
      link_source: linkSource.value,
      use_referral_api: useReferralLinks.value,
      shared_texts: sharedTexts.value,
      bots: rowsToCreate.map((r) => ({
        row_id: r.id,
        display_name: r.displayName.trim(),
        username: r.username.replace(/^@/, '').trim(),
        target_url:
          linkSource.value === LINK_SOURCE.PER_BOT ? r.targetUrl?.trim() || null : null,
      })),
    })
  );
  for (const row of rowsToCreate) {
    const avatarFile = resolveRowAvatar(row, manualRows.value);
    if (avatarFile) {
      form.append(`avatar_${row.id}`, avatarFile);
    }
  }

  try {
    const job = await campaignService.startManualBulk(campaignId.value, form);
    activeJob.value = job;
    saveJobSnapshot(job.id);
    startJobPolling();
    await pollJob();
    await activeJobsPanelRef.value?.loadJobs?.();
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
      targetUrl: targetUrlForDraft(),
      keyword: row.keyword.trim(),
      linkMode: resolvedLinkMode.value,
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
        targetUrl: targetUrlForDraft(),
        keyword: row.keyword.trim(),
        linkMode: resolvedLinkMode.value,
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
  const url = targetUrlForDraft();
  return {
    campaign_id: campaignId.value,
    telegram_account_id: row.accountId,
    target_url: url,
    display_name: d.display_name.trim(),
    username: d.username.replace(/^@/, '').trim(),
    description: d.description,
    about_text: d.about_text,
    welcome_message: d.welcome_message,
    welcome_button_enabled: d.welcome_button_enabled,
    welcome_button_text: d.welcome_button_text,
    keyword: row.keyword.trim() || null,
    redirect_slug: d.redirect_slug,
    link_mode: resolvedLinkMode.value,
    create_via_botfather: true,
    auto_start: autoStart.value,
    generate_avatar: true,
    use_referral_api: useReferralLinks.value,
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
    applyCampaignButtonDefaults(sharedTexts.value, c);
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

watch([linkSource, campaignResourceUrl, usesReferralApi], () => {
  if (linkSource.value === LINK_SOURCE.REFERRAL && !usesReferralApi.value) {
    linkSource.value = pickDefaultLinkSource({
      usesReferralApi: false,
      campaignResourceUrl: campaignResourceUrl.value,
    });
  }
  if (linkSource.value === LINK_SOURCE.CAMPAIGN && !campaignResourceUrl.value?.trim()) {
    linkSource.value = LINK_SOURCE.BATCH;
  }
});

onMounted(async () => {
  try {
    await settingsStore.fetchBotfatherPacing();
    const data = await campaignService.get(campaignId.value);
    campaign.value = data.campaign;
    campaignResourceUrl.value = data.campaign.resource_url || '';
    if (campaignResourceUrl.value) {
      targetUrl.value = campaignResourceUrl.value;
    }
    linkSource.value = pickDefaultLinkSource({
      usesReferralApi: !!(
        data.campaign.referral_endpoint_url?.trim() && data.campaign.referral_api_key?.trim()
      ),
      campaignResourceUrl: campaignResourceUrl.value,
    });
    sharedTexts.value.description = data.campaign.default_description || '';
    sharedTexts.value.welcome_message = data.campaign.default_welcome_message || '';
    sharedTexts.value.about_text = data.campaign.default_about_text || '';
    applyCampaignButtonDefaults(sharedTexts.value, data.campaign);

    accounts.value = await campaignService.getAccounts(campaignId.value);
    const first = readyAccounts.value[0];
    if (first) accountId.value = first.id;

    activeJobs.value = data.activeJobs?.length
      ? data.activeJobs
      : data.activeJob
        ? [data.activeJob]
        : [];

    await tryResumeActiveJob();

    const restoreJobId = Number(route.query.restoreJob);
    if (restoreJobId) {
      const job = await jobService.get(restoreJobId, { includeSnapshots: true });
      await restoreFromHistory(job);
    }
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

.inline-link {
  color: #93c5fd;
  text-decoration: none;
}

.inline-link:hover {
  text-decoration: underline;
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

.block {
  padding: 1.25rem;
}

.block-hint {
  margin: 0 0 1rem;
}

.history-link-block {
  margin-top: 1rem;
}

.history-page-link {
  color: #93c5fd;
  text-decoration: none;
  font-size: 0.9rem;
}

.history-page-link:hover {
  text-decoration: underline;
}

.history-block {
  margin-top: 1rem;
}

.job-history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.job-history-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.job-history-main {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.job-history-date {
  font-size: 0.78rem;
}

.job-history-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.history-failed {
  color: #f87171;
}

.history-view-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.history-view-meta {
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
}

.link-btn {
  background: none;
  border: none;
  color: #93c5fd;
  cursor: pointer;
  text-align: left;
  padding: 0;
  font: inherit;
}

.link-btn:hover {
  text-decoration: underline;
}

.link-api-hint {
  font-size: 0.85rem;
  font-style: italic;
  word-break: break-all;
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

.manual-table-header {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0.15rem;
}

.manual-head-avatar {
  width: 3.75rem;
  flex-shrink: 0;
  font-size: 0.7rem;
  color: var(--muted);
  text-align: center;
}

.manual-head-cols {
  flex: 1;
  min-width: 0;
  border-bottom: none;
  padding-bottom: 0;
}

.manual-grid-no-avatar {
  display: grid;
  grid-template-columns: 2rem 1.2fr 1.1fr 1.3fr 2rem;
  gap: 0.4rem;
  align-items: center;
}

.manual-group {
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid var(--border);
}

.manual-group:last-child {
  border-bottom: none;
}

.manual-group-avatar {
  width: 3.75rem;
  flex-shrink: 0;
  padding: 0.45rem 0.35rem;
  border-right: 1px solid var(--border);
  background: rgba(8, 12, 20, 0.25);
}

.manual-group-rows {
  flex: 1;
  min-width: 0;
}

.avatar-hint {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
}

.paste-block {
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: rgba(8, 12, 20, 0.35);
}

.paste-block summary {
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text);
}

.paste-block code {
  font-size: 0.78rem;
  color: #93c5fd;
}

.paste-input {
  width: 100%;
  margin-top: 0.65rem;
  font-size: 0.85rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  line-height: 1.45;
}

.paste-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.paste-msg.ok {
  margin: 0.5rem 0 0;
  font-size: 0.82rem;
  color: #4ade80;
}

.paste-errors {
  margin-top: 0.5rem;
}

.row-err--inline {
  margin: 0.15rem 0 0.35rem 2rem;
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

.manual-group-rows .bulk-row {
  border-bottom: none;
  padding: 0.5rem 0.35rem;
}

.manual-group-rows .bulk-row:not(:last-child) {
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.bulk-row {
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}

.bulk-row:hover {
  background: rgba(59, 130, 246, 0.03);
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
