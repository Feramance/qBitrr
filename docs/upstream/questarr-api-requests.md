# Questarr API requests (for upstream discussion)

Use this document as the body (or starting point) for a [Questarr Discussion](https://github.com/Doezer/Questarr/discussions) or feature PR. These requests support external automation tools (e.g. [qBitrr](https://github.com/feramance/qBitrr)) that manage qBittorrent health and library workflows alongside Questarr.

---

## 1. Long-lived API authentication

**Problem:** All `/api/*` routes (after setup) require JWT from `POST /api/auth/login`. Automation tools must store username/password and handle token expiry/refresh.

**Request:** Add a static **API key** (header e.g. `X-Api-Key` or `Authorization: Bearer <token>`) configurable in Questarr settings—similar to Radarr/Sonarr/Lidarr—optionally scoped to a service account user.

**Benefit:** Simpler, more reliable integrations; no password in third-party configs long-term.

---

## 2. Trigger search (and optional grab) for a single game

**Problem:** Questarr already implements the full search-and-download pipeline internally:

- `searchAndCategorizeItemsForGame` (`server/search.ts`, used from `server/cron.ts`)
- Blacklist filtering, preferred release groups, platform filters, indexer deduplication
- Optional grab via `DownloaderManager.addDownloadWithFallback`

That logic runs on a **schedule** (`checkAutoSearch`) or through the **UI**. There is no API to run it for **one game on demand** when an external tool detects a failed torrent or wants to retry immediately.

**Request:** Expose an endpoint that **reuses existing code**, for example:

```
POST /api/games/:id/search
```

or

```
POST /api/games/:id/search-and-grab
```

**Request body (example):**

```json
{
  "grab": false
}
```

- `grab: false` — search indexers, update `searchResultsAvailable`, return summary (items found, filtered count, errors)
- `grab: true` — same as above, then download the best result using the **same rules** as cron/UI (`downloadRules`, preferred groups, platform, etc.)

**Response (example):**

```json
{
  "itemsFound": 12,
  "itemsAfterFilters": 3,
  "grabbed": true,
  "downloadHash": "abc123...",
  "downloaderId": "...",
  "errors": []
}
```

**Benefit:** Integrations do not reimplement ranking/grab logic in another language; behavior stays identical to Questarr's own automation.

---

## 3. Import / link completed download by hash (optional)

**Problem:** When a torrent completes in qBittorrent, external tools know the **hash** and **path** but may not match the release title to a library game reliably.

**Request:** Endpoint such as:

```
POST /api/downloads/import
```

**Body (example):**

```json
{
  "downloaderId": "...",
  "downloadHash": "...",
  "downloadTitle": "...",
  "gameId": "optional-uuid",
  "path": "optional-filesystem-path",
  "category": "main"
}
```

Behavior: link to `gameId` if provided, else attempt library match (existing title utilities), create `game_downloads` record, update game status—same as claim flow today but optimized for post-complete automation.

**Benefit:** Parity with Servarr's `Downloaded*Scan` style workflows without fragile title parsing in external tools.

---

## Context

[qBitrr](https://github.com/feramance/qBitrr) plans Questarr support with feature parity to its Radarr/Sonarr/Lidarr integrations (torrent health, re-search, missing search, WebUI catalog). These APIs would significantly reduce duplication and drift. Happy to help test or review a PR.
