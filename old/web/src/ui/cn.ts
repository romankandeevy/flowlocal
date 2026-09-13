/** Склейка классов. Своя, а не clsx: три строки против зависимости. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
