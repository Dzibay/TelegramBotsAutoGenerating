<template>
  <div
    class="dropzone"
    :class="{ 'dropzone--active': isDragging, 'dropzone--has-files': files.length }"
    @dragover.prevent="isDragging = true"
    @dragleave.prevent="isDragging = false"
    @drop.prevent="onDrop"
    @click="openPicker"
  >
    <input ref="inputRef" type="file" accept=".zip" multiple hidden @change="onPick" />

    <div v-if="!files.length" class="dropzone-empty">
      <p class="dropzone-title">Перетащите архив с данными Telegram</p>
      <p class="dropzone-hint">ZIP-файл на каждый аккаунт · или нажмите, чтобы выбрать</p>
    </div>

    <ul v-else class="file-list" @click.stop>
      <li v-for="(f, i) in files" :key="`${f.name}-${i}`" class="file-item">
        <span class="file-icon">ZIP</span>
        <span class="file-name">{{ f.name }}</span>
        <span class="file-size">{{ formatSize(f.size) }}</span>
        <button type="button" class="file-remove" @click="remove(i)">×</button>
      </li>
    </ul>

    <button v-if="files.length" type="button" class="btn-add-more" @click.stop="openPicker">
      + Добавить ещё
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
});

const emit = defineEmits(['update:modelValue']);

const inputRef = ref(null);
const isDragging = ref(false);
const files = ref([...props.modelValue]);

function sync() {
  emit('update:modelValue', [...files.value]);
}

function openPicker() {
  inputRef.value?.click();
}

function addFiles(list) {
  const incoming = Array.from(list).filter((f) => f.name.toLowerCase().endsWith('.zip'));
  files.value = [...files.value, ...incoming];
  sync();
}

function onPick(e) {
  addFiles(e.target.files || []);
  e.target.value = '';
  isDragging.value = false;
}

function onDrop(e) {
  isDragging.value = false;
  addFiles(e.dataTransfer?.files || []);
}

function remove(index) {
  files.value.splice(index, 1);
  sync();
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
</script>

<style scoped>
.dropzone {
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 1.25rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  background: rgba(15, 20, 25, 0.5);
}

.dropzone--active {
  border-color: var(--accent);
  background: rgba(59, 130, 246, 0.08);
}

.dropzone--has-files {
  cursor: default;
}

.dropzone-empty {
  text-align: center;
  padding: 1rem 0;
}

.dropzone-title {
  margin: 0;
  font-weight: 600;
}

.dropzone-hint {
  margin: 0.35rem 0 0;
  font-size: 0.85rem;
  color: var(--muted);
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.65rem;
  background: var(--bg);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.file-icon {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--accent);
  background: rgba(59, 130, 246, 0.15);
  padding: 0.2rem 0.35rem;
  border-radius: 4px;
}

.file-name {
  flex: 1;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 0.8rem;
  color: var(--muted);
}

.file-remove {
  padding: 0.15rem 0.45rem;
  background: transparent;
  border: none;
  color: var(--muted);
  font-size: 1.1rem;
  line-height: 1;
}

.file-remove:hover {
  color: var(--danger);
  background: transparent;
}

.btn-add-more {
  margin-top: 0.75rem;
  width: 100%;
  background: transparent;
  border: 1px dashed var(--border);
  color: var(--muted);
}

.btn-add-more:hover {
  background: var(--surface);
  color: var(--text);
}
</style>
