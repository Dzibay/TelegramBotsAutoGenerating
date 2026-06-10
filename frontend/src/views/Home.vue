<template>
  <div class="page">
    <section class="hero card">
      <img src="/favicon.svg" alt="" class="hero-icon" width="64" height="64" />
      <h1>{{ siteName }}</h1>
      <p class="muted">
        Создавайте и ведите Telegram-ботов для рекламных кампаний: подготовка аккаунтов,
        генерация текстов и массовый запуск из одного интерфейса.
      </p>
      <div class="actions">
        <RouterLink v-if="!auth.isAuthenticated" to="/login" class="btn">Войти</RouterLink>
        <RouterLink v-else to="/app" class="btn">Кампании</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { SITE_NAME } from '../constants/site';
import { useAuthStore } from '../stores/authStore';

const auth = useAuthStore();
const siteName = SITE_NAME;

onMounted(() => {
  if (localStorage.getItem('access_token')) auth.fetchUser();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.hero {
  max-width: 560px;
  text-align: center;
}

.hero-icon {
  margin-bottom: 0.75rem;
  border-radius: 16px;
}

.hero h1 {
  margin: 0 0 0.75rem;
  font-size: 1.75rem;
}

.muted {
  color: var(--muted);
  margin: 0 0 1.5rem;
}

.actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
