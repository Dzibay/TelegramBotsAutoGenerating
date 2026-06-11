import apiClient from '../utils/apiClient';
import { API_ENDPOINTS } from '../config/api';

export const settingsService = {
  async getBotfatherPacing() {
    const res = await apiClient.get(API_ENDPOINTS.SETTINGS.BOTFATHER_PACING);
    return res.data?.botfather_pacing ?? null;
  },

  async updateBotfatherPacing(pacing) {
    const res = await apiClient.put(API_ENDPOINTS.SETTINGS.BOTFATHER_PACING, pacing);
    return res.data?.botfather_pacing ?? pacing;
  },
};
