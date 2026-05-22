<template>
  <nav class="workflow-nav" aria-label="Шаги работы">
    <RouterLink
      v-for="item in items"
      :key="item.key"
      :to="item.to"
      class="wf-tab"
      :class="{
        'wf-tab--disabled': item.disabled,
        'router-link-active': isItemActive(item),
        'wf-tab--done': item.done,
      }"
      @click="onTabClick(item, $event)"
    >
      <span class="wf-num">{{ item.done ? '✓' : item.step }}</span>
      <span class="wf-label">{{ item.label }}</span>
      <span v-if="item.hint" class="wf-hint">{{ item.hint }}</span>
    </RouterLink>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useWorkflowProgress } from '../composables/useWorkflowProgress';
import { useWorkflowStore } from '../stores/workflowStore';

const route = useRoute();
const workflow = useWorkflowStore();
const { hasCampaigns, hasPrepared, campaignAccounts, campaignBots } = useWorkflowProgress();

const items = computed(() => {
  const cid = workflow.activeCampaignId;
  const campaignTo = cid
    ? { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'guide' } }
    : { name: 'dashboard' };

  const step4Hint = cid
    ? route.name === 'campaign-workspace' && route.query.tab === 'list'
      ? 'список'
      : 'создание · список'
    : 'выберите кампанию';

  return [
    {
      key: 'campaign',
      step: '1',
      label: 'Кампания',
      hint: hasCampaigns.value ? 'есть кампании' : 'создать группу',
      to: { name: 'dashboard' },
      disabled: false,
      done: hasCampaigns.value || !!cid,
    },
    {
      key: 'prep',
      step: '2',
      label: 'Аккаунты',
      hint: hasPrepared.value ? 'готовы к добавлению' : 'подготовка',
      to: { name: 'account-prep' },
      disabled: false,
      done: hasPrepared.value,
    },
    {
      key: 'in-campaign',
      step: '3',
      label: 'В кампании',
      hint: cid ? workflow.activeCampaignTitle || `#${cid}` : 'выберите кампанию',
      to: { ...campaignTo, query: { tab: 'accounts' } },
      disabled: !cid,
      done: campaignAccounts.value > 0,
    },
    {
      key: 'bots',
      step: '4',
      label: 'Боты',
      hint: step4Hint,
      to: cid
        ? {
            name: 'campaign-workspace',
            params: { id: cid },
            query: { tab: route.query.tab === 'list' ? 'list' : 'create' },
          }
        : { name: 'dashboard' },
      disabled: !cid,
      done: campaignBots.value > 0,
    },
  ];
});

function isItemActive(item) {
  if (item.key === 'campaign') {
    return route.name === 'dashboard' || route.name === 'campaign-create';
  }
  if (item.key === 'prep') {
    return route.name === 'account-prep';
  }
  if (item.key === 'in-campaign') {
    return (
      route.name === 'campaign-workspace' &&
      (!route.query.tab || route.query.tab === 'accounts' || route.query.tab === 'guide')
    );
  }
  if (item.key === 'bots') {
    if (route.name === 'bulk-bot-create' || route.name === 'campaign-bot-create') return true;
    if (route.name === 'bot-edit') return true;
    return route.name === 'campaign-workspace' && ['create', 'list'].includes(route.query.tab);
  }
  return false;
}

function onTabClick(item, event) {
  if (item.disabled) {
    event.preventDefault();
  }
}
</script>

<style scoped>
.workflow-nav {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
  margin-bottom: 1.25rem;
}

@media (max-width: 800px) {
  .workflow-nav {
    grid-template-columns: repeat(2, 1fr);
  }
}

.wf-tab {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.75rem 0.85rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  text-decoration: none;
  color: var(--text);
  transition:
    border-color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
}

.wf-tab:hover {
  text-decoration: none;
  border-color: rgba(59, 130, 246, 0.45);
  background: var(--surface-hover);
}

.wf-tab.router-link-active {
  border-color: var(--accent);
  background: rgba(59, 130, 246, 0.12);
  box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.25);
}

.wf-tab--done:not(.router-link-active) {
  border-color: rgba(34, 197, 94, 0.35);
}

.wf-tab--done .wf-num {
  color: #4ade80;
}

.wf-tab--disabled {
  opacity: 0.45;
  pointer-events: none;
}

.wf-num {
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 0.04em;
}

.wf-label {
  font-size: 0.9rem;
  font-weight: 600;
}

.wf-hint {
  font-size: 0.72rem;
  color: var(--muted);
  line-height: 1.3;
}
</style>
