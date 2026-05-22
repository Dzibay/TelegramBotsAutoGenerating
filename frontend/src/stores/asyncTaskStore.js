import { defineStore } from 'pinia';
import { TASK_PRESETS } from '../constants/asyncTaskPresets';

export const useAsyncTaskStore = defineStore('asyncTask', {
  state: () => ({
    active: null,
    elapsedSec: 0,
    _elapsedTimer: null,
    _stepTimer: null,
  }),

  getters: {
    isActive(state) {
      return !!state.active;
    },

    currentStep(state) {
      if (!state.active) return '';
      const steps = state.active.steps;
      if (!steps?.length) return state.active.hint || '';
      return steps[state.active.stepIndex % steps.length];
    },

    /** Псевдо-прогресс до ~92%, пока задача не завершена. */
    progressPercent(state) {
      if (!state.active) return 0;
      const est = state.active.estimatedSec || 45;
      const ratio = state.elapsedSec / est;
      return Math.min(92, Math.round(ratio * 92));
    },

    contextLabel(state) {
      const ctx = state.active?.context;
      if (!ctx) return '';
      if (ctx.accountLabel) return ctx.accountLabel;
      if (ctx.username) return `@${ctx.username.replace(/^@/, '')}`;
      if (ctx.count != null) return `${ctx.count} акк.`;
      return '';
    },
  },

  actions: {
    async run(presetKey, fn, context = {}) {
      const preset = TASK_PRESETS[presetKey];
      if (!preset) {
        throw new Error(`Unknown async task preset: ${presetKey}`);
      }
      this._start({ ...preset, presetKey, context });
      try {
        return await fn();
      } finally {
        this._finishProgress();
        this._stop();
      }
    },

    _start(task) {
      this._stop();
      this.active = {
        ...task,
        stepIndex: 0,
        startedAt: Date.now(),
        done: false,
      };
      this.elapsedSec = 0;
      this._elapsedTimer = setInterval(() => {
        if (this.active) {
          this.elapsedSec = Math.floor((Date.now() - this.active.startedAt) / 1000);
        }
      }, 400);
      if (task.steps?.length > 1) {
        this._stepTimer = setInterval(() => {
          if (this.active && !this.active.done) {
            this.active = {
              ...this.active,
              stepIndex: (this.active.stepIndex + 1) % task.steps.length,
            };
          }
        }, 3500);
      }
    },

    _finishProgress() {
      if (this.active) {
        this.active = { ...this.active, done: true };
        this.elapsedSec = Math.max(
          this.elapsedSec,
          Math.floor((Date.now() - this.active.startedAt) / 1000)
        );
      }
    },

    _stop() {
      if (this._elapsedTimer) {
        clearInterval(this._elapsedTimer);
        this._elapsedTimer = null;
      }
      if (this._stepTimer) {
        clearInterval(this._stepTimer);
        this._stepTimer = null;
      }
      this.active = null;
      this.elapsedSec = 0;
    },

    matchesContext(field, value) {
      return this.active?.context?.[field] === value;
    },
  },
});
