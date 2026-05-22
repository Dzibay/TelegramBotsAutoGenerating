import { defineStore } from 'pinia';
import { ref } from 'vue';

const STORAGE_KEY = 'tg_bots_active_campaign_id';

export const useWorkflowStore = defineStore('workflow', () => {
  const stored = localStorage.getItem(STORAGE_KEY);
  const activeCampaignId = ref(stored ? Number(stored) : null);
  const activeCampaignTitle = ref('');

  function setCampaign(id, title = '') {
    activeCampaignId.value = id ? Number(id) : null;
    activeCampaignTitle.value = title || '';
    if (id) {
      localStorage.setItem(STORAGE_KEY, String(id));
    } else {
      localStorage.removeItem(STORAGE_KEY);
      activeCampaignTitle.value = '';
    }
  }

  return {
    activeCampaignId,
    activeCampaignTitle,
    setCampaign,
  };
});
