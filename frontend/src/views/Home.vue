<template>
  <div class="page">
    <section class="hero card">
      <div class="hero-icon-wrap">
        <img src="/favicon.svg" alt="" class="hero-icon" width="48" height="48" />
      </div>
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
  box-shadow: var(--shadow-md);
}

.hero-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 4.5rem;
  height: 4.5rem;
  margin-bottom: 0.75rem;
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
  box-shadow: 0 0 32px var(--accent-glow);
}

.hero-icon {
  border-radius: 14px;
}

.hero h1 {
  margin: 0 0 0.75rem;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.muted {
  color: var(--muted);
  margin: 0 0 1.5rem;
  line-height: 1.6;
}

.actions {
  display: flex;
  gap: 0.75rem;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
