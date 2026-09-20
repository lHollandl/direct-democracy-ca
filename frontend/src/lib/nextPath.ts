/**
 * Guards the `next` query parameter used by `/login` (ARCHITECTURE.md §9,
 * "Signing in returns you to where you were"). Only a same-site path —
 * beginning with exactly one `/` — is accepted; a protocol-relative address
 * (`//evil.example`) or an absolute URL (`https://evil.example`) is an
 * open-redirect vector and is dropped in favor of the caller's default.
 */
export function safeNextPath(next: string | null | undefined): string | null {
  if (!next) return null;
  if (!next.startsWith("/") || next.startsWith("//")) return null;
  if (next.includes("://")) return null;
  return next;
}
