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
      :title="item.disabled ? item.disabledTitle : item.label"
      :aria-disabled="item.disabled ? 'true' : undefined"
      @click="onClick(item, $event)"
    >
      <component :is="item.icon" :size="18" class="nav-icon" aria-hidden="true" />
      <span class="nav-label">{{ item.label }}</span>
      <span v-if="isActive(item)" class="nav-indicator" aria-hidden="true" />
    </RouterLink>
  </nav>
</template>

<script setup>
import { computed } from 'vue';
import { Bot, Megaphone, Users } from 'lucide-vue-next';
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
      icon: Megaphone,
      to: { name: 'dashboard' },
      disabled: false,
    },
    {
      key: 'accounts',
      label: 'Аккаунты',
      icon: Users,
      to: { name: 'account-prep' },
      disabled: false,
    },
    {
      key: 'bots',
      label: 'Боты',
      icon: Bot,
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
  flex-direction: column;
  gap: 0.2rem;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.6rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  transition:
    color 0.15s,
    background 0.15s;
}

.nav-item:hover {
  color: var(--text);
  text-decoration: none;
  background: var(--surface-hover);
}

.nav-item.router-link-active {
  color: #fff;
  background: var(--accent-soft);
}

.nav-item.router-link-active .nav-icon {
  color: var(--accent);
}

.nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 60%;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
}

.nav-item--disabled {
  opacity: 0.35;
  pointer-events: none;
  cursor: not-allowed;
}

.nav-icon {
  flex-shrink: 0;
  color: var(--muted);
  transition: color 0.15s;
}

.nav-item:hover .nav-icon {
  color: var(--text);
}

.nav-label {
  line-height: 1.2;
}

@media (max-width: 768px) {
  .nav-label {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 0.65rem;
  }

  .nav-indicator {
    left: auto;
    right: 4px;
    top: 4px;
    transform: none;
    width: 5px;
    height: 5px;
    border-radius: 50%;
  }
}
</style>
