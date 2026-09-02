/** Join truthy class-name parts with a space. Pure leaf helper (spec §1). */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
