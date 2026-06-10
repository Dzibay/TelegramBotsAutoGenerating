<template>
  <nav v-if="crumbs.length" class="breadcrumb" aria-label="Навигация">
    <template v-for="(c, i) in crumbs" :key="i">
      <span v-if="i > 0" class="sep">/</span>
      <RouterLink v-if="c.to" :to="c.to" class="crumb">{{ c.label }}</RouterLink>
      <span v-else class="crumb crumb--current">{{ c.label }}</span>
    </template>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useWorkflowStore } from '../stores/workflowStore';

const route = useRoute();
const workflow = useWorkflowStore();

const crumbs = computed(() => {
  const cid = workflow.activeCampaignId;
  const ctitle = workflow.activeCampaignTitle || (cid ? `Кампания #${cid}` : null);
  const base = cid
    ? [{ label: ctitle, to: { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'guide' } } }]
    : [{ label: 'Кампании', to: { name: 'dashboard' } }];

  const map = {
    'campaign-bot-create': [
      ...base,
      { label: 'Создание', to: { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'create' } } },
      { label: 'Один бот' },
    ],
    'bulk-bot-create': [
      ...base,
      { label: 'Создание', to: { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'create' } } },
      { label: 'Несколько ботов' },
    ],
    'bot-edit': [...base, { label: 'Редактирование бота' }],
    'campaign-edit': [...base, { label: 'Настройки' }],
    'campaign-create': [{ label: 'Кампании', to: { name: 'dashboard' } }, { label: 'Новая кампания' }],
    'account-prep': [{ label: 'Аккаунты' }],
  };

  return map[route.name] || [];
});
</script>

<style scoped>
.breadcrumb {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 1.25rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  background: rgba(8, 12, 20, 0.35);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.sep {
  color: var(--muted);
  opacity: 0.5;
}

.crumb {
  color: var(--muted);
  text-decoration: none;
  transition: color 0.15s;
}

.crumb:hover {
  color: var(--accent);
  text-decoration: none;
}

.crumb--current {
  color: var(--text);
  font-weight: 600;
}
</style>
