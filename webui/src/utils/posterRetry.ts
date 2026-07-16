/**
 * Helpers for Arr poster `<img>` load retries (cache-bust + backoff).
 */

/** Max retries after the first failed load (total attempts = 1 + this). */
export const POSTER_MAX_RETRIES = 3;

/** Base delay in ms; backoff is ``base * 2^attempt`` before each retry. */
export const POSTER_RETRY_BACKOFF_MS = 150;

/**
 * Append or replace ``_retry`` so the browser does not reuse a failed response.
 * ``attempt`` 0 leaves ``src`` unchanged; 1+ sets ``_retry=<attempt>``.
 */
export function withPosterRetryParam(src: string, attempt: number): string {
  if (attempt <= 0) return src;
  const qIndex = src.indexOf("?");
  const base = qIndex >= 0 ? src.slice(0, qIndex) : src;
  const existing = qIndex >= 0 ? src.slice(qIndex + 1) : "";
  const params = new URLSearchParams(existing);
  params.set("_retry", String(attempt));
  const qstr = params.toString();
  return qstr ? `${base}?${qstr}` : base;
}

/** Backoff before retrying after a failure at ``attempt`` (0-based, before increment). */
export function posterRetryBackoffMs(attempt: number): number {
  const safe = Math.max(0, attempt);
  return POSTER_RETRY_BACKOFF_MS * 2 ** safe;
}
