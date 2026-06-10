<template>
  <div>
    <OnboardingModal :open="showOnboarding" @dismiss="showOnboarding = false" />
    <header class="dash-header">
      <div>
        <h1>Кампании</h1>
        <p class="subtitle">Создайте группу для аккаунтов и ботов. Ключевая фраза нужна только при генерации текстов AI.</p>
      </div>
      <RouterLink to="/app/campaigns/new" class="btn">
        <Plus :size="16" />
        Новая кампания
      </RouterLink>
    </header>

    <ol class="steps-guide card">
      <li :class="{ done: campaigns.length }">
        <span class="step-num">1</span>
        <span><strong>Кампания</strong> — название и ссылка на ваш сервис</span>
      </li>
      <li>
        <span class="step-num">2</span>
        <span>
          <strong>Аккаунты</strong> —
          <RouterLink to="/app/accounts/prepare">подготовьте Telegram</RouterLink>
          и добавьте в кампанию
        </span>
      </li>
      <li>
        <span class="step-num">3</span>
        <span><strong>Боты</strong> — по одному или таблицей; фраза только если нужен AI</span>
      </li>
    </ol>

    <p v-if="route.query.hint === 'select_campaign'" class="warn-banner card">
      Откройте кампанию из списка ниже — затем в меню станет доступен раздел «Боты».
    </p>
    <p v-else-if="createBotHint" class="warn-banner card">{{ createBotHint }}</p>
    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <p v-else-if="loading" class="muted">Загрузка…</p>

    <div v-else-if="!campaigns.length" class="card empty-onboarding">
      <div class="empty-icon-wrap">
        <Megaphone :size="32" />
      </div>
      <p><strong>Начните с кампании</strong></p>
      <p class="muted">Группа для аккаунтов и ботов. Дальше — подготовка Telegram и создание ботов.</p>
      <div class="empty-actions">
        <RouterLink to="/app/campaigns/new" class="btn">Создать кампанию</RouterLink>
        <RouterLink to="/app/accounts/prepare" class="btn btn-ghost">Подготовить аккаунты</RouterLink>
      </div>
    </div>

    <ul v-else class="list campaign-grid">
      <li v-for="c in campaigns" :key="c.id" class="card campaign-card">
        <button type="button" class="item-link" @click="openCampaign(c)">
          <div class="item-main">
            <div class="item-title">
              <strong>{{ c.title }}</strong>
              <StatusBadge :status="c.status" />
            </div>
            <div class="meta-row">
              <span class="meta-item">
                <Bot :size="13" />
                {{ c.bots_count }} ботов
              </span>
              <span class="meta-item">
                <Users :size="13" />
                {{ c.accounts_count }} аккаунтов
              </span>
            </div>
          </div>
          <ChevronRight :size="18" class="chevron" />
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
import { Bot, ChevronRight, Megaphone, Plus, Users } from 'lucide-vue-next';
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
  margin-bottom: 1.25rem;
}

.dash-header h1 {
  margin: 0;
  font-size: 1.625rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.subtitle {
  margin: 0.35rem 0 0;
  font-size: 0.875rem;
  color: var(--muted);
  max-width: 32rem;
  line-height: 1.5;
}

.steps-guide {
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.steps-guide li {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  font-size: 0.875rem;
  color: var(--muted);
  line-height: 1.5;
}

.steps-guide li.done {
  color: #4ade80;
}

.steps-guide li.done .step-num {
  background: var(--success-soft);
  border-color: rgba(34, 197, 94, 0.35);
  color: #4ade80;
}

.step-num {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 700;
  border: 1px solid var(--border-strong);
  background: rgba(8, 12, 20, 0.5);
  color: var(--muted);
}

.empty-onboarding {
  text-align: center;
  padding: 2.5rem 2rem;
}

.empty-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3.5rem;
  height: 3.5rem;
  margin-bottom: 0.75rem;
  border-radius: var(--radius);
  background: var(--accent-soft);
  color: var(--accent);
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 1rem;
}

.campaign-grid {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.campaign-card {
  padding: 0;
  overflow: hidden;
  transition: border-color 0.18s, box-shadow 0.18s;
}

.campaign-card:hover {
  border-color: rgba(59, 130, 246, 0.3);
}

.item-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 1.1rem 1.25rem;
  border: none;
  background: transparent;
  text-align: left;
  color: inherit;
  font: inherit;
  cursor: pointer;
  transition: background 0.15s;
}

.item-link:hover {
  background: var(--surface-hover);
}

.item-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0.6rem 1.25rem 0.85rem;
  border-top: 1px solid var(--border);
}

.item-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.item-title strong {
  font-size: 0.95rem;
  font-weight: 600;
}

.meta-row {
  display: flex;
  gap: 1rem;
  margin-top: 0.4rem;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.78rem;
  color: var(--muted);
}

.chevron {
  flex-shrink: 0;
  color: var(--muted);
  opacity: 0.6;
  transition: opacity 0.15s, transform 0.15s;
}

.campaign-card:hover .chevron {
  opacity: 1;
  transform: translateX(2px);
  color: var(--accent);
}

.warn-banner {
  margin-bottom: 1rem;
}
</style>
