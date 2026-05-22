<template>
  <nav class="workflow-nav" aria-label="Шаги работы">
    <RouterLink
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      class="wf-tab"
      :class="{ 'wf-tab--disabled': item.disabled }"
      @click="onTabClick(item, $event)"
    >
      <span class="wf-num">{{ item.step }}</span>
      <span class="wf-label">{{ item.label }}</span>
      <span v-if="item.hint" class="wf-hint">{{ item.hint }}</span>
    </RouterLink>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useWorkflowStore } from '../stores/workflowStore';

const route = useRoute();
const workflow = useWorkflowStore();

const items = computed(() => {
  const cid = workflow.activeCampaignId;
  const campaignTo = cid
    ? { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'guide' } }
    : { name: 'dashboard' };

  return [
    {
      step: '1',
      label: 'Кампания',
      hint: 'Создать группу',
      to: { name: 'dashboard' },
      disabled: false,
    },
    {
      step: '2',
      label: 'Аккаунты',
      hint: 'Подготовка',
      to: { name: 'account-prep' },
      disabled: false,
    },
    {
      step: '3',
      label: 'В кампании',
      hint: cid ? workflow.activeCampaignTitle || `#${cid}` : 'выберите кампанию',
      to: { ...campaignTo, query: { tab: 'accounts' } },
      disabled: !cid,
    },
    {
      step: '4',
      label: 'Боты',
      hint: 'Создание',
      to: cid
        ? { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'create' } }
        : { name: 'dashboard' },
      disabled: !cid,
    },
  ];
});

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
