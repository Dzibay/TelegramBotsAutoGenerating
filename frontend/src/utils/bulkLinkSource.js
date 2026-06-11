/** Режимы ссылок при массовом создании ботов. */
export const LINK_SOURCE = {
  REFERRAL: 'referral',
  PER_BOT: 'per_bot',
  CAMPAIGN: 'campaign',
  BATCH: 'batch',
};

export function pickDefaultLinkSource({ usesReferralApi, campaignResourceUrl }) {
  if (usesReferralApi) return LINK_SOURCE.REFERRAL;
  if (campaignResourceUrl?.trim()) return LINK_SOURCE.CAMPAIGN;
  return LINK_SOURCE.BATCH;
}

export function sharedLinkUrl(linkSource, { campaignResourceUrl, batchUrl }) {
  if (linkSource === LINK_SOURCE.CAMPAIGN) return campaignResourceUrl?.trim() || '';
  if (linkSource === LINK_SOURCE.BATCH) return batchUrl?.trim() || '';
  return '';
}

export function usesReferralLinks(linkSource) {
  return linkSource === LINK_SOURCE.REFERRAL;
}

export function showRedirectToggle(linkSource) {
  return [LINK_SOURCE.CAMPAIGN, LINK_SOURCE.BATCH, LINK_SOURCE.PER_BOT].includes(linkSource);
}

export function effectiveLinkMode(linkSource, trackClicks) {
  if (usesReferralLinks(linkSource)) return 'direct';
  return trackClicks ? 'redirect' : 'direct';
}

export function isLinkStepValid(linkSource, { usesReferralApi, campaignResourceUrl, batchUrl }) {
  switch (linkSource) {
    case LINK_SOURCE.REFERRAL:
      return usesReferralApi;
    case LINK_SOURCE.PER_BOT:
      return true;
    case LINK_SOURCE.CAMPAIGN:
      return !!campaignResourceUrl?.trim();
    case LINK_SOURCE.BATCH:
      return !!batchUrl?.trim();
    default:
      return false;
  }
}
