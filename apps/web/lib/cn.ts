/** Tiny class-name joiner. We don't pull in clsx/tailwind-merge for this. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}
