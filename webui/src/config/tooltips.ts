export const FIELD_TOOLTIPS: Record<string, string> = {
  "Settings.ConsoleLevel":
    "Level of logging; choose between CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE.",
  "Settings.Logging": "Enable writing log output to files.",
  "Settings.CompletedDownloadFolder":
    "Folder where completed downloads are stored. Replace backslashes with forward slashes.",
  "Settings.FreeSpace":
    "Desired free space threshold (use K, M, G, T suffix). Set to -1 to disable the free space guard.",
  "Settings.FreeSpaceFolder":
    "Path used when checking free space. Replace backslashes with forward slashes.",
  "Settings.AutoPauseResume":
    "Automatically pause and resume torrents in response to the free space guard.",
  "Settings.NoInternetSleepTimer":
    "Delay, in seconds, before retrying when no internet connectivity is detected.",
  "Settings.LoopSleepTimer":
    "Delay, in seconds, between processing passes when monitoring torrents.",
  "Settings.SearchLoopDelay":
    "Delay, in seconds, between media search requests.",
  "Settings.FailedCategory": "Category that marks torrents as failed.",
  "Settings.RecheckCategory": "Category that triggers recheck handling.",
  "Settings.Tagless": "Enable tagless operation when categories are not used.",
  "Settings.IgnoreTorrentsYoungerThan":
    "Ignore torrents younger than this many seconds when evaluating failures.",
  "Settings.PingURLS":
    "Hostnames used to test for internet connectivity. They are pinged frequently.",
  "Settings.FFprobeAutoUpdate":
    "Download and update the bundled ffprobe binary automatically.",
  "Settings.AutoUpdateEnabled":
    "Enable the background worker that periodically checks for qBitrr updates.",
  "Settings.AutoUpdateCron":
    "Cron expression describing when to check for updates (default weekly Sunday at 03:00).",
  "Settings.WebUIHost":
    "Interface address for the built-in WebUI. 0.0.0.0 binds on all interfaces.",
  "Settings.WebUIPort": "Port number for the built-in WebUI.",
  "Settings.WebUIToken":
    "Optional bearer token required by the WebUI/API. Leave empty to disable authentication.",

  "qBit.Disabled":
    "Disable qBitrr's direct qBittorrent integration (headless mode for search-only setups).",
  "qBit.Host": "qBittorrent WebUI host or IP address.",
  "qBit.Port": "qBittorrent WebUI port.",
  "qBit.UserName": "qBittorrent WebUI username.",
  "qBit.Password":
    "qBittorrent WebUI password. Remove this if authentication is bypassed for the host.",

  "ARR.Managed": "Toggle whether this Servarr instance is actively managed by qBitrr.",
  "ARR.URI":
    "Servarr URL, including protocol and port if needed (for example http://localhost:8989).",
  "ARR.APIKey": "Servarr API key from Settings > General > Security.",
  "ARR.Category":
    "qBittorrent category applied by the Servarr instance to its downloads.",
  "ARR.ReSearch": "Re-run searches for failed torrents that qBitrr removes.",
  "ARR.importMode":
    "Preferred import mode (Move, Copy, or Auto) when Servarr grabs completed files.",
  "ARR.RssSyncTimer":
    "Interval, in minutes, between RSS sync requests (0 disables the task).",
  "ARR.RefreshDownloadsTimer":
    "Interval, in minutes, between queue refresh requests (0 disables the task).",
  "ARR.ArrErrorCodesToBlocklist":
    "List of Servarr error messages that should trigger blocklisting and cleanup.",

  "EntrySearch.SearchMissing": "Search for missing media items.",
  "EntrySearch.AlsoSearchSpecials": "Include season 0 specials in missing searches.",
  "EntrySearch.Unmonitored": "Include unmonitored series or episodes in searches.",
  "EntrySearch.SearchLimit":
    "Maximum number of concurrent search tasks (Servarr enforces its own limits).",
  "EntrySearch.SearchByYear":
    "Order searches by the year the episode or movie first aired.",
  "EntrySearch.SearchInReverse":
    "Reverse search order (search oldest to newest instead of newest to oldest).",
  "EntrySearch.SearchRequestsEvery":
    "Delay, in seconds, between submitting individual search requests.",
  "EntrySearch.DoUpgradeSearch":
    "Search for improved releases even if a file already exists.",
  "EntrySearch.QualityUnmetSearch":
    "Search again when the quality requirements were not met.",
  "EntrySearch.CustomFormatUnmetSearch":
    "Search again when the minimum custom format score was not met.",
  "EntrySearch.ForceMinimumCustomFormat":
    "Automatically remove torrents that do not meet the minimum custom format score.",
  "EntrySearch.SearchAgainOnSearchCompletion":
    "Restart the search loop when the configured year range is exhausted.",
  "EntrySearch.UseTempForMissing":
    "Switch to temporary profiles when searching for missing media.",
  "EntrySearch.KeepTempProfile": "Do not revert to the main profile after using the temp profile.",
  "EntrySearch.MainQualityProfile":
    "Primary quality profile names, in the same order as the temporary profiles.",
  "EntrySearch.TempQualityProfile":
    "Temporary quality profile names, paired with the primary profiles.",
  "EntrySearch.SearchBySeries":
    "Search by entire series instead of individual episodes when applicable.",
  "EntrySearch.PrioritizeTodaysReleases":
    "Prioritise items released today (similar to RSS prioritisation).",

  "EntrySearch.Ombi.SearchOmbiRequests":
    "Pull pending Ombi requests when SearchMissing is enabled.",
  "EntrySearch.Ombi.OmbiURI": "Ombi server URL.",
  "EntrySearch.Ombi.OmbiAPIKey": "Ombi API key.",
  "EntrySearch.Ombi.ApprovedOnly": "Only process Ombi requests that are approved.",
  "EntrySearch.Ombi.Is4K": "Treat this Ombi configuration as 4K specific.",

  "EntrySearch.Overseerr.SearchOverseerrRequests":
    "Pull Overseerr requests when SearchMissing is enabled.",
  "EntrySearch.Overseerr.OverseerrURI": "Overseerr server URL.",
  "EntrySearch.Overseerr.OverseerrAPIKey": "Overseerr API key.",
  "EntrySearch.Overseerr.ApprovedOnly": "Only process Overseerr requests that are approved.",
  "EntrySearch.Overseerr.Is4K": "Treat this Overseerr configuration as 4K specific.",

  "Torrent.CaseSensitiveMatches":
    "When enabled, regex matches will respect case; otherwise they are case-insensitive.",
  "Torrent.FolderExclusionRegex":
    "Regex patterns that exclude folders outright (full-name match).",
  "Torrent.FileNameExclusionRegex":
    "Regex patterns that exclude individual files based on the file name.",
  "Torrent.FileExtensionAllowlist":
    "Allowed file extensions (or regex) for downloads; leave empty to allow all.",
  "Torrent.AutoDelete": "Automatically delete files that are not recognised as media.",
  "Torrent.IgnoreTorrentsYoungerThan":
    "Ignore torrents younger than this many seconds for failure handling.",
  "Torrent.MaximumETA":
    "Maximum allowed remaining ETA in seconds; values above this are considered stalled.",
  "Torrent.MaximumDeletablePercentage":
    "Upper bound for completion percentage when deciding to delete a torrent.",
  "Torrent.DoNotRemoveSlow": "Ignore slow torrents when pruning.",
  "Torrent.StalledDelay":
    "Minutes to allow stalled torrents before taking action (-1 disables, 0 is infinite).",
  "Torrent.ReSearchStalled":
    "Re-run searches for stalled torrents before or after removal depending on configuration.",
  "Torrent.RemoveDeadTrackers": "Remove trackers flagged as dead.",
  "Torrent.RemoveTrackerWithMessage":
    "Tracker status messages that should trigger tracker removal when RemoveDeadTrackers is enabled.",

  "Torrent.SeedingMode.DownloadRateLimitPerTorrent":
    "Per-torrent download rate limit in bytes per second (-1 disables the limit).",
  "Torrent.SeedingMode.UploadRateLimitPerTorrent":
    "Per-torrent upload rate limit in bytes per second (-1 disables the limit).",
  "Torrent.SeedingMode.MaxUploadRatio":
    "Maximum allowed upload ratio (-1 disables the limit).",
  "Torrent.SeedingMode.MaxSeedingTime":
    "Maximum seeding duration in seconds (-1 disables the limit).",
  "Torrent.SeedingMode.RemoveTorrent":
    "Removal policy: -1 do not remove, 1 remove on ratio, 2 remove on time, 3 remove on ratio or time, 4 remove on ratio and time.",
};

export function getTooltip(path: string[]): string | undefined {
  const joined = path.join(".");
  if (FIELD_TOOLTIPS[joined]) return FIELD_TOOLTIPS[joined];
  if (path.length > 1) {
    const withArrPrefix = ["ARR", ...path.slice(1)].join(".");
    if (FIELD_TOOLTIPS[withArrPrefix]) return FIELD_TOOLTIPS[withArrPrefix];
    const entrySearchPrefix = ["EntrySearch", ...path.slice(2)].join(".");
    if (path[1] === "EntrySearch" && FIELD_TOOLTIPS[entrySearchPrefix]) {
      return FIELD_TOOLTIPS[entrySearchPrefix];
    }
    const torrentPrefix = ["Torrent", ...path.slice(2)].join(".");
    if (path[1] === "Torrent" && FIELD_TOOLTIPS[torrentPrefix]) {
      return FIELD_TOOLTIPS[torrentPrefix];
    }
  }
  const leaf = path[path.length - 1];
  return FIELD_TOOLTIPS[leaf];
}
