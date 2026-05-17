import apiClient from '../utils/apiClient';

export const botService = {
  async listGrouped() {
    const res = await apiClient.get('/bots', { params: { grouped: true } });
    return res.data?.campaigns ?? [];
  },

  async list(campaignId) {
    const params = campaignId ? { campaign_id: campaignId } : {};
    const res = await apiClient.get('/bots', { params });
    return res.data?.bots ?? [];
  },

  async get(id) {
    const res = await apiClient.get(`/bots/${id}`);
    return res.data?.bot;
  },

  async generateDraft({ campaignId, accountId, targetUrl, keyword, redirectSlug }) {
    const res = await apiClient.post('/bots/generate-draft', {
      campaign_id: campaignId,
      telegram_account_id: accountId,
      target_url: targetUrl,
      keyword: keyword || null,
      redirect_slug: redirectSlug || null,
    });
    return res.data?.draft;
  },

  async create(payload) {
    const res = await apiClient.post('/bots', payload, { timeout: 300000 });
    return res.data?.bot;
  },

  async update(id, payload) {
    const res = await apiClient.patch(`/bots/${id}`, payload);
    return res.data?.bot;
  },

  async remove(id) {
    await apiClient.delete(`/bots/${id}`);
  },

  async start(id) {
    const res = await apiClient.post(`/bots/${id}/start`);
    return res.data?.bot;
  },

  async stop(id) {
    const res = await apiClient.post(`/bots/${id}/stop`);
    return res.data?.bot;
  },

  async verify(id) {
    const res = await apiClient.post(`/bots/${id}/verify`);
    return res.data;
  },
};
