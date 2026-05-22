<template>
  <nav class="main-nav" aria-label="Разделы приложения">
    <RouterLink
      v-for="item in items"
      :key="item.key"
      :to="item.to"
      class="nav-item"
      :class="{
        'router-link-active': isActive(item),
        'nav-item--disabled': item.disabled,
      }"
      :title="item.disabled ? item.disabledTitle : undefined"
      :aria-disabled="item.disabled ? 'true' : undefined"
      @click="onClick(item, $event)"
    >
      <span class="nav-icon" aria-hidden="true">{{ item.icon }}</span>
      <span class="nav-label">{{ item.label }}</span>
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
  const botsTo = cid
    ? { name: 'campaign-workspace', params: { id: cid }, query: { tab: 'create' } }
    : { name: 'dashboard', query: { hint: 'select_campaign' } };

  return [
    {
      key: 'campaigns',
      label: 'Кампании',
      icon: '◆',
      to: { name: 'dashboard' },
      disabled: false,
    },
    {
      key: 'accounts',
      label: 'Аккаунты',
      icon: '◎',
      to: { name: 'account-prep' },
      disabled: false,
    },
    {
      key: 'bots',
      label: 'Боты',
      icon: '◇',
      to: botsTo,
      disabled: !cid,
      disabledTitle: 'Сначала откройте кампанию в разделе «Кампании»',
    },
  ];
});

function isActive(item) {
  const name = route.name;
  if (item.key === 'campaigns') {
    return ['dashboard', 'campaign-create', 'campaign-workspace', 'campaign-edit'].includes(name);
  }
  if (item.key === 'accounts') {
    return name === 'account-prep';
  }
  if (item.key === 'bots') {
    if (['bulk-bot-create', 'campaign-bot-create', 'bot-edit'].includes(name)) return true;
    return name === 'campaign-workspace' && ['create', 'list'].includes(route.query.tab);
  }
  return false;
}

function onClick(item, event) {
  if (item.disabled) {
    event.preventDefault();
  }
}
</script>

<style scoped>
.main-nav {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.nav-item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.9rem;
  border-radius: 9px;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  transition:
    color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
}

.nav-item:hover {
  color: var(--text);
  text-decoration: none;
  background: var(--surface-hover);
}

.nav-item.router-link-active {
  color: #fff;
  background: var(--accent);
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.35);
}

.nav-item.router-link-active .nav-icon {
  opacity: 1;
}

.nav-item--disabled {
  opacity: 0.4;
  pointer-events: none;
  cursor: not-allowed;
}

.nav-icon {
  font-size: 0.65rem;
  opacity: 0.7;
  line-height: 1;
}

.nav-label {
  line-height: 1.2;
}

@media (max-width: 640px) {
  .nav-label {
    font-size: 0.8rem;
  }

  .nav-item {
    padding: 0.4rem 0.65rem;
  }

  .nav-icon {
    display: none;
  }
}
</style>
