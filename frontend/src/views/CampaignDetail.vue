<template>
  <div v-if="loading" class="muted">Загрузка кампании…</div>
  <div v-else-if="loadError" class="error-text">{{ loadError }}</div>

  <div v-else class="detail">
    <header class="detail-header">
      <RouterLink to="/app" class="back">← Все кампании</RouterLink>
      <div class="title-row">
        <div class="title-main">
          <h1>{{ campaign.title }}</h1>
          <StatusBadge :status="campaign.status" />
        </div>
        <div class="header-btns">
          <RouterLink
            :to="{ name: 'campaign-job-history', params: { id: campaignId } }"
            class="btn-ghost btn-sm"
          >
            История задач
          </RouterLink>
          <RouterLink :to="{ name: 'campaign-edit', params: { id: campaignId } }" class="btn-ghost btn-sm">
            <Settings :size="14" />
            Настройки
          </RouterLink>
          <RouterLink
            v-if="canOpenCreate"
            :to="{ name: 'bulk-bot-create', params: { id: campaignId } }"
            class="btn btn-sm"
          >
            <Rocket :size="14" />
            Создать ботов
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

    <WizardSteps
      class="campaign-stepper"
      :steps="workflowSteps"
      :current="workflowCurrentStep"
      aria-label="Прогресс кампании"
    />

    <WorkspaceTabs v-model="activeTab" :tabs="workspaceTabs" />

    <CampaignActiveJobsPanel
      v-if="campaignId"
      ref="activeJobsPanelRef"
      :campaign-id="campaignId"
      :bulk-link="bulkCreateLink"
      @update:jobs="onActiveJobsUpdate"
    />

    <section v-show="activeTab === 'guide'" class="guide-grid">
      <div v-if="nextStepGuide" class="guide-cta card">
        <h2>{{ nextStepGuide.title }}</h2>
        <p v-if="nextStepGuide.hint" class="guide-cta-hint muted">{{ nextStepGuide.hint }}</p>
        <ul class="guide-checks">
          <li :class="{ ok: hasServiceUrl }">
            <Check :size="14" />
            Ссылка на сервис {{ hasServiceUrl ? 'указана' : 'не указана' }}
          </li>
          <li :class="{ ok: campaign.accounts_count > 0 }">
            <Check :size="14" />
            {{ campaign.accounts_count || 0 }} аккаунтов в кампании
          </li>
          <li :class="{ ok: readyAccountsCount > 0 }">
            <Check :size="14" />
            {{ readyAccountsCount }} готовы к созданию ботов
          </li>
        </ul>
        <div class="guide-cta-actions">
          <RouterLink
            v-if="nextStepGuide.route"
            :to="nextStepGuide.route"
            class="btn"
          >
            {{ nextStepGuide.actionLabel }}
          </RouterLink>
          <button
            v-else-if="nextStepGuide.action"
            type="button"
            class="btn"
            @click="nextStepGuide.action()"
          >
            {{ nextStepGuide.actionLabel }}
          </button>
          <button
            v-if="canStart && nextStepGuide.showAutoStart"
            type="button"
            class="btn btn-ghost"
            :disabled="starting"
            @click="onStart"
          >
            {{ starting ? 'Запуск…' : 'Авто-создание по ключевым словам' }}
          </button>
        </div>
      </div>

      <div class="guide-next card">
        <h3>Что дальше</h3>
        <ol class="next-steps-list">
          <li :class="{ done: hasServiceUrl }">
            <span class="step-num">1</span>
            <div>
              <strong>Сервис</strong>
              <p>Укажите ссылку, куда будут вести боты</p>
            </div>
          </li>
          <li :class="{ done: campaign.accounts_count > 0 }">
            <span class="step-num">2</span>
            <div>
              <strong>Аккаунты</strong>
              <p>Добавьте подготовленные Telegram-аккаунты</p>
            </div>
          </li>
          <li :class="{ done: readyAccountsCount > 0 }">
            <span class="step-num">3</span>
            <div>
              <strong>Проверка</strong>
              <p>Убедитесь, что аккаунты в статусе «Готов»</p>
            </div>
          </li>
          <li :class="{ done: campaign.bots_count > 0 }">
            <span class="step-num">4</span>
            <div>
              <strong>Создание</strong>
              <p>Один бот или массовая очередь</p>
            </div>
          </li>
        </ol>
      </div>
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
          <Bot :size="22" class="cc-icon" />
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
          <Users :size="22" class="cc-icon cc-icon--purple" />
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
      <div class="bots-list-head">
        <div>
          <h2>Боты кампании</h2>
          <p class="bots-list-meta muted">{{ bots.length }} всего · {{ campaign.active_bots_count }} активных</p>
        </div>
        <div class="bots-list-actions">
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
      </div>

      <div v-if="bots.length" class="bots-filters">
        <div class="search-wrap">
          <Search :size="15" class="search-icon" />
          <input
            v-model="botSearch"
            type="search"
            class="search-input"
            placeholder="Поиск по имени, @username, фразе…"
          />
        </div>
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

      <div v-else class="bots-table-wrap">
        <table class="bots-table">
          <thead>
            <tr>
              <th>Бот</th>
              <th>Статус</th>
              <th>Аккаунт</th>
              <th>Создан</th>
              <th>Активность</th>
              <th class="th-actions" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in filteredBots" :key="b.id">
              <td>
                <div class="bot-cell">
                  <div class="bot-avatar" :class="avatarColorClass(b)">
                    <BotAvatar :bot="b" :size="36" :cache-key="b.updated_at || ''" />
                  </div>
                  <div class="bot-info">
                    <span class="bot-name">{{ b.display_name || 'Без имени' }}</span>
                    <a
                      v-if="b.username && botLink(b)"
                      :href="botLink(b)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="bot-handle"
                    >
                      @{{ b.username }}
                    </a>
                    <span v-else class="bot-handle muted">@—</span>
                    <span v-if="b.keyword" class="bot-kw">«{{ b.keyword }}»</span>
                  </div>
                </div>
              </td>
              <td>
                <StatusBadge :status="b.status" />
              </td>
              <td class="account-cell">
                <span class="account-name">{{ b.account_label || accountLabelById(b.telegram_account_id) }}</span>
                <span v-if="b.account_phone" class="account-phone">{{ b.account_phone }}</span>
              </td>
              <td class="date-cell">{{ formatDateTime(b.created_at) }}</td>
              <td class="activity-cell">
                <span class="activity-cell-content">
                  <span class="activity-dot" :class="`activity-dot--${b.status}`" />
                  {{ formatRelativeTime(b.updated_at) }}
                </span>
              </td>
              <td class="actions-cell">
                <details class="row-menu">
                  <summary class="menu-trigger" aria-label="Действия">
                    <MoreVertical :size="16" />
                  </summary>
                  <div class="menu-dropdown">
                    <a
                      v-if="botLink(b)"
                      :href="botLink(b)"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="menu-item"
                    >
                      Открыть в Telegram
                    </a>
                    <button
                      v-if="b.status !== 'active'"
                      type="button"
                      class="menu-item"
                      @click="onBotStart(b)"
                    >
                      Запустить
                    </button>
                    <button v-else type="button" class="menu-item" @click="onBotStop(b)">Остановить</button>
                    <RouterLink :to="{ name: 'bot-edit', params: { id: b.id } }" class="menu-item">
                      Изменить
                    </RouterLink>
                    <button type="button" class="menu-item menu-item--danger" @click="onBotDelete(b)">
                      Удалить
                    </button>
                  </div>
                </details>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { Bot, Check, MoreVertical, Rocket, Search, Settings, Users, Zap } from 'lucide-vue-next';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import BotAvatar from '../components/BotAvatar.vue';
import CampaignAccountsPanel from '../components/CampaignAccountsPanel.vue';
import CampaignActiveJobsPanel from '../components/CampaignActiveJobsPanel.vue';
import EmptyState from '../components/EmptyState.vue';
import StatusBadge from '../components/StatusBadge.vue';
import WizardSteps from '../components/WizardSteps.vue';
import WorkspaceTabs from '../components/WorkspaceTabs.vue';
import { formatDateTime, formatRelativeTime } from '../utils/formatDate';
import { useWorkflowStore } from '../stores/workflowStore';
import { botService } from '../services/botService';
import { campaignService } from '../services/campaignService';
import { useAsyncTaskStore } from '../stores/asyncTaskStore';
import { telegramBotUrl } from '../utils/botLink';

const taskStore = useAsyncTaskStore();

function accountLabel(account) {
  return account?.label || account?.phone || `Аккаунт #${account?.id}`;
}

function botLink(b) {
  return b.telegram_url || telegramBotUrl(b.username);
}

function avatarColorClass(b) {
  const colors = ['green', 'purple', 'blue', 'orange'];
  return `bot-avatar--${colors[(b.id || 0) % colors.length]}`;
}

function accountLabelById(id) {
  if (!id) return '—';
  const acc = accounts.value.find((a) => a.id === id);
  return acc ? accountLabel(acc) : `Аккаунт #${id}`;
}

const workflowSteps = [
  { label: 'Сервис' },
  { label: 'Аккаунты' },
  { label: 'Проверка' },
  { label: 'Создание' },
  { label: 'Запуск' },
];

const workflowCurrentStep = computed(() => {
  if (!hasServiceUrl.value) return 1;
  if (!campaign.value.accounts_count) return 2;
  if (!readyAccountsCount.value) return 3;
  if (!campaign.value.bots_count) return 4;
  if (!campaign.value.active_bots_count) return 5;
  return 5;
});

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
const activeJobs = ref([]);
const activeJobsPanelRef = ref(null);
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
const starting = ref(false);

const hasActiveJobs = computed(() =>
  activeJobs.value.some((j) => ['queued', 'running'].includes(j.status))
);

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

const isPolling = computed(() => hasActiveJobs.value);

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
    !hasActiveJobs.value &&
    ['draft', 'failed', 'completed', 'cancelled'].includes(campaign.value.status)
);

const canAddAccounts = computed(
  () => !activeJobs.value.some(
    (j) => j.job_mode === 'auto' && ['queued', 'running'].includes(j.status)
  )
);

function onActiveJobsUpdate(jobs) {
  activeJobs.value = jobs;
}

async function loadCampaign() {
  const data = await campaignService.get(campaignId.value);
  campaign.value = data.campaign;
  activeJobs.value = data.activeJobs?.length
    ? data.activeJobs
    : data.activeJob
      ? [data.activeJob]
      : [];
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

async function onStart() {
  starting.value = true;
  try {
    await taskStore.run('START_CAMPAIGN', async ({ logStep }) => {
      logStep('POST /start — постановка задачи в очередь', 'debug');
      const j = await campaignService.start(campaignId.value);
      logStep(`Job #${j.id} status=${j.status}`, 'info', j);
      return j;
    });
    await loadCampaign();
    await activeJobsPanelRef.value?.loadJobs?.();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось запустить';
  } finally {
    starting.value = false;
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

onMounted(async () => {
  try {
    await loadCampaign();
    await loadExtras();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Кампания не найдена';
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.detail-header {
  margin-bottom: 1rem;
}

.title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
}

.title-main {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.resource {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
}

.header-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.campaign-stepper {
  margin-bottom: 1.25rem;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

@media (max-width: 640px) {
  .stats {
    grid-template-columns: 1fr;
  }
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 1.1rem 1.25rem;
}

.stat-icon--blue { color: #60a5fa; }
.stat-icon--purple { color: #a78bfa; }
.stat-icon--green { color: #4ade80; }

.stat-val {
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

/* Guide tab */
.guide-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

@media (max-width: 800px) {
  .guide-grid {
    grid-template-columns: 1fr;
  }
}

.guide-cta {
  padding: 1.35rem;
  border-color: rgba(34, 197, 94, 0.2);
}

.guide-cta h2 {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.guide-cta-hint {
  margin: 0 0 1rem;
  font-size: 0.875rem;
  line-height: 1.5;
}

.guide-checks {
  list-style: none;
  margin: 0 0 1.15rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.guide-checks li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--muted);
}

.guide-checks li svg {
  flex-shrink: 0;
  opacity: 0.35;
}

.guide-checks li.ok {
  color: #4ade80;
}

.guide-checks li.ok svg {
  opacity: 1;
}

.guide-cta-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.guide-next {
  padding: 1.25rem;
}

.guide-next h3 {
  margin: 0 0 1rem;
  font-size: 0.95rem;
  font-weight: 600;
}

.next-steps-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.next-steps-list li {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.next-steps-list li.done .step-num {
  background: var(--success-soft);
  border-color: rgba(34, 197, 94, 0.35);
  color: #4ade80;
}

.next-steps-list li.done strong {
  color: var(--text);
}

.step-num {
  flex-shrink: 0;
  width: 1.5rem;
  height: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.72rem;
  font-weight: 700;
  border: 1px solid var(--border-strong);
  background: rgba(8, 12, 20, 0.5);
  color: var(--muted);
}

.next-steps-list strong {
  display: block;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 0.15rem;
}

.next-steps-list p {
  margin: 0;
  font-size: 0.78rem;
  color: var(--muted);
  line-height: 1.4;
}

/* Create tab */
.create-hub {
  padding: 1.35rem;
  margin-bottom: 1.25rem;
}

.create-hub h2 {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
}

.intro {
  margin: 0 0 1rem;
  font-size: 0.875rem;
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
  gap: 0.4rem;
  padding: 1.2rem;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: rgba(8, 12, 20, 0.45);
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, transform 0.15s;
}

.create-card:hover {
  text-decoration: none;
  border-color: rgba(59, 130, 246, 0.35);
  transform: translateY(-1px);
}

.create-card--primary {
  border-color: rgba(59, 130, 246, 0.3);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(37, 99, 235, 0.05));
}

.create-card--disabled {
  opacity: 0.5;
  pointer-events: none;
}

.cc-icon {
  color: #60a5fa;
}

.cc-icon--purple {
  color: #a78bfa;
}

.cc-title {
  font-weight: 600;
  font-size: 0.95rem;
}

.cc-desc {
  font-size: 0.8rem;
  color: var(--muted);
  line-height: 1.45;
}

/* Bots list */
.bots-list {
  padding: 1.25rem;
}

.bots-list-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.bots-list h2 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.bots-list-meta {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
}

.bots-list-actions {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}

.bots-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.search-wrap {
  position: relative;
  flex: 1;
  min-width: 12rem;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.55rem 0.75rem 0.55rem 2.25rem;
  font-size: 0.85rem;
}

.filter-select {
  padding: 0.55rem 0.75rem;
  font-size: 0.85rem;
  width: auto;
  min-width: 10rem;
}

.empty-bots {
  margin: 0;
}

.bots-table-wrap {
  overflow-x: auto;
  margin: 0 -0.25rem;
}

.bots-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.bots-table th {
  text-align: left;
  padding: 0.55rem 0.75rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
}

.th-actions {
  width: 2.5rem;
}

.bots-table td {
  padding: 0.75rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

.bots-table tbody tr {
  transition: background 0.12s;
}

.bots-table tbody tr:hover {
  background: rgba(59, 130, 246, 0.04);
}

.bots-table tbody tr:last-child td {
  border-bottom: none;
}

.bot-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 12rem;
}

.bot-avatar {
  flex-shrink: 0;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid var(--border);
}

.bot-avatar :deep(.bot-avatar-image) {
  width: 100%;
  height: 100%;
  border: none;
}

.bot-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bot-avatar--green { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.bot-avatar--purple { background: rgba(139, 92, 246, 0.15); color: #a78bfa; }
.bot-avatar--blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.bot-avatar--orange { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }

.bot-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.bot-name {
  font-weight: 600;
  font-size: 0.875rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bot-handle {
  font-size: 0.78rem;
  color: var(--muted);
  text-decoration: none;
}

a.bot-handle:hover {
  color: var(--accent);
  text-decoration: none;
}

.bot-kw {
  font-size: 0.72rem;
  color: var(--accent);
}

.account-cell {
  min-width: 8rem;
}

.account-name {
  display: block;
  font-size: 0.85rem;
}

.account-phone {
  display: block;
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.1rem;
}

.date-cell,
.activity-cell {
  white-space: nowrap;
  color: var(--muted);
  font-size: 0.8rem;
}

.activity-cell-content {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.activity-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--muted);
}

.activity-dot--active { background: #4ade80; }
.activity-dot--creating,
.activity-dot--running { background: #fbbf24; }
.activity-dot--error,
.activity-dot--failed { background: #f87171; }

.actions-cell {
  text-align: right;
}

.row-menu {
  position: relative;
  display: inline-block;
}

.menu-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  list-style: none;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.menu-trigger::-webkit-details-marker {
  display: none;
}

.menu-trigger:hover,
.row-menu[open] .menu-trigger {
  background: var(--surface-hover);
  border-color: var(--border);
  color: var(--text);
}

.menu-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 30;
  min-width: 10.5rem;
  padding: 0.3rem;
  background: var(--surface-solid);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
}

.menu-item {
  display: block;
  width: 100%;
  padding: 0.5rem 0.7rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 0.8125rem;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
  transition: background 0.12s;
}

.menu-item:hover {
  background: var(--surface-hover);
  text-decoration: none;
}

.menu-item--danger {
  color: #f87171;
}

.menu-item--danger:hover {
  background: rgba(239, 68, 68, 0.12);
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
