import apiClient from '../utils/apiClient';
import { API_ENDPOINTS } from '../config/api';

export const campaignService = {
  async list() {
    const res = await apiClient.get(API_ENDPOINTS.CAMPAIGNS.LIST);
    return res.data?.campaigns ?? [];
  },

  async create(payload) {
    const res = await apiClient.post(API_ENDPOINTS.CAMPAIGNS.CREATE, payload);
    return res.data?.campaign;
  },

  async createFull({ payload, preparedAccountIds, autoStart = true }) {
    const form = new FormData();
    form.append('data', JSON.stringify(payload));
    form.append('prepared_account_ids', JSON.stringify(preparedAccountIds ?? []));
    form.append('auto_start', autoStart ? 'true' : 'false');
    const res = await apiClient.post(API_ENDPOINTS.CAMPAIGNS.CREATE_FULL, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return res.data;
  },

  async get(id) {
    const res = await apiClient.get(API_ENDPOINTS.CAMPAIGNS.GET(id));
    return {
      campaign: res.data?.campaign,
      activeJob: res.data?.active_job,
    };
  },

  async getBots(id) {
    const res = await apiClient.get(API_ENDPOINTS.CAMPAIGNS.BOTS(id));
    return res.data?.bots ?? [];
  },

  async getAccounts(id) {
    const res = await apiClient.get(API_ENDPOINTS.CAMPAIGNS.ACCOUNTS(id));
    return res.data?.accounts ?? [];
  },

  async attachPreparedAccounts(campaignId, preparedAccountIds) {
    const form = new FormData();
    form.append('prepared_account_ids', JSON.stringify(preparedAccountIds));
    const res = await apiClient.post(
      API_ENDPOINTS.PREPARED_ACCOUNTS.ATTACH(campaignId),
      form,
      { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000 }
    );
    return {
      accounts: res.data?.accounts ?? [],
      verifySummary: res.data?.verify_summary,
    };
  },

  async verifyAllAccounts(campaignId) {
    const res = await apiClient.post(API_ENDPOINTS.CAMPAIGNS.VERIFY_ACCOUNTS(campaignId), null, {
      timeout: 300000,
    });
    return res.data;
  },

  async verifyAccount(campaignId, accountId) {
    const res = await apiClient.post(
      API_ENDPOINTS.CAMPAIGNS.VERIFY_ACCOUNT(campaignId, accountId),
      null,
      { timeout: 120000 }
    );
    return res.data?.account;
  },

  async removeAccount(campaignId, accountId) {
    await apiClient.delete(API_ENDPOINTS.CAMPAIGNS.REMOVE_ACCOUNT(campaignId, accountId));
  },

  async start(campaignId) {
    const res = await apiClient.post(API_ENDPOINTS.CAMPAIGNS.START(campaignId));
    return res.data?.job;
  },

  async update(id, payload) {
    const res = await apiClient.patch(API_ENDPOINTS.CAMPAIGNS.GET(id), payload);
    return res.data?.campaign;
  },

  async generateKeywords(campaignId, { count = 10, merge = true } = {}) {
    const res = await apiClient.post(API_ENDPOINTS.CAMPAIGNS.GENERATE_KEYWORDS(campaignId), {
      count,
      merge,
    });
    return {
      campaign: res.data?.campaign,
      keywords: res.data?.keywords ?? res.data?.campaign?.keywords ?? [],
    };
  },

  async suggestKeyword(campaignId, preferred = null) {
    const res = await apiClient.get(API_ENDPOINTS.CAMPAIGNS.SUGGEST_KEYWORD(campaignId), {
      params: preferred ? { preferred } : {},
    });
    return res.data;
  },

  async remove(id) {
    await apiClient.delete(API_ENDPOINTS.CAMPAIGNS.GET(id));
  },
};

export const jobService = {
  async get(jobId) {
    const res = await apiClient.get(API_ENDPOINTS.JOBS.GET(jobId));
    return res.data?.job;
  },

  async getLogs(jobId, afterId = 0) {
    const res = await apiClient.get(API_ENDPOINTS.JOBS.LOGS(jobId), { params: { after_id: afterId } });
    return res.data?.logs ?? [];
  },
};
