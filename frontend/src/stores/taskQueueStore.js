import { defineStore } from 'pinia';
import { taskService } from '../services/taskService';
import { formatApiError } from '../utils/apiErrorMessage';

const ACTIVE = new Set(['queued', 'running']);
/** Создание ботов — в журнале кампании (creation_jobs), не дублируем здесь */
const HIDDEN_TASK_TYPES = new Set(['creation']);

export const useTaskQueueStore = defineStore('taskQueue', {
  state: () => ({
    tasks: [],
    activeCount: 0,
    loading: false,
    error: null,
    pollTimer: null,
    polling: false,
  }),

  getters: {
    activeTasks: (state) => state.tasks.filter((task) => ACTIVE.has(task.status)),
    recentTasks: (state) => state.tasks.filter((task) => !ACTIVE.has(task.status)),
    hasActive: (state) => state.activeCount > 0 || state.tasks.some((task) => ACTIVE.has(task.status)),
  },

  actions: {
    async refresh({ activeOnly = false } = {}) {
      this.loading = true;
      this.error = null;
      try {
        const data = await taskService.list({ activeOnly, limit: 100 });
        const tasks = (data.tasks || []).filter((t) => !HIDDEN_TASK_TYPES.has(t.task_type));
        this.tasks = tasks;
        this.activeCount = tasks.filter((t) => ACTIVE.has(t.status)).length;
        return tasks;
      } catch (e) {
        this.error = formatApiError(e, 'Не удалось загрузить очередь задач');
        return this.tasks;
      } finally {
        this.loading = false;
      }
    },

    startPolling(intervalMs = 2500) {
      if (this.polling) return;
      this.polling = true;
      this.refresh();
      this.pollTimer = window.setInterval(() => {
        this.refresh();
      }, intervalMs);
    },

    stopPolling() {
      this.polling = false;
      if (this.pollTimer) {
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
    },

    async cancel(taskId) {
      const task = await taskService.cancel(taskId);
      this.tasks = this.tasks.map((item) => (item.id === task.id ? task : item));
      await this.refresh();
      return task;
    },

    async retry(taskId) {
      const task = await taskService.retry(taskId);
      this.tasks = this.tasks.map((item) => (item.id === task.id ? task : item));
      await this.refresh();
      return task;
    },
  },
});
