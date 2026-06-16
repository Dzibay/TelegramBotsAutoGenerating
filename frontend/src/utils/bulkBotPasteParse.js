/**
 * Парсит текст со списком ботов: каждая строка «имя,username» или «имя, username».
 * @returns {{ entries: { displayName: string, username: string }[], errors: string[] }}
 */
export function parseBulkBotPaste(text) {
  const entries = [];
  const errors = [];
  const lines = (text || '').split(/\r?\n/);

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trim();
    if (!raw || raw.startsWith('#')) continue;

    const match = raw.match(/^(.+?)\s*,\s*(.+)$/);
    if (!match) {
      errors.push(`Строка ${i + 1}: ожидается формат «имя,username» или «имя, username»`);
      continue;
    }

    let displayName = match[1].trim();
    let username = match[2].trim().replace(/^@+/, '');

    if (
      (displayName.startsWith('"') && displayName.endsWith('"')) ||
      (displayName.startsWith('«') && displayName.endsWith('»'))
    ) {
      displayName = displayName.slice(1, -1).trim();
    }

    if (!displayName) {
      errors.push(`Строка ${i + 1}: пустое имя`);
      continue;
    }
    if (!username) {
      errors.push(`Строка ${i + 1}: пустой username`);
      continue;
    }

    entries.push({ displayName, username });
  }

  return { entries, errors };
}
