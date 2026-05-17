<template>
  <div class="layout">
    <header class="header">
      <RouterLink to="/app" class="logo">TG Bots Generator</RouterLink>
      <nav>
        <RouterLink to="/app" class="nav-link">Кампании</RouterLink>
        <RouterLink to="/app/bots" class="nav-link">Боты</RouterLink>
        <RouterLink to="/app/accounts/prepare" class="nav-link">Подготовка</RouterLink>
        <span class="user">Админ</span>
        <button type="button" class="btn-ghost" @click="onLogout">Выйти</button>
      </nav>
    </header>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { RouterLink, RouterView, useRouter } from 'vue-router';
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
  max-width: 1100px;
  margin: 0 auto;
  width: 100%;
}
</style>
