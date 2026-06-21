<template>
  <div class="bot-create">
    <header class="page-header">
      <h1>Один бот</h1>
      <p class="subtitle">Аккаунт и ссылка → тексты (вручную или через AI) → создание в Telegram.</p>
    </header>

    <WizardSteps
      :steps="[{ label: 'Основное' }, { label: 'Тексты' }, { label: 'Создание' }]"
      :current="wizardStep"
      :clickable="!submitting && !generating"
      @go="wizardStep = $event"
    />

    <div :class="['bot-create-body', { 'form-with-preview': wizardStep >= 2 }]">
      <form class="card form" @submit.prevent="onSubmit">
        <div v-show="wizardStep === 1" class="wizard-pane">
          <div
            v-if="campaignId && campaignResourceUrl && !useCustomUrl"
            class="url-from-campaign card-inner"
          >
            <label>Ссылка на сервис</label>
            <p class="url-value">
              <a :href="campaignResourceUrl" target="_blank" rel="noopener noreferrer">{{ campaignResourceUrl }}</a>
            </p>
            <p class="field-hint">Из настроек кампании.</p>
            <button type="button" class="link-btn" @click="useCustomUrl = true">Другая ссылка для этого бота</button>
          </div>
          <div v-else class="form-group">
            <label>Ссылка на рекламируемый сервис *</label>
            <input v-model="targetUrl" type="url" required placeholder="https://example.com/landing" />
            <button
              v-if="campaignId && campaignResourceUrl"
              type="button"
              class="link-btn"
              @click="useCampaignUrl"
            >
              ← Вернуть ссылку из кампании
            </button>
          </div>

          <BotLinkModeField v-model="linkMode" :preview-url="linkPreview || ''" />

          <div v-if="!routeCampaignId" class="form-group">
            <label>Кампания</label>
            <select v-model.number="campaignId" required @change="onCampaignChange">
              <option :value="null" disabled>Выберите кампанию</option>
              <option v-for="c in campaigns" :key="c.id" :value="c.id">{{ c.title }}</option>
            </select>
          </div>

          <div class="form-group">
            <label>Аккаунт Telegram</label>
            <select v-model.number="accountId" required :disabled="!usableAccounts.length">
              <option :value="null" disabled>Выберите аккаунт</option>
              <option v-for="a in usableAccounts" :key="a.id" :value="a.id">
                {{ accountOptionLabel(a) }}
              </option>
            </select>
            <p v-if="campaignId && accounts.length && !usableAccounts.length" class="field-hint error-text">
              Нет доступных аккаунтов (нужен статус «Готов», не забанен, есть свободные слоты).
              <RouterLink :to="{ name: 'campaign-workspace', params: { id: campaignId }, query: { tab: 'accounts' } }">
                Добавьте и проверьте
              </RouterLink>.
            </p>
          </div>
          <button type="button" class="btn btn-next" :disabled="!canGoStep2" @click="goToTextsStep">
            Далее: тексты →
          </button>
        </div>

        <div v-show="wizardStep === 2" class="wizard-pane">
          <div class="ai-block card-inner">
            <div class="form-group">
              <label>Ключевая фраза <span class="optional">(только для AI)</span></label>
              <input v-model="keyword" type="text" placeholder="например: vpn бот бесплатно" />
              <p class="field-hint">Необязательна при ручном вводе текстов ниже.</p>
            </div>
            <button
              type="button"
              class="btn-ai"
              :disabled="!campaignId || !accountId || !effectiveTargetUrl.trim() || !keyword.trim() || generating"
              @click="onGenerate"
            >
              {{ generating ? 'Генерация…' : '✨ Заполнить тексты по фразе (AI)' }}
            </button>
          </div>

          <BotProfileFields
            v-model="form"
            v-model:generate-avatar="generateAvatar"
            :keyword="keyword"
            :avatar-prompt="avatarPrompt"
            :public-link="linkPreview || ''"
            show-generate-on-create
            collapse-long-fields
            @update:avatar-file="avatarFile = $event"
            @update:avatar-preview="avatarPreviewUrl = $event"
          />

          <label class="check">
            <input v-model="autoStart" type="checkbox" />
            Запустить бота сразу после создания
          </label>
          <div class="wizard-nav">
            <button type="button" class="btn-ghost" @click="wizardStep = 1">← Назад</button>
            <button type="button" class="btn btn-next" :disabled="!canGoStep3" @click="wizardStep = 3">
              Далее: создание →
            </button>
          </div>
        </div>

        <div v-show="wizardStep === 3" class="wizard-pane">
          <p v-if="submitError" class="error-text">{{ submitError }}</p>
          <OperationStatus v-if="submitting" :message="jobProgress" :status="jobStatus" />
          <InlineTaskIndicator v-if="submitting" fallback-label="Создаём бота в Telegram…" />
          <div class="actions">
            <button type="button" class="btn-ghost" @click="wizardStep = 2">← К текстам</button>
            <button type="submit" class="btn" :disabled="submitting || !canGoStep3 || !effectiveTargetUrl.trim()">
              {{ submitting ? 'Создание…' : 'Создать бота в Telegram' }}
            </button>
          </div>
        </div>
      </form>

      <BotTelegramPreview
        v-if="wizardStep >= 2"
        :display-name="form.display_name"
        :username="form.username"
        :about-text="form.about_text"
        :description="form.description"
        :welcome-message="form.welcome_message"
        :welcome-button-enabled="form.welcome_button_enabled"
        :welcome-button-text="form.welcome_button_text"
        :avatar-url="avatarPreviewUrl"
        :public-link="linkPreview || ''"
      />
    </div>
  </div>
</template>

<script setup>
import { newIdempotencyKey } from '../utils/apiClient';
import { pollCreationJob } from '../utils/serverTaskProgress';
import { computed, onMounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import BotLinkModeField from '../components/BotLinkModeField.vue';
import BotProfileFields from '../components/BotProfileFields.vue';
import BotTelegramPreview from '../components/BotTelegramPreview.vue';
import InlineTaskIndicator from '../components/InlineTaskIndicator.vue';
import OperationStatus from '../components/OperationStatus.vue';
import WizardSteps from '../components/WizardSteps.vue';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { applyCampaignTextDefaults, applyCampaignButtonDefaults } from '../utils/campaignTextDefaults';
import { accountDisplayLabel } from '../utils/accountLabel';
import { formatWaitLabel, getFloodWaitSeconds } from '../utils/floodWait';

const taskStore = useAsyncTaskStore();
const route = useRoute();
const router = useRouter();

const routeCampaignId = route.params.id ? Number(route.params.id) : null;
const wizardStep = ref(1);
const campaigns = ref([]);
const accounts = ref([]);
const campaignId = ref(routeCampaignId || (route.query.campaign_id ? Number(route.query.campaign_id) : null));

const campaignResourceUrl = ref('');
const campaignMeta = ref(null);
const useCustomUrl = ref(false);
const targetUrl = ref('');
const accountId = ref(null);
const keyword = ref('');
const linkMode = ref('redirect');
const redirectSlug = ref(null);
const draftPublicLink = ref(null);
const generating = ref(false);
const submitting = ref(false);
const submitError = ref(null);
const jobProgress = ref('');
const jobStatus = ref('');
const autoStart = ref(true);
const generateAvatar = ref(true);
const avatarFile = ref(null);
const avatarPreviewUrl = ref(null);
const avatarPrompt = ref('');
const form = ref({
  display_name: '',
  username: '',
  description: '',
  about_text: '',
  welcome_message: '',
  welcome_button_enabled: true,
  welcome_button_text: 'Перейти по ссылке',
});

const STATUS_LABELS = {
  ready: 'готов',
  creating: 'создание',
  pending: 'ожидание',
  error: 'ошибка',
  exhausted: 'лимит ботов',
  disabled: 'отключён',
};

const effectiveTargetUrl = computed(() => {
  if (campaignId.value && campaignResourceUrl.value && !useCustomUrl.value) {
    return campaignResourceUrl.value;
  }
  return targetUrl.value;
});

const canGoStep2 = computed(
  () =>
    campaignId.value &&
    accountId.value &&
    effectiveTargetUrl.value.trim() &&
    usableAccounts.value.length
);

const canGoStep3 = computed(
  () => !!form.value.display_name?.trim() && !!form.value.username?.trim()
);

const linkPreview = computed(() => {
  if (draftPublicLink.value) return draftPublicLink.value;
  if (linkMode.value === 'direct' && effectiveTargetUrl.value.trim()) return effectiveTargetUrl.value.trim();
  return null;
});

function useCampaignUrl() {
  useCustomUrl.value = false;
  targetUrl.value = campaignResourceUrl.value;
}

function goToTextsStep() {
  if (campaignMeta.value) {
    applyCampaignTextDefaults(form.value, campaignMeta.value);
    applyCampaignButtonDefaults(form.value, campaignMeta.value);
  }
  wizardStep.value = 2;
}

const usableAccounts = computed(() =>
  accounts.value.filter((a) => {
    if (a.is_banned) return false;
    if (a.status === 'disabled') return false;
    if (a.bots_created >= a.max_bots_limit) return false;
    return ['ready', 'creating', 'pending', 'error', 'exhausted'].includes(a.status);
  })
);

function accountOptionLabel(a) {
  const name = accountDisplayLabel(a);
  const st = STATUS_LABELS[a.status] || a.status;
  return `${name} — ${st} (${a.bots_created}/${a.max_bots_limit} ботов)`;
}

async function loadCampaignMeta() {
  if (!campaignId.value) {
    campaignResourceUrl.value = '';
    return;
  }
  const data = await campaignService.get(campaignId.value);
  campaignMeta.value = data.campaign || null;
  campaignResourceUrl.value = data.campaign?.resource_url || '';
  if (campaignResourceUrl.value) {
    if (!useCustomUrl.value) targetUrl.value = campaignResourceUrl.value;
  } else {
    useCustomUrl.value = true;
  }
}

async function loadCampaigns() {
  campaigns.value = await campaignService.list();
  if (campaignId.value) {
    const c = campaigns.value.find((x) => x.id === campaignId.value);
    if (c?.resource_url) {
      campaignResourceUrl.value = c.resource_url;
      if (!useCustomUrl.value) targetUrl.value = c.resource_url;
    }
  }
}

async function loadAccounts() {
  if (!campaignId.value) {
    accounts.value = [];
    return;
  }
  accounts.value = await campaignService.getAccounts(campaignId.value);
  const pick =
    usableAccounts.value.find((a) => a.status === 'ready' || a.status === 'creating') ??
    usableAccounts.value[0];
  accountId.value = pick?.id ?? null;
}

async function onCampaignChange() {
  accountId.value = null;
  keyword.value = '';
  const c = campaigns.value.find((x) => x.id === campaignId.value);
  if (c?.resource_url) {
    campaignResourceUrl.value = c.resource_url;
    if (!useCustomUrl.value) targetUrl.value = c.resource_url;
  }
  await loadAccounts();
}

async function onGenerate() {
  if (!keyword.value.trim()) {
    submitError.value = 'Укажите ключевую фразу для генерации текстов нейросетью';
    return;
  }
  generating.value = true;
  submitError.value = null;
  try {
    const draft = await botService.generateDraft({
      campaignId: campaignId.value,
      accountId: accountId.value,
      targetUrl: effectiveTargetUrl.value.trim(),
      keyword: keyword.value.trim(),
      redirectSlug: redirectSlug.value,
      linkMode: linkMode.value,
    });
    redirectSlug.value = draft.redirect_slug;
    draftPublicLink.value = draft.public_link;
    if (draft.link_mode) linkMode.value = draft.link_mode;
    targetUrl.value = draft.target_url || targetUrl.value;
    form.value.display_name = draft.display_name;
    form.value.username = draft.username;
    form.value.description = draft.description;
    form.value.about_text = draft.about_text || '';
    form.value.welcome_message = draft.welcome_message;
    form.value.welcome_button_enabled = draft.welcome_button_enabled !== false;
    form.value.welcome_button_text = draft.welcome_button_text || 'Перейти по ссылке';
    avatarPrompt.value = draft.avatar_prompt || '';
    if (draft.keyword) keyword.value = draft.keyword;
    if (draft.ai_hint) submitError.value = draft.ai_hint;
  } catch (e) {
    submitError.value = formatApiError(e, 'Ошибка генерации AI');
  } finally {
    generating.value = false;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForSingleBotJob(jobId, logStep, setServerProgress) {
  const job = await pollCreationJob(jobId, {
    logStep,
    onProgress: (msg, st) => {
      jobProgress.value = msg || jobProgress.value;
      jobStatus.value = st || '';
      setServerProgress?.(msg, st);
    },
  });
  const rows = job.result_snapshot?.row_results || [];
  const botId = rows.find((r) => r.status === 'done')?.bot_id;
  if (botId) return botService.get(botId);
  throw new Error('Задача завершена, но бот не найден в результате');
}

async function createBotWithFloodRetry(uname, logStep, setServerProgress) {
  const payload = {
    campaign_id: campaignId.value,
    telegram_account_id: accountId.value,
    target_url: effectiveTargetUrl.value.trim(),
    display_name: form.value.display_name,
    username: uname,
    description: form.value.description,
    about_text: form.value.about_text,
    welcome_message: form.value.welcome_message,
    welcome_button_enabled: form.value.welcome_button_enabled,
    welcome_button_text: form.value.welcome_button_text,
    keyword: keyword.value.trim() || null,
    redirect_slug: redirectSlug.value,
    link_mode: linkMode.value,
    create_via_botfather: true,
    auto_start: autoStart.value,
    generate_avatar: generateAvatar.value,
  };
  const idempotencyKey = newIdempotencyKey();
  let retries = 0;
  while (retries <= 3) {
    try {
      const result = await botService.create(payload, avatarFile.value, { idempotencyKey });
      if (result.queued && result.job?.id) {
        logStep('Бот поставлен в очередь создания', 'info', { job_id: result.job.id });
        return waitForSingleBotJob(result.job.id, logStep, setServerProgress);
      }
      return result.bot;
    } catch (e) {
      const waitSec = getFloodWaitSeconds(e);
      if (waitSec != null && retries < 3) {
        for (let s = Math.ceil(waitSec); s > 0; s -= 1) {
          submitError.value = `Лимит Telegram, осталось ${formatWaitLabel(s)}…`;
          await sleep(1000);
        }
        submitError.value = null;
        retries += 1;
        continue;
      }
      throw e;
    }
  }
  throw new Error('Не удалось создать бота');
}

async function onSubmit() {
  if (!canGoStep3.value) {
    submitError.value = 'Заполните имя и username бота';
    wizardStep.value = 2;
    return;
  }
  submitting.value = true;
  submitError.value = null;
  jobProgress.value = '';
  jobStatus.value = '';
  const uname = form.value.username.replace(/^@/, '');
  try {
    const bot = await taskStore.run(
      'CREATE_BOT',
      async ({ logStep, setServerProgress }) => {
        logStep(`Создание @${uname} через BotFather`, 'info');
        const b = await createBotWithFloodRetry(uname, logStep, setServerProgress);
        logStep(`Бот #${b.id} @${b.username} создан`, 'success', { bot_id: b.id });
        return b;
      },
      { username: uname }
    );
    router.push({ name: 'bot-edit', params: { id: bot.id }, query: { created: '1' } });
  } catch (e) {
    submitError.value = formatApiError(e, 'Не удалось создать бота');
  } finally {
    submitting.value = false;
  }
}

watch(campaignId, loadAccounts);
onMounted(async () => {
  await loadCampaigns();
  await loadCampaignMeta();
  await loadAccounts();
});
</script>

<style scoped>
.bot-create-body.form-with-preview {
  max-width: 1100px;
}
</style>
