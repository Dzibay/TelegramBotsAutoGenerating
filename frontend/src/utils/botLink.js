export function telegramBotUrl(username) {
  if (!username) return null;
  const u = String(username).trim().replace(/^@/, '').toLowerCase();
  return u ? `https://t.me/${u}` : null;
}
