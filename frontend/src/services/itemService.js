import apiClient from '../utils/apiClient';
import { API_ENDPOINTS } from '../config/api';

export const itemService = {
  async list() {
    const res = await apiClient.get(API_ENDPOINTS.ITEMS.LIST);
    return res.data?.items ?? [];
  },

  async create(title, description) {
    const res = await apiClient.post(API_ENDPOINTS.ITEMS.CREATE, { title, description });
    return res.data?.item;
  },

  async update(id, payload) {
    const res = await apiClient.patch(API_ENDPOINTS.ITEMS.UPDATE(id), payload);
    return res.data?.item;
  },

  async remove(id) {
    await apiClient.delete(API_ENDPOINTS.ITEMS.DELETE(id));
  },
};
