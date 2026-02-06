# Search Configuration

Configure automated search and request integration for qBitrr.

## Overview

qBitrr can automatically trigger searches in your Arr instances for:

- Missing media
- Quality upgrades
- User requests from Overseerr/Ombi
- Failed downloads (re-search after blacklisting)

## Automated Search

### Enable Missing Media Search

Configure qBitrr to periodically search for missing content:

```toml
[[Radarr]]
Name = "Radarr-Main"
SearchMissing = true
SearchPeriodDays = 7  # Search every 7 days
```

This will automatically search for:

- Movies marked as "Wanted" in Radarr
- TV episodes marked as "Monitored" in Sonarr
- Albums marked as "Monitored" in Lidarr

### Search Intervals

Control how often qBitrr searches:

```toml
[[Radarr]]
SearchPeriodDays = 1   # Daily (aggressive)
SearchPeriodDays = 7   # Weekly (recommended)
SearchPeriodDays = 30  # Monthly (conservative)
```

**Recommendations:**
- **Daily** - For new/popular content
- **Weekly** - Balanced approach
- **Monthly** - For established libraries

## Request Integration

### Supported Request Systems

| System | Type | qBitrr Support |
|--------|------|----------------|
| [Overseerr](overseerr.md) | Full request management | ✅ Native API polling |
| [Ombi](ombi.md) | Full request management | ✅ Native API polling |
| [Requestrr](requestrr.md) | Discord chatbot | ✅ Via Overseerr or Ombi |

!!! tip "Requestrr Users"
    Requestrr is a Discord chatbot. Connect it to **Overseerr or Ombi**, then qBitrr
    will process requests through its existing integration.

### Request Priority

Prioritize searches for user requests:

```toml
[[Radarr]]
PrioritizeRequests = true  # Search requests first
RequestSearchDelay = 60    # Wait 1 minute after request
```

## Quality Upgrades

### Enable Upgrade Searches

Search for better quality releases:

```toml
[[Radarr]]
SearchUpgrades = true
UpgradePeriodDays = 14  # Search for upgrades every 2 weeks
```

### Upgrade Criteria

Configure what qualifies as an upgrade:

```toml
[[Radarr]]
# Only upgrade if:
MinimumQualityGain = "1080p"  # At least 1080p
CustomFormatScore = 100        # CF score improvement
```

## Failed Download Re-search

### Automatic Re-search

When a download fails, automatically search again:

```toml
[[Radarr]]
AutoResearchFailed = true
ResearchDelay = 300        # Wait 5 minutes before re-searching
MaxResearchAttempts = 3    # Try up to 3 times
```

### Blacklist Behavior

Configure blacklisting of failed releases:

```toml
[[Radarr]]
BlacklistFailed = true      # Blacklist failed torrents
BlacklistMinSize = 104857600  # Only blacklist if > 100MB
```

## Search Limits

### Rate Limiting

Prevent overwhelming your indexers:

```toml
[Settings]
MaxSearchesPerHour = 60    # Limit to 60 searches/hour
SearchDelaySeconds = 10    # Wait 10s between searches
```

### Concurrent Searches

Limit parallel searches:

```toml
[Settings]
MaxConcurrentSearches = 5  # Max 5 simultaneous searches
```

## Search Modes

### Radarr Search Modes

- **Standard** - Normal movie search
- **Interactive** - Allow manual selection
- **RSS** - Grab from RSS feeds

```toml
[[Radarr]]
SearchMode = "Standard"  # or "Interactive" or "RSS"
```

### Sonarr Search Modes

- **Series** - Search entire series
- **Season** - Search specific season
- **Episode** - Search individual episodes

```toml
[[Sonarr]]
DefaultSearchMode = "Episode"  # More targeted
```

## Advanced Search Options

### Custom Format Requirements

Only search if custom format requirements can be met:

```toml
[[Radarr]]
RequireCustomFormat = true
MinimumCustomFormatScore = 100
```

### Release Restrictions

Filter searches by release properties:

```toml
[[Radarr]]
PreferredWords = ["PROPER", "REPACK"]
ForbiddenWords = ["CAM", "TS"]
MinSeeders = 5  # Require at least 5 seeders
```

## Search Triggers

qBitrr triggers searches in these scenarios:

1. **Scheduled** - Based on SearchPeriodDays
2. **On Request** - When new Overseerr/Ombi request
3. **On Failure** - After torrent fails/is blacklisted
4. **Manual** - Via WebUI or API
5. **On Import** - If configured to search for upgrades

## Monitoring Searches

### Search Logs

Monitor search activity in logs:

```bash
# Check search activity
grep "search" ~/config/logs/Radarr-Main.log
```

### Search History

qBitrr tracks search history in the database:

```sql
SELECT * FROM searches ORDER BY created_at DESC LIMIT 10;
```

## Troubleshooting

### Too Many Searches

**Problem:** qBitrr is searching too frequently

**Solutions:**
```toml
# Increase search interval
SearchPeriodDays = 14

# Reduce concurrent searches
MaxConcurrentSearches = 2

# Add delay between searches
SearchDelaySeconds = 30
```

### No Search Results

**Problem:** Searches return no results

**Solutions:**
- Check indexer configuration in Arr instance
- Verify indexers are accessible
- Review search criteria (too restrictive?)
- Check Arr logs for errors

### Request Integration Not Working

**Problem:** Overseerr/Ombi requests not triggering searches

**Solutions:**
- Verify API key is correct
- Check Overseerr/Ombi is accessible
- Ensure CheckInterval is reasonable
- Review logs for connection errors

## Best Practices

### Search Frequency

- **New Libraries** - Search more frequently (daily)
- **Established Libraries** - Search less often (weekly/monthly)
- **Request-Driven** - Enable Overseerr/Ombi integration

### Resource Management

- Limit concurrent searches to avoid overload
- Add delays between searches
- Use reasonable check intervals
- Monitor indexer hit limits

### Quality Over Quantity

- Set minimum quality requirements
- Use custom format scoring
- Blacklist problematic releases
- Prioritize quality upgrades

## Configuration Examples

### Aggressive Search (New Library)

```toml
[[Radarr]]
Name = "Radarr-New"
SearchMissing = true
SearchPeriodDays = 1        # Daily
SearchUpgrades = true
UpgradePeriodDays = 3       # Upgrade search every 3 days
PrioritizeRequests = true
```

### Conservative Search (Established Library)

```toml
[[Radarr]]
Name = "Radarr-Established"
SearchMissing = true
SearchPeriodDays = 30       # Monthly
SearchUpgrades = false      # No automatic upgrades
MaxSearchesPerHour = 10     # Limited searches
```

### Request-Focused Configuration

```toml
[Settings.Overseerr]
Enabled = true
URI = "http://overseerr:5055"
APIKey = "overseerr-api-key"
CheckInterval = 180  # Check every 3 minutes

[[Radarr]]
PrioritizeRequests = true
RequestSearchDelay = 30     # Quick response
SearchMissing = false       # Only search requests
```

## Related Documentation

- [Radarr Configuration](../arr/radarr.md)
- [Sonarr Configuration](../arr/sonarr.md)
- [Lidarr Configuration](../arr/lidarr.md)
- [Configuration Reference](../config-file.md)

## Future Features

Planned enhancements for search configuration:

- Webhook support for custom triggers
- Advanced scheduling (cron-like)
- Search quota management
- A/B testing for search strategies
- Machine learning-based search optimization

---

**Note:** Overseerr and Ombi integration are planned features. Check the latest release notes for availability.
