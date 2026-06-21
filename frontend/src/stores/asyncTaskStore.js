import { defineStore } from 'pinia';
import { TASK_PRESETS } from '../constants/asyncTaskPresets';
import { formatApiError } from '../utils/apiErrorMessage';
import { useUiPrefsStore } from './uiPrefsStore';

let logSeq = 0;

export const useAsyncTaskStore = defineStore('asyncTask', {
  state: () => ({
    active: null,
    elapsedSec: 0,
    runtimeLogs: [],
    lastRuntimeLogs: [],
    serverProgressMessage: '',
    serverJobStatus: '',
    useServerProgress: false,
    _elapsedTimer: null,
    _stepTimer: null,
  }),

  getters: {
    isActive(state) {
      return !!state.active;
    },

    currentStep(state) {
      if (state.useServerProgress && state.serverProgressMessage) {
        return state.serverProgressMessage;
      }
      if (!state.active) return '';
      const steps = state.active.steps;
      if (!steps?.length) return state.active.hint || '';
      return steps[state.active.stepIndex % steps.length];
    },

    progressPercent(state) {
      if (!state.active) return 0;
      if (state.useServerProgress) {
        if (state.serverJobStatus === 'completed') return 100;
        if (state.serverJobStatus === 'failed' || state.serverJobStatus === 'cancelled') return 100;
        if (state.serverJobStatus === 'running') {
          return Math.min(90, 20 + state.elapsedSec * 2);
        }
        if (state.serverJobStatus === 'queued') return 12;
        if (state.serverJobStatus === 'syncing' || state.serverJobStatus === 'pending') {
          return Math.min(88, 15 + state.elapsedSec * 2);
        }
      }
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

    visibleRuntimeLogs(state) {
      if (state.active && state.runtimeLogs.length) return state.runtimeLogs;
      return state.lastRuntimeLogs;
    },
  },

  actions: {
    setServerProgress(message, status = '') {
      this.serverProgressMessage = message || '';
      this.serverJobStatus = status || '';
      this.useServerProgress = !!(message || status);
    },

    clearServerProgress() {
      this.serverProgressMessage = '';
      this.serverJobStatus = '';
      this.useServerProgress = false;
    },

    logStep(message, level = 'info', detail = null) {
      const entry = {
        id: `client-${++logSeq}`,
        message: String(message),
        level,
        time: new Date().toISOString(),
        context: detail,
        source: 'client',
      };
      if (this.active) {
        this.runtimeLogs.push(entry);
      }
      return entry;
    },

    async run(presetKey, fn, context = {}) {
      const preset = TASK_PRESETS[presetKey];
      if (!preset) {
        throw new Error(`Unknown async task preset: ${presetKey}`);
      }

      const uiPrefs = useUiPrefsStore();
      this.runtimeLogs = [];
      this.clearServerProgress();
      this._start({ ...preset, presetKey, context });

      const logStep = (message, level = 'info', detail = null) =>
        this.logStep(message, level, detail);

      if (uiPrefs.verboseLogs && preset.verboseSteps?.length) {
        logStep('План операции:', 'debug');
        for (const step of preset.verboseSteps) {
          logStep(`  · ${step}`, 'debug');
        }
      }

      logStep(`▶ ${preset.title}`, 'info', context);

      try {
        const result = await fn({ logStep, setServerProgress: (msg, st) => this.setServerProgress(msg, st) });
        logStep('✓ Готово', 'success');
        return result;
      } catch (err) {
        const msg = formatApiError(err, 'Ошибка');
        logStep(`✗ ${msg}`, 'error', err?.response?.data?.details || null);
        throw err;
      } finally {
        this._finishProgress();
        this.lastRuntimeLogs = [...this.runtimeLogs];
        this.clearServerProgress();
        this._stop();
      }
    },

    _start(task) {
      this._stopTimers();
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
      if (task.steps?.length > 1 && !this.useServerProgress) {
        this._stepTimer = setInterval(() => {
          if (this.active && !this.active.done && !this.useServerProgress) {
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

    _stopTimers() {
      if (this._elapsedTimer) {
        clearInterval(this._elapsedTimer);
        this._elapsedTimer = null;
      }
      if (this._stepTimer) {
        clearInterval(this._stepTimer);
        this._stepTimer = null;
      }
    },

    _stop() {
      this._stopTimers();
      this.active = null;
      this.elapsedSec = 0;
    },

    matchesContext(field, value) {
      return this.active?.context?.[field] === value;
    },

    clearLastLogs() {
      this.lastRuntimeLogs = [];
      this.runtimeLogs = [];
    },
  },
});
