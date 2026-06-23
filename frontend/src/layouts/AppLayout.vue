<template>
  <div class="layout">
    <aside class="sidebar">
      <RouterLink to="/app" class="logo">
        <img src="/favicon.svg" alt="" class="logo-icon" width="32" height="32" />
        <span class="logo-text">{{ siteName }}</span>
      </RouterLink>

      <AppMainNav class="sidebar-nav" />

      <div class="sidebar-footer">
        <RouterLink
          v-if="workflow.activeCampaignId"
          :to="{
            name: 'campaign-workspace',
            params: { id: workflow.activeCampaignId },
            query: { tab: 'guide' },
          }"
          class="campaign-chip"
          :title="workflow.activeCampaignTitle || 'Текущая кампания'"
        >
          <span class="chip-dot" />
          {{ workflow.activeCampaignTitle || `Кампания #${workflow.activeCampaignId}` }}
        </RouterLink>

        <VerboseLogToggle label="Детальные логи" class="sidebar-verbose" />
        <button type="button" class="btn-logout" @click="onLogout">
          <LogOut :size="16" />
          <span>Выйти</span>
        </button>
      </div>
    </aside>

    <div class="layout-main">
      <main class="main">
        <TaskProgressBanner />
        <TaskQueueIndicator />
        <PageBreadcrumb v-if="showBreadcrumb" />
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue';
import { LogOut } from 'lucide-vue-next';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import AppMainNav from '../components/AppMainNav.vue';
import PageBreadcrumb from '../components/PageBreadcrumb.vue';
import TaskProgressBanner from '../components/TaskProgressBanner.vue';
import TaskQueueIndicator from '../components/TaskQueueIndicator.vue';
import VerboseLogToggle from '../components/VerboseLogToggle.vue';
import { SITE_NAME } from '../constants/site';
import { useAuthStore } from '../stores/authStore';
import { useSettingsStore } from '../stores/settingsStore';
import { useWorkflowStore } from '../stores/workflowStore';

const siteName = SITE_NAME;

const auth = useAuthStore();
const settingsStore = useSettingsStore();
const workflow = useWorkflowStore();

onMounted(() => {
  settingsStore.fetchBotfatherPacing();
});
const route = useRoute();
const router = useRouter();

const showBreadcrumb = computed(() => !!route.meta.hideWorkflowNav);

function onLogout() {
  auth.logout();
  router.push({ name: 'login' });
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  background: var(--bg);
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  padding: 1.25rem 0.85rem;
  border-right: 1px solid var(--border);
  background: rgba(10, 13, 20, 0.85);
  backdrop-filter: blur(16px) saturate(1.3);
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.25rem 0.5rem 1.25rem;
  text-decoration: none;
  color: var(--text);
}

.logo:hover {
  text-decoration: none;
  color: var(--text);
}

.logo-icon {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  border-radius: 10px;
}

.logo-text {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.sidebar-nav {
  flex: 1;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.campaign-chip {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.5rem 0.7rem;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(59, 130, 246, 0.25);
  background: var(--accent-soft);
  color: #93c5fd;
  text-decoration: none;
  transition: border-color 0.15s, background 0.15s;
}

.campaign-chip:hover {
  text-decoration: none;
  border-color: rgba(59, 130, 246, 0.5);
  background: rgba(59, 130, 246, 0.18);
  color: #fff;
}

.chip-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--success);
}

.sidebar-verbose {
  padding: 0 0.25rem;
}

.btn-logout {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, background 0.15s, border-color 0.15s;
}

.btn-logout:hover {
  color: var(--text);
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.layout-main {
  flex: 1;
  margin-left: var(--sidebar-width);
  min-width: 0;
}

.main {
  padding: 1.5rem 2rem 2rem;
  max-width: 1200px;
  width: 100%;
}

@media (max-width: 768px) {
  .sidebar {
    width: 64px;
    padding: 1rem 0.5rem;
    align-items: center;
  }

  .logo {
    padding: 0.25rem 0 1rem;
    justify-content: center;
  }

  .logo-text {
    display: none;
  }

  .sidebar-footer {
    align-items: center;
  }

  .campaign-chip span:not(.chip-dot),
  .btn-logout span,
  .sidebar-verbose :deep(.verbose-toggle-label) {
    display: none;
  }

  .campaign-chip {
    padding: 0.5rem;
    justify-content: center;
  }

  .btn-logout {
    width: auto;
    padding: 0.55rem;
    justify-content: center;
  }

  .layout-main {
    margin-left: 64px;
  }

  .main {
    padding: 1rem 1.25rem 1.5rem;
  }
}
</style>
