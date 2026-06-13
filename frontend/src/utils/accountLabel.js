/** Отображаемое имя аккаунта — только введённое пользователем label. */
export function accountDisplayLabel(account) {
  const label = (account?.label || '').trim();
  if (label) return label;
  const id = account?.id;
  return id != null ? `Аккаунт #${id}` : 'Аккаунт';
}
