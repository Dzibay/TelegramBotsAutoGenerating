/** Группы аватарок в ручной массовой партии (якорная строка + span). */
export function getAvatarAnchorGroups(rows) {
  const groups = [];
  let i = 0;
  while (i < rows.length) {
    const maxSpan = rows.length - i;
    const span = Math.max(1, Math.min(rows[i].avatarSpan || 1, maxSpan));
    groups.push({ index: i, span, row: rows[i] });
    i += span;
  }
  return groups;
}

export function resolveRowAvatar(row, rows) {
  const idx = rows.findIndex((r) => r.id === row.id);
  if (idx < 0) return row.avatarFile || null;
  for (const g of getAvatarAnchorGroups(rows)) {
    if (idx >= g.index && idx < g.index + g.span) {
      return g.row.avatarFile || null;
    }
  }
  return row.avatarFile || null;
}

export function normalizeAvatarSpans(rows) {
  let i = 0;
  while (i < rows.length) {
    const maxSpan = rows.length - i;
    rows[i].avatarSpan = Math.max(1, Math.min(rows[i].avatarSpan || 1, maxSpan));
    i += rows[i].avatarSpan;
  }
}

export function findAnchorForRowIndex(rows, rowIndex) {
  for (const g of getAvatarAnchorGroups(rows)) {
    if (rowIndex >= g.index && rowIndex < g.index + g.span) {
      return g;
    }
  }
  return null;
}
