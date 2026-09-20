/**
 * Guards the `next` query parameter used by `/login` (ARCHITECTURE.md §9,
 * "Signing in returns you to where you were"). Resolves `next` the way the
 * browser's own URL parser will (a backslash is read the same as a forward
 * slash for http/https, so `/\evil.example` becomes `//evil.example`), and
 * accepts only when that resolution stays on this site's origin. Returns the
 * *parsed* pathname + search + hash, never the raw string, so a value that
 * only coincidentally resolves same-site (after the parser strips control
 * characters, say) can't smuggle those characters through.
 */
const CONTROL_CHAR_RE = /[\x00-\x1f]/;
const PLACEHOLDER_ORIGIN = "http://placeholder.invalid";

export function safeNextPath(next: string | null | undefined): string | null {
  if (!next) return null;
  if (!next.startsWith("/")) return null;
  if (next.includes("\\")) return null;
  if (CONTROL_CHAR_RE.test(next)) return null;

  let url: URL;
  try {
    url = new URL(next, PLACEHOLDER_ORIGIN);
  } catch {
    return null;
  }
  if (url.origin !== PLACEHOLDER_ORIGIN) return null;

  return url.pathname + url.search + url.hash;
}
