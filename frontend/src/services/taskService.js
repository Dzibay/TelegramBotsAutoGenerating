import apiClient from '../utils/apiClient';
import { API_ENDPOINTS } from '../config/api';

export const taskService = {
  async list({ activeOnly = false, campaignId = null, botId = null, limit = 100, offset = 0 } = {}) {
    const params = {
      active_only: activeOnly,
      limit,
      offset,
    };
    if (campaignId) params.campaign_id = campaignId;
    if (botId) params.bot_id = botId;
    const res = await apiClient.get(API_ENDPOINTS.TASKS.LIST, { params });
    return {
      tasks: res.data?.tasks ?? [],
      activeCount: res.data?.active_count ?? 0,
    };
  },

  async get(taskId) {
    const res = await apiClient.get(API_ENDPOINTS.TASKS.GET(taskId));
    return res.data?.task;
  },

  async getLogs(taskId, afterId = 0, { minLevel = 'info' } = {}) {
    const res = await apiClient.get(API_ENDPOINTS.TASKS.LOGS(taskId), {
      params: { after_id: afterId, min_level: minLevel },
    });
    return res.data?.logs ?? [];
  },

  async cancel(taskId) {
    const res = await apiClient.post(API_ENDPOINTS.TASKS.CANCEL(taskId));
    return res.data?.task;
  },

  async retry(taskId) {
    const res = await apiClient.post(API_ENDPOINTS.TASKS.RETRY(taskId));
    return res.data?.task;
  },
};
