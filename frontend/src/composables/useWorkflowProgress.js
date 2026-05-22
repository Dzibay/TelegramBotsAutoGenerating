import { onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { campaignService } from '../services/campaignService';
import { preparedAccountService } from '../services/preparedAccountService';
import { useWorkflowStore } from '../stores/workflowStore';

export function useWorkflowProgress() {
  const route = useRoute();
  const workflow = useWorkflowStore();

  const hasCampaigns = ref(false);
  const hasPrepared = ref(false);
  const campaignAccounts = ref(0);
  const campaignBots = ref(0);
  const loading = ref(false);

  async function refresh() {
    loading.value = true;
    try {
      const [campaigns, prepared] = await Promise.all([
        campaignService.list(),
        preparedAccountService.listAvailable(),
      ]);
      hasCampaigns.value = campaigns.length > 0;
      hasPrepared.value = prepared.length > 0;

      const cid = workflow.activeCampaignId;
      if (cid) {
        const c = campaigns.find((x) => x.id === cid);
        campaignAccounts.value = c?.accounts_count ?? 0;
        campaignBots.value = c?.bots_count ?? 0;
      } else {
        campaignAccounts.value = 0;
        campaignBots.value = 0;
      }
    } catch {
      /* не блокируем навигацию */
    } finally {
      loading.value = false;
    }
  }

  onMounted(refresh);
  watch(
    () => [route.path, workflow.activeCampaignId],
    () => refresh()
  );

  return {
    hasCampaigns,
    hasPrepared,
    campaignAccounts,
    campaignBots,
    loading,
    refresh,
  };
}
