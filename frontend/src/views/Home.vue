<template>
  <div class="page">
    <section class="hero card">
      <h1>Telegram Bots Generator</h1>
      <p class="muted">
        Массовое создание ботов по ключевым словам и нише: tdata-аккаунты,
        AI-контент и единый процесс обслуживания.
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
import { useAuthStore } from '../stores/authStore';

const auth = useAuthStore();

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
