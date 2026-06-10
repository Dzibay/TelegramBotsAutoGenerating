<template>
  <div v-if="loading" class="muted">Загрузка кампании…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>

  <div v-else class="detail">
    <header class="detail-header">
      <RouterLink to="/app" class="back">← Все кампании</RouterLink>
      <div class="title-row">
        <h1>{{ campaign.title }}</h1>
        <StatusBadge :status="campaign.status" />
        <div class="header-btns">
          <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }" class="btn-ghost btn-sm">
            Изменить
          </RouterLink>
          <button type="button" class="btn-ghost btn-sm btn-danger" @click="onDeleteCampaign">
            Удалить
          </button>
        </div>
      </div>
      <p v-if="campaign.resource_url" class="resource">
        Сервис:
        <a :href="campaign.resource_url" target="_blank" rel="noopener noreferrer">{{ campaign.resource_url }}</a>
      </p>
    </header>

    <WorkspaceTabs v-model="activeTab" :tabs="workspaceTabs" />

    <CampaignJobBanner
      v-if="job && isPolling"
      :job="job"
      :logs="logs"
      :logs-loading="logsLoading"
      :active="isPolling"
      :cancelling="cancellingJob"
      :bulk-link="bulkCreateLink"
      :elapsed-sec="jobElapsedSec"
      @cancel="onCancelJob"
    />

    <section v-show="activeTab === 'guide'" class="guide card">
      <h2>Что делать дальше</h2>
      <div v-if="nextStepGuide" class="next-step card-inner">
        <p class="next-step-label">{{ nextStepGuide.title }}</p>
        <p v-if="nextStepGuide.hint" class="next-step-hint muted">{{ nextStepGuide.hint }}</p>
        <div class="next-step-actions">
          <RouterLink
            v-if="nextStepGuide.route"
            :to="nextStepGuide.route"
            class="btn btn-sm"
          >
            {{ nextStepGuide.actionLabel }}
          </RouterLink>
          <button
            v-else-if="nextStepGuide.action"
            type="button"
            class="btn btn-sm"
            @click="nextStepGuide.action()"
          >
            {{ nextStepGuide.actionLabel }}
          </button>
          <button
            v-if="canStart && nextStepGuide.showAutoStart"
            type="button"
            class="btn btn-sm btn-ghost"
            :disabled="starting"
            @click="onStart"
          >
            {{ starting ? 'Запуск…' : 'Авто-создание по ключевым словам' }}
          </button>
        </div>
      </div>
      <ol class="checklist">
        <li :class="{ ok: campaign.resource_url }">
          <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }">Ссылка на сервис</RouterLink>
          {{ campaign.resource_url ? '— указана' : '— укажите в настройках' }}
        </li>
        <li :class="{ ok: campaign.accounts_count > 0 }">
          <a href="#" @click.prevent="activeTab = 'accounts'">Аккаунты в кампании</a>
          — {{ campaign.accounts_count ? `${campaign.accounts_count} добавлено` : 'добавьте из подготовленных' }}
        </li>
        <li :class="{ ok: readyAccountsCount > 0 }">
          Готовых к созданию ботов: {{ readyAccountsCount }}
        </li>
        <li :class="{ ok: campaign.bots_count > 0 }">
          <a href="#" @click.prevent="activeTab = 'list'">Боты</a>
          — {{ campaign.bots_count }} шт.
        </li>
      </ol>
    </section>

    <div v-show="activeTab !== 'accounts'" class="stats">
      <div class="stat card">
        <Users :size="18" class="stat-icon stat-icon--blue" />
        <span class="stat-val">{{ campaign.accounts_count }}</span>
        <span class="stat-label">Аккаунтов</span>
      </div>
      <div class="stat card">
        <Bot :size="18" class="stat-icon stat-icon--purple" />
        <span class="stat-val">{{ campaign.bots_count }}</span>
        <span class="stat-label">Ботов</span>
      </div>
      <div class="stat card">
        <Zap :size="18" class="stat-icon stat-icon--green" />
        <span class="stat-val">{{ campaign.active_bots_count }}</span>
        <span class="stat-label">Активных</span>
      </div>
    </div>

    <section v-show="activeTab === 'create'" class="create-hub card">
      <h2>Создание ботов</h2>
      <p class="muted intro">
        Тексты можно заполнить вручную или сгенерировать по фразе (AI). Фраза обязательна только для генерации.
      </p>
      <div class="create-cards">
        <component
          :is="canOpenCreate ? 'RouterLink' : 'div'"
          :to="canOpenCreate ? { name: 'campaign-bot-create', params: { id: campaignId } } : undefined"
          class="create-card create-card--primary"
          :class="{ 'create-card--disabled': !canOpenCreate }"
          :title="createBlockedReason || undefined"
          :aria-disabled="!canOpenCreate ? 'true' : undefined"
        >
          <span class="cc-title">Один бот</span>
          <span class="cc-desc">Пошагово: тексты вручную или через AI → создание в Telegram.</span>
        </component>
        <component
          :is="canOpenCreate ? 'RouterLink' : 'div'"
          :to="canOpenCreate ? { name: 'bulk-bot-create', params: { id: campaignId } } : undefined"
          class="create-card"
          :class="{ 'create-card--disabled': !canOpenCreate }"
          :title="createBlockedReason || undefined"
          :aria-disabled="!canOpenCreate ? 'true' : undefined"
        >
          <span class="cc-title">Несколько ботов</span>
          <span class="cc-desc">Общие тексты, список ботов с аватаром и ссылкой, создание по очереди.</span>
        </component>
      </div>
      <p v-if="createBlockedReason" class="warn-banner">{{ createBlockedReason }}</p>
    </section>

    <div v-show="activeTab === 'accounts'" class="grid-2">
      <div class="side side--full">
        <CampaignAccountsPanel
          ref="accountsPanelRef"
          :accounts="accounts"
          :can-add="canAddAccounts"
          :attaching="attaching"
          :verifying-all="verifyingAll"
          :busy="accountBusy || taskStore.isActive"
          :busy-id="accountBusyId"
          :bots-busy-id="botsBusyId"
          :delete-busy="deleteBotBusy"
          :bots-lists="accountBotsLists"
          :bots-error="accountBotsErrors"
          :attach-message="attachMessage"
          @attach="onAttachPrepared"
          @verify="onVerifyAccount"
          @verify-all="onVerifyAllAccounts"
          @remove="onRemoveAccount"
          @load-bots="onLoadAccountBots"
          @delete-bot="onDeleteAccountBot"
        />
      </div>
    </div>

    <section v-show="activeTab === 'list'" class="bots-list card">
      <div class="section-head">
        <h2>Боты кампании</h2>
        <RouterLink
          v-if="canOpenCreate"
          :to="{ name: 'campaign-bot-create', params: { id: campaignId } }"
          class="btn btn-sm"
        >
          + Один бот
        </RouterLink>
        <RouterLink
          v-if="canOpenCreate"
          :to="{ name: 'bulk-bot-create', params: { id: campaignId } }"
          class="btn btn-sm btn-ghost"
        >
          + Несколько
        </RouterLink>
      </div>

      <div v-if="bots.length" class="bots-filters">
        <input
          v-model="botSearch"
          type="search"
          class="search-input"
          placeholder="Поиск по имени, @username, фразе…"
        />
        <select v-model="botStatusFilter" class="filter-select">
          <option value="">Все статусы</option>
          <option value="active">Активные</option>
          <option value="draft">Черновики</option>
          <option value="creating">Создаются</option>
          <option value="stopped">Остановлены</option>
          <option value="error">С ошибкой</option>
        </select>
      </div>

      <p v-if="!bots.length" class="empty-bots">
        <EmptyState
          icon="🤖"
          title="Пока нет ботов"
          description="Создайте одного бота пошагово или запустите массовое создание на вкладке «Создание»."
        >
          <RouterLink v-if="canOpenCreate" :to="{ name: 'campaign-bot-create', params: { id: campaignId } }" class="btn btn-sm">
            Один бот
          </RouterLink>
          <RouterLink v-if="canOpenCreate" :to="{ name: 'bulk-bot-create', params: { id: campaignId } }" class="btn btn-sm btn-ghost">
            Несколько ботов
          </RouterLink>
        </EmptyState>
      </p>
      <p v-else-if="!filteredBots.length" class="muted empty-bots">Ничего не найдено. Измените поиск или фильтр.</p>
      <ul v-else class="mini-list bots">
        <li v-for="b in filteredBots" :key="b.id" class="bot-li">
          <div class="bot-li-main">
            <strong>@{{ b.username || '—' }}</strong>
            <span v-if="b.keyword" class="bot-kw">«{{ b.keyword }}»</span>
            <span>{{ b.display_name }}</span>
            <StatusBadge :status="b.status" />
            <a
              v-if="botLink(b)"
              :href="botLink(b)"
              target="_blank"
              rel="noopener noreferrer"
              class="tg-open"
            >
              Telegram ↗
            </a>
          </div>
          <div class="bot-li-actions">
            <button
              v-if="b.status !== 'active'"
              type="button"
              class="link-btn"
              @click="onBotStart(b)"
            >
              Запустить
            </button>
            <button v-else type="button" class="link-btn" @click="onBotStop(b)">Стоп</button>
            <RouterLink :to="{ name: 'bot-edit', params: { id: b.id } }" class="link-btn">
              Изменить
            </RouterLink>
            <button type="button" class="link-btn danger" @click="onBotDelete(b)">Удалить</button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { Bot, Users, Zap } from 'lucide-vue-next';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import CampaignAccountsPanel from '../components/CampaignAccountsPanel.vue';
import CampaignJobBanner from '../components/CampaignJobBanner.vue';
import EmptyState from '../components/EmptyState.vue';
import StatusBadge from '../components/StatusBadge.vue';
import WorkspaceTabs from '../components/WorkspaceTabs.vue';
import { useWorkflowStore } from '../stores/workflowStore';
import { useUiPrefsStore } from '../stores/uiPrefsStore';
import { botService } from '../services/botService';
import { campaignService, jobService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { telegramBotUrl } from '../utils/botLink';

const taskStore = useAsyncTaskStore();
const uiPrefs = useUiPrefsStore();

function accountLabel(account) {
  return account?.label || account?.phone || `Аккаунт #${account?.id}`;
}

function botLink(b) {
  return b.telegram_url || telegramBotUrl(b.username);
}

const route = useRoute();
const router = useRouter();
const workflow = useWorkflowStore();
const campaignId = computed(() => Number(route.params.id));

const activeTab = ref(route.query.tab || 'guide');
const workspaceTabs = computed(() => [
  { id: 'guide', label: 'Обзор' },
  { id: 'accounts', label: 'Аккаунты', badge: campaign.value.accounts_count || null },
  { id: 'create', label: 'Создание' },
  { id: 'list', label: 'Список ботов', badge: campaign.value.bots_count || null },
]);

watch(
  () => route.query.tab,
  (t) => {
    if (t && ['guide', 'accounts', 'create', 'list'].includes(t)) activeTab.value = t;
  }
);

watch(activeTab, (t) => {
  router.replace({ query: { ...route.query, tab: t } });
});

const loading = ref(true);
const loadError = ref(null);
const campaign = ref({});
const accounts = ref([]);
const bots = ref([]);
const job = ref(null);
const logs = ref([]);
const logsLoading = ref(false);
const lastLogId = ref(0);
const starting = ref(false);
const cancellingJob = ref(false);
const jobElapsedSec = ref(0);
const jobStartedAt = ref(null);
const attaching = ref(false);
const verifyingAll = ref(false);
const accountBusy = ref(false);
const accountBusyId = ref(null);
const botsBusyId = ref(null);
const deleteBotBusy = ref(null);
const accountBotsLists = ref({});
const accountBotsErrors = ref({});
const attachMessage = ref(null);
const accountsPanelRef = ref(null);
let pollTimer = null;
let elapsedTimer = null;

const readyAccountsCount = computed(
  () => accounts.value.filter((a) => a.status === 'ready' && a.can_create_bots).length
);

const hasServiceUrl = computed(
  () => !!(campaign.value.resource_url && String(campaign.value.resource_url).trim())
);

const canOpenCreate = computed(() => hasServiceUrl.value && readyAccountsCount.value > 0);

const createBlockedReason = computed(() => {
  if (!hasServiceUrl.value) {
    return 'Сначала укажите ссылку на сервис в настройках кампании.';
  }
  if (readyAccountsCount.value === 0) {
    return 'Нет готовых аккаунтов — на вкладке «Аккаунты» добавьте и нажмите «Проверить все».';
  }
  return null;
});

const botSearch = ref('');
const botStatusFilter = ref('');

const filteredBots = computed(() => {
  let list = bots.value;
  const q = botSearch.value.trim().toLowerCase();
  if (botStatusFilter.value) {
    list = list.filter((b) => b.status === botStatusFilter.value);
  }
  if (!q) return list;
  return list.filter((b) => {
    const hay = [
      b.username,
      b.display_name,
      b.keyword,
      String(b.id),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return hay.includes(q);
  });
});

const isPolling = computed(
  () => job.value && ['queued', 'running'].includes(job.value.status)
);

const bulkCreateLink = computed(() =>
  campaignId.value
    ? { name: 'bulk-bot-create', params: { id: campaignId.value }, query: { step: 3 } }
    : null
);

const campaignKeywords = computed(() => {
  const kw = campaign.value.keywords;
  return Array.isArray(kw) ? kw.filter(Boolean) : [];
});

const nextStepGuide = computed(() => {
  if (isPolling.value) {
    return {
      title: 'Идёт фоновая задача создания ботов',
      hint: 'Прогресс и журнал — в блоке выше. Можно переключаться между вкладками.',
      actionLabel: 'Открыть очередь',
      route: bulkCreateLink.value,
    };
  }
  if (!hasServiceUrl.value) {
    return {
      title: 'Шаг 1: укажите ссылку на сервис',
      hint: 'Без неё боты не смогут вести пользователей на ваш ресурс.',
      actionLabel: 'Настройки кампании',
      route: { name: 'campaign-edit', params: { id: campaignId.value } },
    };
  }
  if (campaign.value.accounts_count === 0) {
    return {
      title: 'Шаг 2: добавьте Telegram-аккаунты',
      hint: 'Выберите подготовленные аккаунты из пула и привяжите к кампании.',
      actionLabel: 'Перейти к аккаунтам',
      action: () => {
        activeTab.value = 'accounts';
      },
    };
  }
  if (readyAccountsCount.value === 0) {
    return {
      title: 'Шаг 3: проверьте аккаунты',
      hint: 'Нужен статус «Готов» и свободные слоты для создания ботов.',
      actionLabel: 'Проверить аккаунты',
      action: () => {
        activeTab.value = 'accounts';
      },
    };
  }
  return {
    title: 'Шаг 4: создайте ботов',
    hint: 'Один бот — пошагово. Несколько — массовая очередь с паузами BotFather.',
    actionLabel: 'Массовое создание',
    route: { name: 'bulk-bot-create', params: { id: campaignId.value } },
    showAutoStart: campaignKeywords.value.length > 0,
  };
});

const canStart = computed(
  () =>
    campaign.value.accounts_count > 0 &&
    (!job.value || !['queued', 'running'].includes(job.value.status)) &&
    ['draft', 'failed', 'completed', 'cancelled'].includes(campaign.value.status)
);

const canAddAccounts = computed(
  () => !job.value || !['running'].includes(job.value.status)
);

async function loadCampaign() {
  const data = await campaignService.get(campaignId.value);
  campaign.value = data.campaign;
  job.value = data.activeJob;
  workflow.setCampaign(campaignId.value, data.campaign.title);
}

async function loadExtras() {
  const [acc, b] = await Promise.all([
    campaignService.getAccounts(campaignId.value),
    campaignService.getBots(campaignId.value),
  ]);
  accounts.value = acc;
  bots.value = b;
}

async function fetchLogs() {
  if (!job.value?.id) return;
  logsLoading.value = true;
  try {
    const batch = await jobService.getLogs(job.value.id, lastLogId.value, {
      minLevel: uiPrefs.verboseLogs ? 'debug' : 'info',
    });
    if (batch.length) {
      logs.value = [...logs.value, ...batch];
      lastLogId.value = batch[batch.length - 1].id;
    }
  } finally {
    logsLoading.value = false;
  }
}

async function refreshJob() {
  if (!job.value?.id) return;
  job.value = await jobService.get(job.value.id);
  if (!['queued', 'running'].includes(job.value.status)) {
    stopElapsedTimer();
    await loadCampaign();
    await loadExtras();
  }
}

function startElapsedTimer() {
  stopElapsedTimer();
  if (!jobStartedAt.value) jobStartedAt.value = Date.now();
  elapsedTimer = setInterval(() => {
    if (jobStartedAt.value) {
      jobElapsedSec.value = Math.floor((Date.now() - jobStartedAt.value) / 1000);
    }
  }, 1000);
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
}

async function poll() {
  await refreshJob();
  await fetchLogs();
}

function startPolling() {
  stopPolling();
  startElapsedTimer();
  pollTimer = setInterval(poll, 2000);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function onStart() {
  starting.value = true;
  try {
    job.value = await taskStore.run('START_CAMPAIGN', async ({ logStep }) => {
      logStep('POST /start — постановка задачи в очередь', 'debug');
      const j = await campaignService.start(campaignId.value);
      logStep(`Job #${j.id} status=${j.status}`, 'info', j);
      return j;
    });
    logs.value = [];
    lastLogId.value = 0;
    jobStartedAt.value = Date.now();
    jobElapsedSec.value = 0;
    await fetchLogs();
    startPolling();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось запустить';
  } finally {
    starting.value = false;
  }
}

async function onCancelJob() {
  if (!job.value?.id || cancellingJob.value) return;
  cancellingJob.value = true;
  try {
    job.value = await jobService.cancel(job.value.id);
    await poll();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось остановить задачу';
  } finally {
    cancellingJob.value = false;
  }
}

async function onDeleteCampaign() {
  if (!confirm(`Удалить кампанию «${campaign.value.title}»?`)) return;
  try {
    await campaignService.remove(campaignId.value);
    router.push({ name: 'dashboard' });
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка удаления';
  }
}

async function onBotStart(b) {
  try {
    await botService.start(b.id);
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка запуска';
  }
}

async function onBotStop(b) {
  try {
    await botService.stop(b.id);
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка остановки';
  }
}

async function onBotDelete(b) {
  if (!confirm(`Удалить @${b.username || b.id}?`)) return;
  try {
    await taskStore.run(
      'DELETE_BOT',
      () => botService.remove(b.id),
      { username: b.username || String(b.id) }
    );
    await loadCampaign();
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка удаления';
  }
}

async function onAttachPrepared(ids) {
  if (!ids?.length) return;
  attaching.value = true;
  attachMessage.value = null;
  loadError.value = null;
  try {
    const result = await taskStore.run(
      'ATTACH_ACCOUNTS',
      async ({ logStep }) => {
        logStep(`Attach ${ids.length} prepared account(s)`, 'debug', { ids });
        const res = await campaignService.attachPreparedAccounts(campaignId.value, ids);
        logStep('Аккаунты добавлены, verify-all выполнен', 'info', res.verifySummary);
        return res;
      },
      { count: ids.length }
    );
    accounts.value = result.accounts ?? [];
    const s = result.verifySummary;
    if (s) {
      attachMessage.value = `Добавлено и проверено: ${s.verified_ok} OK, ${s.verified_failed} с ошибкой`;
    }
    await loadCampaign();
    accountsPanelRef.value?.reloadPicker?.();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка добавения аккаунтов';
  } finally {
    attaching.value = false;
  }
}

async function onVerifyAccount(account) {
  accountBusy.value = true;
  accountBusyId.value = account.id;
  loadError.value = null;
  try {
    const updated = await taskStore.run(
      'VERIFY_ACCOUNT',
      async ({ logStep }) => {
        logStep(`POST verify account #${account.id}`, 'debug');
        const res = await campaignService.verifyAccount(campaignId.value, account.id);
        logStep(res.verify_message || (res.verified ? 'Сессия OK' : 'Ошибка проверки'), res.verified ? 'info' : 'warn', {
          verified: res.verified,
          status: res.status,
          bots_created: res.bots_created,
        });
        return res;
      },
      { accountId: account.id, accountLabel: accountLabel(account) }
    );
    const idx = accounts.value.findIndex((a) => a.id === account.id);
    if (idx >= 0) accounts.value[idx] = updated;
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка проверки';
  } finally {
    accountBusy.value = false;
    accountBusyId.value = null;
  }
}

async function onVerifyAllAccounts() {
  verifyingAll.value = true;
  loadError.value = null;
  try {
    const result = await taskStore.run(
      'VERIFY_ALL_ACCOUNTS',
      async ({ logStep }) => {
        logStep(`POST verify-all (${accounts.value.length} акк.)`, 'debug');
        const res = await campaignService.verifyAllAccounts(campaignId.value);
        logStep(`Итог: ${res.verified_ok} OK, ${res.verified_failed} ошибок`, 'info', res);
        return res;
      },
      { count: accounts.value.length }
    );
    accounts.value = result.accounts ?? accounts.value;
    attachMessage.value = `Проверка: ${result.verified_ok} OK, ${result.verified_failed} ошибок`;
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Ошибка проверки';
  } finally {
    verifyingAll.value = false;
  }
}

function patchAccount(updated) {
  const idx = accounts.value.findIndex((a) => a.id === updated.id);
  if (idx >= 0) {
    accounts.value[idx] = { ...accounts.value[idx], ...updated };
  }
}

async function onLoadAccountBots(account) {
  botsBusyId.value = account.id;
  accountBotsErrors.value = { ...accountBotsErrors.value, [account.id]: null };
  try {
    const data = await taskStore.run(
      'LIST_ACCOUNT_BOTS',
      async ({ logStep }) => {
        logStep(`GET bots for account #${account.id}`, 'debug');
        const res = await campaignService.listAccountBots(campaignId.value, account.id);
        logStep(`Telegram: ${res.telegram_bots_count ?? res.bots?.length ?? 0} бот(ов)`, 'info', {
          bots_in_app: res.bots_in_app,
          bots_created: res.bots_created,
        });
        return res;
      },
      { accountId: account.id, accountLabel: accountLabel(account) }
    );
    accountBotsLists.value = { ...accountBotsLists.value, [account.id]: data.bots ?? [] };
    const idx = accounts.value.findIndex((a) => a.id === account.id);
    if (idx >= 0) {
      accounts.value[idx] = {
        ...accounts.value[idx],
        bots_created: data.bots_created,
        bots_in_telegram: data.telegram_bots_count,
        bots_in_db: data.bots_in_app,
      };
    }
  } catch (err) {
    accountBotsErrors.value = {
      ...accountBotsErrors.value,
      [account.id]: err.response?.data?.error || 'Не удалось загрузить список ботов',
    };
  } finally {
    botsBusyId.value = null;
  }
}

async function onDeleteAccountBot({ account, bot }) {
  const uname = bot.username;
  if (!confirm(`Удалить @${uname} из Telegram${bot.in_app ? ' и из списка кампании' : ''}?`)) return;
  deleteBotBusy.value = `${account.id}:${uname}`;
  loadError.value = null;
  try {
    const data = await taskStore.run(
      'DELETE_ACCOUNT_BOT',
      async () => {
        const result = await campaignService.deleteAccountBot(
          campaignId.value,
          account.id,
          uname
        );
        const listData = await campaignService.listAccountBots(campaignId.value, account.id);
        accountBotsLists.value = {
          ...accountBotsLists.value,
          [account.id]: listData.bots ?? [],
        };
        return { ...result, listData };
      },
      {
        accountId: account.id,
        accountLabel: accountLabel(account),
        username: uname,
      }
    );
    patchAccount({
      id: account.id,
      bots_created: data.bots_created,
      bots_in_telegram: data.telegram_bots_count,
      bots_in_db: data.listData?.bots_in_app,
    });
    await loadCampaign();
    await loadExtras();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Не удалось удалить бота';
  } finally {
    deleteBotBusy.value = null;
  }
}

async function onRemoveAccount(account) {
  if (!confirm(`Убрать «${account.label || account.phone || account.id}» из кампании?`)) return;
  accountBusy.value = true;
  accountBusyId.value = account.id;
  try {
    await campaignService.removeAccount(campaignId.value, account.id);
    await loadCampaign();
    await loadExtras();
    accountsPanelRef.value?.reloadPicker?.();
  } catch (err) {
    loadError.value = err.response?.data?.error || 'Не удалось убрать аккаунт';
  } finally {
    accountBusy.value = false;
    accountBusyId.value = null;
  }
}

watch(isPolling, (v) => {
  if (v) startPolling();
  else stopPolling();
});

watch(
  () => uiPrefs.verboseLogs,
  async () => {
    if (!job.value?.id) return;
    logs.value = [];
    lastLogId.value = 0;
    await fetchLogs();
  }
);

onMounted(async () => {
  try {
    await loadCampaign();
    await loadExtras();
    if (job.value?.id) {
      await fetchLogs();
      if (isPolling.value) {
        jobStartedAt.value = Date.now();
        startPolling();
      }
    }
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  } finally {
    loading.value = false;
  }
});

onUnmounted(() => {
  stopPolling();
  stopElapsedTimer();
});
</script>

<style scoped>
.detail-header {
  margin-bottom: 1.25rem;
}

.back {
  font-size: 0.875rem;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

.title-row h1 {
  margin: 0;
  font-size: 1.625rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.resource {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
}

.bot-kw {
  font-size: 0.75rem;
  color: var(--accent);
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 1.1rem 1.25rem;
}

.stat-icon {
  margin-bottom: 0.15rem;
}

.stat-icon--blue {
  color: #60a5fa;
}

.stat-icon--purple {
  color: #a78bfa;
}

.stat-icon--green {
  color: #4ade80;
}

.stat-val {
  display: block;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
}

.stat-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--muted);
}

.progress-section h2 {
  margin: 0;
  font-size: 1rem;
}

.progress-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.progress-msg {
  margin: 0 0 0.75rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.progress-bar-wrap {
  height: 6px;
  background: var(--bg);
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s;
}

.progress-section {
  margin-bottom: 1.25rem;
}

.actions {
  margin-top: 1rem;
}

.guide {
  padding: 1.25rem;
  margin-bottom: 1rem;
}

.guide h2 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}

.checklist {
  margin: 0;
  padding-left: 1.2rem;
  line-height: 1.7;
  color: var(--muted);
}

.checklist li.ok {
  color: #86efac;
}

.next-step {
  margin-bottom: 1rem;
  padding: 1rem 1.15rem;
  border: 1px solid rgba(59, 130, 246, 0.3);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.06));
  border-radius: var(--radius);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.08);
}

.next-step-label {
  margin: 0 0 0.25rem;
  font-weight: 600;
  font-size: 0.92rem;
}

.next-step-hint {
  margin: 0 0 0.65rem;
  font-size: 0.82rem;
}

.next-step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.empty-bots {
  margin: 0;
}

.create-hub {
  padding: 1.25rem;
}

.create-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

@media (max-width: 640px) {
  .create-cards {
    grid-template-columns: 1fr;
  }
}

.create-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg);
  text-decoration: none;
  color: inherit;
}

.create-card:hover {
  text-decoration: none;
  border-color: var(--accent);
}

.create-card--primary {
  border-color: rgba(59, 130, 246, 0.4);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(37, 99, 235, 0.06));
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.1);
}

.create-card--disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.bots-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.search-input {
  flex: 1;
  min-width: 12rem;
  padding: 0.45rem 0.65rem;
  font-size: 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
}

.filter-select {
  padding: 0.45rem 0.65rem;
  font-size: 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
}

.cc-title {
  font-weight: 600;
}

.cc-desc {
  font-size: 0.8rem;
  color: var(--muted);
}

.bots-list {
  padding: 1rem;
}

.bots-list .section-head {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.bots-list h2 {
  margin: 0;
  flex: 1;
  font-size: 1rem;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 800px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}

.section h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.mini-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.mini-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.875rem;
}

.mini-meta {
  width: 100%;
  font-size: 0.75rem;
  color: var(--muted);
}

.bots li {
  flex-direction: column;
  align-items: flex-start;
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

.upload-more {
  display: block;
  margin-top: 0.75rem;
  padding: 0.5rem;
  text-align: center;
  border: 1px dashed var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--muted);
}

.side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.header-btns {
  display: flex;
  gap: 0.35rem;
  margin-left: auto;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.section-head h3 {
  margin: 0;
}

.bot-li {
  flex-direction: column;
  align-items: stretch !important;
  gap: 0.35rem;
}

.bot-li-main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.tg-open {
  font-size: 0.75rem;
  color: var(--accent);
}

.clicks {
  font-size: 0.75rem;
  color: var(--muted);
}

.bot-li-actions {
  display: flex;
  gap: 0.5rem;
}


</style>
