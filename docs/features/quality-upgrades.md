# Quality Upgrades

qBitrr can automatically upgrade your existing media to higher quality versions, ensuring your library continuously improves as better releases become available.

---

## Overview

Quality upgrading is a continuous process where qBitrr:

1. **Monitors** existing media for better quality releases
2. **Searches** for improved versions based on your criteria
3. **Downloads** upgrades when found
4. **Replaces** old files with new ones (managed by Arr)
5. **Seeds** the new torrent while removing the old one

**Use Cases:**

- Upgrading 720p → 1080p → 4K as releases become available
- Replacing x264 → x265 for better compression
- Upgrading lossy → lossless audio (Lidarr)
- Improving custom format scores (Scene → P2P, HDR, etc.)

---

## Upgrade Strategies

### Strategy 1: Continuous Upgrade Search

**Goal:** Always look for better quality

**Configuration:**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true  # Enable upgrade searching
SearchRequestsEvery = 600  # Check every 10 minutes
SearchAgainOnSearchCompletion = true  # Continuous loop
```

**How it works:**

- qBitrr queries Radarr for **all movies** (not just missing)
- Sends upgrade search commands for each movie
- Radarr downloads better quality if available and allowed by quality profile

**Best for:**

- Building a high-quality library
- Users with large storage capacity
- Private tracker members with good retention

**Considerations:**

- **Bandwidth:** Upgrades can download massive amounts of data (50+ GB per 4K movie)
- **Indexer hits:** Searches every movie repeatedly (respect rate limits)
- **Storage:** Requires space for both old and new files during transition

---

### Strategy 2: Quality Target Enforcement

**Goal:** Ensure media meets minimum quality standards

**Configuration:**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = false
QualityUnmetSearch = true  # Only search if quality not met
SearchRequestsEvery = 1200  # Check every 20 minutes
```

**How it works:**

- qBitrr checks each movie's quality against quality profile cutoff
- Only searches if current quality is **below cutoff**
- Stops searching once cutoff is met

**Example:**

- Quality profile cutoff: 1080p
- Current quality: 720p → **search triggered**
- Upgrade to 1080p → **searching stops**

**Best for:**

- Enforcing minimum quality standards
- Reducing bandwidth usage
- "Good enough" quality approach

**Benefit:** Focused searching only where needed, saving bandwidth and indexer hits

---

### Strategy 3: Custom Format Upgrades

**Goal:** Upgrade based on release characteristics (HDR, P2P, audio codecs, etc.)

**Configuration:**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = false
CustomFormatUnmetSearch = true  # Search for better custom format scores
SearchRequestsEvery = 1200
```

**How it works:**

- qBitrr checks custom format scores against profile requirements
- Searches for releases with higher custom format scores
- Upgrades when better-scoring release is found

**Example Custom Formats:**

- HDR/DV preference
- Release group ranking (SPARKS > RARBG)
- Proper/Repack detection
- Audio codec preference (Atmos, DTS-HD)

**Best for:**

- Advanced users with custom format expertise
- Fine-tuned quality control beyond resolution
- TraSH Guides users

!!! info "Custom Formats Guide"
    See **[Custom Formats](custom-formats.md)** for detailed setup and examples.

---

### Strategy 4: Strict Enforcement (Aggressive)

**Goal:** Reject anything below custom format minimum score

**Configuration:**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = true  # Remove releases below minimum
SearchRequestsEvery = 600
```

**How it works:**

- qBitrr checks custom format scores
- **Removes** and **blacklists** torrents below minimum score
- Triggers immediate search for higher-scoring release

**Warning:** Very aggressive! Only use if:

- You have strict quality requirements
- Your custom formats are well-tested
- You're confident in your scoring system

**Best for:**

- High-end home theaters
- Strict quality control environments
- Users who know exactly what they want

---

### Strategy 5: Staged Upgrade Path

**Goal:** Gradually improve quality over time

**Phase 1: Build Library (Get Anything)**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = false
UseTempForMissing = true  # Accept lower quality for missing
QualityProfileMappings = {"Ultra HD" = "HD-1080p"}
```

**Phase 2: Upgrade to Target Quality**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = false
QualityUnmetSearch = true  # Upgrade to cutoff
UseTempForMissing = false
```

**Phase 3: Continuous Improvement**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true  # Always look for better
QualityUnmetSearch = true
```

**How it works:**

1. **Build:** Accept any quality just to have the content
2. **Stabilize:** Upgrade everything to minimum acceptable quality
3. **Optimize:** Continuously seek better versions

**Best for:**

- New library builds
- Limited initial bandwidth
- Long-term quality improvement plans

---

## Configuration Reference

### DoUpgradeSearch

**Type:** Boolean
**Default:** `false`

Enable continuous upgrade searching for all media.

```toml
DoUpgradeSearch = true
```

**When enabled:**

- Searches **all existing media** for better versions
- Runs continuously (not just for missing items)
- Respects quality profile upgrade settings

**Bandwidth Impact:** ⚠️ **HIGH** - can download many GB per movie/episode

---

### QualityUnmetSearch

**Type:** Boolean
**Default:** `false`

Search only for media below quality profile cutoff.

```toml
QualityUnmetSearch = true
```

**When enabled:**

- Only searches media **below cutoff quality**
- Stops searching once cutoff is met
- More efficient than DoUpgradeSearch

**Bandwidth Impact:** ⚠️ **MEDIUM** - targeted upgrades only

---

### CustomFormatUnmetSearch

**Type:** Boolean
**Default:** `false`

Search for media below custom format score requirements.

```toml
CustomFormatUnmetSearch = true
```

**When enabled:**

- Checks custom format scores
- Searches for higher-scoring releases
- Upgrades based on format quality, not just resolution

**Bandwidth Impact:** ⚠️ **MEDIUM to HIGH** - depends on format strictness

---

### ForceMinimumCustomFormat

**Type:** Boolean
**Default:** `false`

Automatically remove torrents below minimum custom format score.

```toml
ForceMinimumCustomFormat = true
```

**When enabled:**

- **Deletes** torrents with insufficient custom format scores
- **Blacklists** the release
- Triggers immediate new search

**Bandwidth Impact:** ⚠️ **VERY HIGH** - aggressive re-downloading

!!! danger "Use with Caution"
    This will **delete downloaded content** if it doesn't meet your custom format requirements. Only enable if you're confident in your custom format configuration.

---

## Quality Profile Setup

### Radarr Quality Profile Example

**Goal:** Accept 1080p minimum, upgrade to 4K when available

**In Radarr:**

1. Go to **Settings** → **Profiles**
2. Create or edit a profile
3. Set **Cutoff:** 1080p
4. Enable qualities: 720p, 1080p, 2160p
5. **Upgrade Until:** 2160p
6. **Upgrade Until Custom Format Score:** (optional)

**In qBitrr:**

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
QualityUnmetSearch = true  # Search until 1080p cutoff met
DoUpgradeSearch = true  # Continue searching for 4K
SearchRequestsEvery = 1200
```

**Result:**

- Missing movies: Download any quality (720p, 1080p, or 4K)
- 720p movies: Upgrade to 1080p (cutoff)
- 1080p movies: Upgrade to 4K (ultimate goal)

---

### Sonarr Quality Profile Example

**Goal:** WEB-1080p for new episodes, upgrade to Bluray later

**In Sonarr:**

1. **Settings** → **Profiles**
2. Set **Cutoff:** WEB-1080p
3. Enable: WEB-720p, WEB-1080p, Bluray-1080p, Bluray-2160p
4. **Upgrade Until:** Bluray-2160p

**In qBitrr:**

```toml
[Sonarr-TV.EntrySearch]
SearchMissing = true
PrioritizeTodaysReleases = true  # Get new episodes fast
DoUpgradeSearch = true  # Upgrade to Bluray later
SearchRequestsEvery = 600
```

**Result:**

- New episodes: Download WEB-1080p immediately
- Older episodes: Gradually upgrade to Bluray-1080p/2160p

---

### Lidarr Quality Profile Example

**Goal:** Accept MP3-320 initially, upgrade to FLAC later

**In Lidarr:**

1. **Settings** → **Profiles**
2. Set **Cutoff:** MP3-320
3. Enable: MP3-320, FLAC
4. **Upgrade Until:** FLAC

**In qBitrr:**

```toml
[Lidarr-Music.EntrySearch]
SearchMissing = true
UseTempForMissing = true
QualityProfileMappings = {"Lossless (FLAC)" = "Lossy (MP3-320)"}
QualityUnmetSearch = true
DoUpgradeSearch = true
SearchRequestsEvery = 1800
```

**Result:**

- Missing albums: Download MP3-320 (temp profile)
- Profile switches back to Lossless
- Future searches look for FLAC upgrades

---

## Upgrade Workflows

### Workflow 1: New Library Build → Quality Improvement

**Timeline:**

**Week 1-2: Rapid Library Build**

```toml
SearchMissing = true
DoUpgradeSearch = false
UseTempForMissing = true
QualityProfileMappings = {"HD-1080p" = "SD"}
```

Result: 1000 movies downloaded (mixed quality)

**Week 3-4: Quality Baseline**

```toml
SearchMissing = true
DoUpgradeSearch = false
QualityUnmetSearch = true  # Upgrade to 1080p cutoff
UseTempForMissing = false
```

Result: 500 movies upgraded to 1080p

**Month 2+: Continuous Optimization**

```toml
SearchMissing = true
DoUpgradeSearch = true  # Always look for better
QualityUnmetSearch = true
CustomFormatUnmetSearch = true
```

Result: Gradual upgrades to 4K, better release groups, HDR

---

### Workflow 2: Seasonal TV Shows (Sonarr)

**Goal:** Get episodes fast, upgrade to Bluray when released

**During Airing Season:**

```toml
[Sonarr-OngoingTV.EntrySearch]
SearchMissing = true
PrioritizeTodaysReleases = true
DoUpgradeSearch = false
SearchRequestsEvery = 300  # Check every 5 minutes
```

Result: WEB-DL episodes available within minutes of release

**After Season Ends:**

```toml
[Sonarr-OngoingTV.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true  # Now look for Bluray
SearchRequestsEvery = 3600  # Less frequent (hourly)
```

Result: Gradual upgrade to Bluray-1080p as releases become available

---

### Workflow 3: Music Collection (Lidarr)

**Goal:** Build library with any quality, upgrade to lossless over time

**Phase 1: Accept Anything**

```toml
[Lidarr-Music.EntrySearch]
SearchMissing = true
DoUpgradeSearch = false
UseTempForMissing = true
QualityProfileMappings = {"Lossless" = "Any"}
```

**Phase 2: Target Lossless**

```toml
[Lidarr-Music.EntrySearch]
SearchMissing = true
QualityUnmetSearch = true  # Upgrade to FLAC
DoUpgradeSearch = true
UseTempForMissing = false
SearchRequestsEvery = 1800
```

---

## Troubleshooting

### Upgrades Not Happening

**Symptom:** DoUpgradeSearch is enabled but no upgrades occur

**Possible Causes:**

1. **Quality Profile:**
   - "Upgrade Until" is set to current quality
   - "Upgrade Allowed" is disabled

2. **Already at Cutoff:**
   - Media already meets cutoff quality
   - Use DoUpgradeSearch (not QualityUnmetSearch)

3. **No Better Releases:**
   - Indexers don't have higher quality
   - Check Radarr/Sonarr activity history

**Solution:**

```bash
# Check Radarr quality profile settings
curl http://localhost:7878/api/v3/qualityprofile \
  -H "X-Api-Key: YOUR_API_KEY"

# Look for:
# - "upgradeAllowed": true
# - "cutoff" vs "items" quality IDs
```

---

### Too Many Upgrades (Bandwidth Issues)

**Symptom:** Constantly downloading huge files

**Solutions:**

**Option 1: Disable Continuous Upgrades**

```toml
DoUpgradeSearch = false
QualityUnmetSearch = true  # Only upgrade to cutoff
```

**Option 2: Increase Search Delay**

```toml
SearchRequestsEvery = 3600  # Check hourly instead of every 5 minutes
```

**Option 3: Pin Quality**

In Radarr/Sonarr, set "Upgrade Until" to current quality (e.g., 1080p)

---

### Upgrades Stuck in Queue

**Symptom:** Arr shows "Queued" upgrades but nothing happens

**Possible Causes:**

1. **Indexer Rate Limits:** Too many searches too fast
2. **Download Client Full:** No space for new torrents
3. **Seeding Requirements:** Old torrent still seeding, can't replace

**Solutions:**

```toml
# Increase search delay
SearchRequestsEvery = 1200

# Enable disk space management
FreeSpace = "100G"
AutoPauseResume = true
```

---

### Custom Format Upgrades Not Working

**Symptom:** CustomFormatUnmetSearch enabled but no upgrades

**Check Custom Format Setup:**

1. **In Radarr/Sonarr:**
   - Custom formats exist
   - Formats have non-zero scores
   - Quality profile has minimum custom format score set

2. **In qBitrr:**
   ```toml
   CustomFormatUnmetSearch = true
   ```

**Debug:**

```bash
# Check movie custom format scores
curl http://localhost:7878/api/v3/movie \
  -H "X-Api-Key: YOUR_API_KEY" | jq '.[].movieFile.customFormats'
```

---

## Performance Optimization

### Reduce Indexer Load

```toml
# Increase search intervals
SearchRequestsEvery = 1800  # 30 minutes

# Disable continuous loops
SearchAgainOnSearchCompletion = false
```

### Prioritize Recent Content

```toml
# Search recent releases first
SearchByYear = true
SearchInReverse = false
```

### Limit Concurrent Searches

```toml
# Sonarr only
SearchLimit = 3  # Match Sonarr's concurrent task limit
```

---

## Best Practices

1. **Start Conservative:** Begin with `QualityUnmetSearch` only, enable `DoUpgradeSearch` later
2. **Monitor Bandwidth:** Track download volume for first week before expanding
3. **Test Custom Formats:** Validate custom format scoring before enabling `ForceMinimumCustomFormat`
4. **Respect Indexers:** Use reasonable `SearchRequestsEvery` intervals (10+ minutes)
5. **Storage Planning:** Ensure adequate free space for simultaneous old + new files
6. **Seeding Compliance:** Check private tracker rules before aggressive upgrades

---

## Related Documentation

- **[Automated Search](automated-search.md)** - Complete search configuration reference
- **[Custom Formats](custom-formats.md)** - Advanced quality filtering
- **[Quality Profiles](../configuration/quality-profiles.md)** - Profile setup and mappings
- **[Seeding Configuration](../configuration/seeding.md)** - Manage seeding during upgrades

---

## Summary

- **DoUpgradeSearch** - Continuous quality improvement (high bandwidth)
- **QualityUnmetSearch** - Targeted upgrades to cutoff (moderate bandwidth)
- **CustomFormatUnmetSearch** - Advanced format-based upgrades
- **ForceMinimumCustomFormat** - Strict enforcement (very aggressive)
- **Staged approach** - Build library first, upgrade later
- **Monitor bandwidth** and adjust `SearchRequestsEvery` accordingly
