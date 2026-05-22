<template>
  <div>
    <OnboardingModal :open="showOnboarding" @dismiss="showOnboarding = false" />
    <header class="dash-header">
      <div>
        <h1>Шаг 1 — Кампания</h1>
        <p class="subtitle">Создайте группу для аккаунтов и ботов. Ключевая фраза нужна только при генерации текстов AI.</p>
      </div>
      <RouterLink to="/app/campaigns/new" class="btn">+ Новая кампания</RouterLink>
    </header>

    <ol class="steps-guide card">
      <li :class="{ done: campaigns.length }">
        <strong>Кампания</strong> — название и ссылка на ваш сервис
      </li>
      <li>
        <strong>Аккаунты</strong> —
        <RouterLink to="/app/accounts/prepare">подготовьте Telegram</RouterLink>
        и добавьте в кампанию
      </li>
      <li>
        <strong>Боты</strong> — по одному или таблицей; фраза только если нужен AI
      </li>
    </ol>

    <p v-if="createBotHint" class="warn-banner card">{{ createBotHint }}</p>
    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <p v-else-if="loading" class="muted">Загрузка…</p>
    <div v-else-if="!campaigns.length" class="card empty-onboarding">
      <p><strong>Начните с кампании</strong></p>
      <p class="muted">Группа для аккаунтов и ботов. Дальше — подготовка Telegram и создание ботов.</p>
      <div class="empty-actions">
        <RouterLink to="/app/campaigns/new" class="btn">Создать кампанию</RouterLink>
        <RouterLink to="/app/accounts/prepare" class="btn btn-ghost">Подготовить аккаунты</RouterLink>
      </div>
    </div>

    <ul v-else class="list">
      <li v-for="c in campaigns" :key="c.id" class="card item">
        <button type="button" class="item-link" @click="openCampaign(c)">
          <div class="item-main">
            <div class="item-title">
              <strong>{{ c.title }}</strong>
              <StatusBadge :status="c.status" />
            </div>
            <p class="meta">
              {{ c.bots_count }} ботов · {{ c.accounts_count }} аккаунтов
            </p>
          </div>
          <span class="chevron">→</span>
        </button>
        <div class="item-actions">
          <button type="button" class="btn-ghost btn-xs" @click="openCampaign(c)">Открыть</button>
          <RouterLink :to="{ name: 'campaign-edit', params: { id: c.id } }" class="btn-ghost btn-xs">
            Настройки
          </RouterLink>
          <button type="button" class="btn-ghost btn-xs danger" @click="onDelete(c)">Удалить</button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import OnboardingModal from '../components/OnboardingModal.vue';
import StatusBadge from '../components/StatusBadge.vue';
import { campaignService } from '../services/campaignService';
import { useWorkflowStore } from '../stores/workflowStore';
import { shouldShowOnboarding } from '../utils/onboarding';

const route = useRoute();
const router = useRouter();
const workflow = useWorkflowStore();
const campaigns = ref([]);
const createBotHint = ref(null);
const showOnboarding = ref(false);
const loading = ref(true);
const loadError = ref(null);

function openCampaign(c) {
  workflow.setCampaign(c.id, c.title);
  router.push({ name: 'campaign-workspace', params: { id: c.id }, query: { tab: 'guide' } });
}

async function onDelete(c) {
  if (!confirm(`Удалить кампанию «${c.title}»?`)) return;
  try {
    await campaignService.remove(c.id);
    if (workflow.activeCampaignId === c.id) workflow.setCampaign(null);
    await load();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Ошибка удаления';
  }
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    campaigns.value = await campaignService.list();
  } catch (e) {
    loadError.value = e.response?.data?.error || 'Не удалось загрузить кампании';
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  showOnboarding.value = shouldShowOnboarding();
  await load();
  if (route.query.open === 'create_bot') {
    if (workflow.activeCampaignId) {
      router.replace({
        name: 'campaign-bot-create',
        params: { id: workflow.activeCampaignId },
      });
    } else {
      createBotHint.value =
        'Чтобы создать бота, сначала откройте кампанию из списка ниже или создайте новую.';
    }
  }
});
</script>

<style scoped>
.dash-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.dash-header h1 {
  margin: 0;
  font-size: 1.35rem;
}

.subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
  max-width: 32rem;
}

.steps-guide {
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  font-size: 0.88rem;
  color: var(--muted);
  line-height: 1.6;
}

.steps-guide li {
  margin: 0.35rem 0;
}

.steps-guide li.done {
  color: #86efac;
}

.empty-onboarding {
  text-align: center;
  padding: 2rem;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 1rem;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.item {
  padding: 0;
  overflow: hidden;
}

.item-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 1rem;
  border: none;
  background: transparent;
  text-align: left;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.item-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0 1rem 0.75rem;
  border-top: 1px solid var(--border);
  padding-top: 0.5rem;
}

.item-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.meta {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.chevron {
  color: var(--muted);
  font-size: 1.25rem;
}

.warn-banner {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  font-size: 0.9rem;
  color: #fcd34d;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.35);
}
</style>
