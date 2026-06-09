<template>
  <div class="avatar-cell">
    <button
      type="button"
      class="avatar-btn"
      :title="previewUrl ? 'Сменить аватар' : 'Загрузить аватар'"
      @click="fileInput?.click()"
    >
      <img v-if="previewUrl" :src="previewUrl" alt="" class="avatar-img" />
      <span v-else class="avatar-placeholder">+</span>
    </button>
    <input
      ref="fileInput"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      class="file-input"
      @change="onFileChange"
    />
    <button
      v-if="previewUrl"
      type="button"
      class="clear-btn"
      title="Убрать"
      @click="clear"
    >
      ×
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const emit = defineEmits(['update:file', 'update:preview']);

const fileInput = ref(null);
const previewUrl = ref(null);

function onFileChange(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) {
    alert('Файл больше 5 МБ');
    e.target.value = '';
    return;
  }
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = URL.createObjectURL(file);
  emit('update:file', file);
  emit('update:preview', previewUrl.value);
}

function clear() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = null;
  if (fileInput.value) fileInput.value.value = '';
  emit('update:file', null);
  emit('update:preview', null);
}

defineExpose({ clear });
</script>

<style scoped>
.avatar-cell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px dashed var(--border);
  background: var(--bg);
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-btn:hover {
  border-color: var(--accent);
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  font-size: 1.1rem;
  color: var(--muted);
  line-height: 1;
}

.file-input {
  display: none;
}

.clear-btn {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: none;
  background: #ef4444;
  color: #fff;
  font-size: 0.65rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
}
</style>
