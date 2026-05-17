<template>
  <div class="auth-page">
    <form class="card auth-form" @submit.prevent="onSubmit">
      <h1>Регистрация</h1>
      <div class="form-group">
        <label for="name">Имя</label>
        <input id="name" v-model="name" type="text" autocomplete="name" />
      </div>
      <div class="form-group">
        <label for="email">Email</label>
        <input id="email" v-model="email" type="email" required autocomplete="email" />
      </div>
      <div class="form-group">
        <label for="password">Пароль (мин. 8 символов)</label>
        <input id="password" v-model="password" type="password" required minlength="8" autocomplete="new-password" />
      </div>
      <p v-if="auth.error" class="error-text">{{ auth.error }}</p>
      <button type="submit" :disabled="auth.loading">{{ auth.loading ? 'Создание…' : 'Создать аккаунт' }}</button>
      <p class="hint">
        Уже есть аккаунт? <RouterLink to="/login">Войти</RouterLink>
      </p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';

const auth = useAuthStore();
const router = useRouter();

const name = ref('');
const email = ref('');
const password = ref('');

async function onSubmit() {
  await auth.register(email.value, password.value, name.value || null);
  router.push('/app');
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
  margin: 0 0 1.25rem;
  font-size: 1.5rem;
}

.auth-form button {
  width: 100%;
  margin-top: 0.5rem;
}

.hint {
  margin-top: 1rem;
  font-size: 0.875rem;
  color: var(--muted);
  text-align: center;
}
</style>
