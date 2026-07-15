export function formatVersionLabel(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return "unknown";
  }
  return trimmed[0] === "v" || trimmed[0] === "V" ? trimmed : `v${trimmed}`;
}
