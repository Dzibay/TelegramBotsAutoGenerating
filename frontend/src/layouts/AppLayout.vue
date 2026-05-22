<template>
  <div class="layout">
    <header class="header">
      <RouterLink to="/app" class="logo">TG Bots Generator</RouterLink>
      <button type="button" class="btn-ghost btn-sm" @click="onLogout">Выйти</button>
    </header>
    <main class="main">
      <TaskProgressBanner />
      <WorkflowNav />
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView, useRouter } from 'vue-router';
import TaskProgressBanner from '../components/TaskProgressBanner.vue';
import WorkflowNav from '../components/WorkflowNav.vue';
import { useAuthStore } from '../stores/authStore';

const auth = useAuthStore();
const router = useRouter();

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
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
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
