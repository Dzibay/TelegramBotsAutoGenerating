<template>
  <div class="layout">
    <header class="app-header">
      <div class="header-inner">
        <RouterLink to="/app" class="logo">
          <span class="logo-mark">TG</span>
          <span class="logo-text">Bots Generator</span>
        </RouterLink>

        <AppMainNav class="header-nav" />

        <div class="header-right">
          <VerboseLogToggle label="Детальные логи" />
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
            {{ workflow.activeCampaignTitle || `Кампания #${workflow.activeCampaignId}` }}
          </RouterLink>
          <button type="button" class="btn-ghost btn-sm btn-logout" @click="onLogout">Выйти</button>
        </div>
      </div>
    </header>

    <main class="main">
      <TaskProgressBanner />
      <PageBreadcrumb v-if="showBreadcrumb" />
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import AppMainNav from '../components/AppMainNav.vue';
import PageBreadcrumb from '../components/PageBreadcrumb.vue';
import TaskProgressBanner from '../components/TaskProgressBanner.vue';
import VerboseLogToggle from '../components/VerboseLogToggle.vue';
import { useAuthStore } from '../stores/authStore';
import { useWorkflowStore } from '../stores/workflowStore';

const auth = useAuthStore();
const workflow = useWorkflowStore();
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
  flex-direction: column;
  background: var(--bg);
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(26, 35, 50, 0.98) 0%, rgba(15, 20, 25, 0.96) 100%);
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
}

.header-inner {
  display: flex;
  align-items: center;
  gap: 1rem;
  max-width: 1280px;
  margin: 0 auto;
  padding: 0.65rem 1.25rem;
  width: 100%;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  text-decoration: none;
  color: var(--text);
}

.logo:hover {
  text-decoration: none;
  color: var(--accent);
}

.logo-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 8px;
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #fff;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
}

.logo-text {
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.header-nav {
  flex: 1;
  justify-content: center;
  max-width: 420px;
  margin: 0 auto;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  margin-left: auto;
}

.campaign-chip {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.35rem 0.7rem;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 99px;
  border: 1px solid rgba(59, 130, 246, 0.35);
  background: rgba(59, 130, 246, 0.12);
  color: #93c5fd;
  text-decoration: none;
  transition: border-color 0.15s, background 0.15s;
}

.campaign-chip:hover {
  text-decoration: none;
  border-color: var(--accent);
  background: rgba(59, 130, 246, 0.2);
  color: #fff;
}

.btn-logout {
  flex-shrink: 0;
}

.main {
  flex: 1;
  padding: 1.25rem 1.5rem 1.5rem;
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
}

@media (max-width: 900px) {
  .header-inner {
    flex-wrap: wrap;
    padding: 0.6rem 1rem;
  }

  .header-nav {
    order: 3;
    width: 100%;
    max-width: none;
    margin: 0.25rem 0 0;
    justify-content: stretch;
  }

  .header-nav :deep(.main-nav) {
    width: 100%;
    justify-content: space-between;
  }

  .header-nav :deep(.nav-item) {
    flex: 1;
    justify-content: center;
  }

  .logo-text {
    display: none;
  }

  .header-right {
    margin-left: 0;
  }
}
</style>
