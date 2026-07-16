import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  POSTER_MAX_RETRIES,
  POSTER_RETRY_BACKOFF_MS,
  posterRetryBackoffMs,
  withPosterRetryParam,
} from "./posterRetry";

describe("withPosterRetryParam", () => {
  it("leaves src unchanged for attempt 0", () => {
    expect(withPosterRetryParam("/web/radarr/x/movie/1/thumbnail", 0)).toBe(
      "/web/radarr/x/movie/1/thumbnail",
    );
  });

  it("appends _retry for attempt > 0", () => {
    expect(withPosterRetryParam("/web/radarr/x/movie/1/thumbnail", 2)).toBe(
      "/web/radarr/x/movie/1/thumbnail?_retry=2",
    );
  });

  it("preserves and replaces existing query params", () => {
    expect(withPosterRetryParam("/thumb?foo=1&_retry=9", 1)).toBe("/thumb?foo=1&_retry=1");
  });
});

describe("posterRetryBackoffMs", () => {
  it("uses exponential backoff from the base", () => {
    expect(posterRetryBackoffMs(0)).toBe(POSTER_RETRY_BACKOFF_MS);
    expect(posterRetryBackoffMs(1)).toBe(POSTER_RETRY_BACKOFF_MS * 2);
    expect(posterRetryBackoffMs(2)).toBe(POSTER_RETRY_BACKOFF_MS * 4);
  });
});

describe("POSTER_MAX_RETRIES", () => {
  it("allows three retries after the first failure", () => {
    expect(POSTER_MAX_RETRIES).toBe(3);
  });
});
