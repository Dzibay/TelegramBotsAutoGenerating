import apiClient from '../utils/apiClient';

export const preparedAccountService = {
  async listAvailable() {
    const res = await apiClient.get('/prepared-accounts', {
      params: { available_only: true },
    });
    return res.data?.accounts ?? [];
  },

  async listAll() {
    const res = await apiClient.get('/prepared-accounts');
    return res.data?.accounts ?? [];
  },

  async attachToCampaign(campaignId, preparedAccountIds) {
    const form = new FormData();
    form.append('prepared_account_ids', JSON.stringify(preparedAccountIds));
    const res = await apiClient.post(
      `/campaigns/${campaignId}/accounts/from-prepared`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return res.data?.accounts ?? [];
  },

  async updateLabel(id, label) {
    const res = await apiClient.patch(`/prepared-accounts/${id}`, { label: label || null });
    return res.data?.account;
  },
};
