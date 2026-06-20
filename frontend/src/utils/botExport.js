export function formatBotExport(bot) {
  const username = String(bot?.username || '').replace(/^@/, '');
  return [
    `Название: ${bot?.display_name || ''}`,
    `Username: @${username}`,
    `Описание: ${bot?.about_text || ''}`,
    `Плакат до Start: ${bot?.description || ''}`,
    `Стартовое сообщение: ${bot?.welcome_message || ''}`,
  ].join('\n');
}

export async function copyBotExportToClipboard(bot) {
  const text = formatBotExport(bot);
  await navigator.clipboard.writeText(text);
  return text;
}
