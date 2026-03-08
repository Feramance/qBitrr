# Search Configuration

Configure automated search and request integration for qBitrr.

## Overview

qBitrr can automatically trigger searches in your Arr instances for:

- **Missing media** – movies, episodes, or albums marked wanted/monitored
- **Quality upgrades** – better quality or custom format score
- **User requests** – from Overseerr or Ombi (when configured)
- **Failed downloads** – re-search after blacklisting

Configuration lives under **`[<Arr>-<Name>.EntrySearch]`** (e.g. `[Radarr-Movies.EntrySearch]`, `[Sonarr-TV.EntrySearch]`). Overseerr and Ombi are configured under `[<Arr>-<Name>.EntrySearch.Overseerr]` and `[<Arr>-<Name>.EntrySearch.Ombi]`.

## Quick reference

| Area | Where | Key examples |
|------|--------|----------------|
| Enable missing search | `[Radarr-Movies.EntrySearch]` | `SearchMissing = true` |
| Request check interval | Same section | `SearchRequestsEvery = 300` (seconds between Overseerr/Ombi checks) |
| Delay between search commands | `[Settings]` | `SearchLoopDelay = 30` (seconds between each search) |
| Overseerr | `[Radarr-Movies.EntrySearch.Overseerr]` | `OverseerrURI`, `OverseerrAPIKey`, `SearchOverseerrRequests` |
| Ombi | `[Radarr-Movies.EntrySearch.Ombi]` | `OmbiURI`, `OmbiAPIKey`, `SearchOmbiRequests` |

There is no top-level `[Settings.Overseerr]` or `[[Radarr]]` search block; each Arr instance is named like `Radarr-Movies` and has its own `EntrySearch` (and optionally `EntrySearch.Overseerr` / `EntrySearch.Ombi`).

## Supported request systems

| System | Type | qBitrr support |
|--------|------|----------------|
| [Overseerr](overseerr.md) | Request management | ✅ Native API polling |
| [Ombi](ombi.md) | Request management | ✅ Native API polling |
| [Requestrr](requestrr.md) | Discord chatbot | ✅ Via Overseerr or Ombi |

Overseerr and Ombi integration is **implemented**: configure Overseerr or Ombi under each Arr instance's `EntrySearch.Overseerr` or `EntrySearch.Ombi` in `config.toml`. Requestrr does not have its own qBitrr config; connect it to Overseerr or Ombi, then qBitrr processes those requests through the same integration.

## Full documentation

For detailed options (SearchMissing, SearchRequestsEvery, SearchLoopDelay, temp profiles, quality mappings, troubleshooting), see:

- [Automated Search](../../features/automated-search.md) – full search loop, Overseerr/Ombi, temp profiles, limits
- [Radarr Configuration](../arr/radarr.md)
- [Sonarr Configuration](../arr/sonarr.md)
- [Lidarr Configuration](../arr/lidarr.md)
- [Configuration File Reference](../config-file.md)

## Related

- [Configuration File Reference](../config-file.md)
- [Overseerr](overseerr.md) | [Ombi](ombi.md) | [Requestrr](requestrr.md)
