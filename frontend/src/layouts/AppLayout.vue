<template>
  <div class="layout">
    <header class="header">
      <div class="header-left">
        <RouterLink to="/app" class="logo">TG Bots Generator</RouterLink>
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
      </div>
      <button type="button" class="btn-ghost btn-sm" @click="onLogout">Выйти</button>
    </header>
    <main class="main">
      <TaskProgressBanner />
      <WorkflowNav v-if="!hideWorkflowNav" />
      <PageBreadcrumb v-if="hideWorkflowNav" />
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import PageBreadcrumb from '../components/PageBreadcrumb.vue';
import TaskProgressBanner from '../components/TaskProgressBanner.vue';
import WorkflowNav from '../components/WorkflowNav.vue';
import { useAuthStore } from '../stores/authStore';
import { useWorkflowStore } from '../stores/workflowStore';

const auth = useAuthStore();
const workflow = useWorkflowStore();
const route = useRoute();
const router = useRouter();

const hideWorkflowNav = computed(() => !!route.meta.hideWorkflowNav);

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
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 0;
  flex: 1;
}

.campaign-chip {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0.3rem 0.65rem;
  font-size: 0.78rem;
  font-weight: 500;
  border-radius: 99px;
  border: 1px solid var(--border);
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent);
  text-decoration: none;
}

.campaign-chip:hover {
  text-decoration: none;
  border-color: var(--accent);
}

.logo {
  font-weight: 700;
  color: var(--text);
  text-decoration: none;
}

.logo:hover {
  text-decoration: none;
  color: var(--accent);
}

nav {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user {
  font-size: 0.875rem;
  color: var(--muted);
}

.main {
  flex: 1;
  padding: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}
</style>
