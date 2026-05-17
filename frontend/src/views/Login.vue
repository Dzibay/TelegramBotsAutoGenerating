<template>
  <div class="auth-page">
    <form class="card auth-form" @submit.prevent="onSubmit">
      <h1>Telegram Bots Generator</h1>
      <p class="muted">Вход по паролю администратора</p>
      <div class="form-group">
        <label for="password">Пароль</label>
        <input
          id="password"
          v-model="password"
          type="password"
          required
          autocomplete="current-password"
          placeholder="Пароль из ADMIN_PASSWORD"
        />
      </div>
      <p v-if="auth.error" class="error-text">{{ auth.error }}</p>
      <button type="submit" :disabled="auth.loading">{{ auth.loading ? 'Вход…' : 'Войти' }}</button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const password = ref('');

async function onSubmit() {
  await auth.login(password.value);
  const redirect = route.query.redirect || '/app';
  router.push(redirect);
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.auth-form {
  width: 100%;
  max-width: 400px;
}

.auth-form h1 {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
}

.muted {
  margin: 0 0 1.25rem;
  font-size: 0.875rem;
  color: var(--muted);
}

.auth-form button {
  width: 100%;
  margin-top: 0.5rem;
}
</style>
