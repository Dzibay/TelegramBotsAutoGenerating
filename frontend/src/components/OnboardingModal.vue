<template>
  <div v-if="open" class="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="onb-title">
    <div class="onboarding card">
      <h2 id="onb-title">Как пользоваться сервисом</h2>
      <ol class="onb-steps">
        <li>
          <strong>Кампания</strong> — название и ссылка на ваш сервис (куда ведут боты).
        </li>
        <li>
          <strong>Подготовка аккаунтов</strong> — загрузите ZIP из Telegram Desktop.
        </li>
        <li>
          <strong>Кампания</strong> — откройте её из списка, добавьте аккаунты и нажмите «Проверить все».
        </li>
        <li>
          <strong>Боты</strong> (в шапке) — создание по одному или списком. Фраза для AI — только при генерации текстов.
        </li>
      </ol>
      <div class="onb-actions">
        <RouterLink to="/app/campaigns/new" class="btn btn-sm" @click="dismiss">Создать кампанию</RouterLink>
        <RouterLink to="/app/accounts/prepare" class="btn btn-sm btn-ghost" @click="dismiss">
          Подготовить аккаунты
        </RouterLink>
        <button type="button" class="btn btn-sm btn-ghost" @click="dismiss">Понятно, больше не показывать</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router';

defineProps({
  open: { type: Boolean, default: false },
});

import { dismissOnboarding } from '../utils/onboarding';

const emit = defineEmits(['dismiss']);

function dismiss() {
  dismissOnboarding();
  emit('dismiss');
}
</script>

<style scoped>
.onboarding-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.55);
}

.onboarding {
  max-width: 480px;
  width: 100%;
  padding: 1.5rem;
}

.onboarding h2 {
  margin: 0 0 1rem;
  font-size: 1.15rem;
}

.onb-steps {
  margin: 0 0 1.25rem;
  padding-left: 1.2rem;
  font-size: 0.9rem;
  color: var(--muted);
  line-height: 1.65;
}

.onb-steps li {
  margin: 0.5rem 0;
}

.onb-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
</style>
