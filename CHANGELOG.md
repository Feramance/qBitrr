# Changelog

## v1.1.3 (14/12/2021)


---

## v1.1.2 (14/12/2021)


---

## v1.1.1 (14/12/2021)


---

## v1.1.0 (14/12/2021)
## What's Changed
* [minor] Self updating FFprobe dependency by @Drapersniper in https://github.com/Drapersniper/Qbitrr/pull/11
  - Adds a FFProbe downloader and updater to the script - qBitrr will now watch its config folder for a probe binary
  - Updated config file to add a `Settings.FFprobeAutoUpdate` key to disable the auto-updating of FFprobe (in case you wish to manually add the binary to the config folder)
  - Adds pre-commit hooks


**Full Changelog**: https://github.com/Drapersniper/Qbitrr/compare/v1.0.9...v1.1.0
---

## v1.0.9 (13/12/2021)

---

## v1.0.8 (13/12/2021)

---

## v1.0.7 (12/12/2021)

---

## v1.0.3 (12/12/2021)
## What's Changed
- Fix a bug where torrents that are not fully available would not get marked as stale by @Drapersniper in https://github.com/Drapersniper/Qbitrr/pull/10
- Improve the value of the "Added on" on logs to reflect when a torrent is actually considered as added (Queued torrents are mostly ignored and aren't considered as added until their status change to not queued) by @Drapersniper in https://github.com/Drapersniper/Qbitrr/pull/10


**Full Changelog**: https://github.com/Drapersniper/Qbitrr/compare/v1.0.2...v1.0.3
---

## v1.0.2 (11/12/2021)
## What's Changed
* Make logging more verbose + some other minor fixes by @Drapersniper in https://github.com/Drapersniper/Qbitrr/pull/9
  - Increase verbosity of logs to show several details for every torrent line logged, these include current torrent state, when it was added, when the last activity was recorded, current progress, current availability and how much time is left on download.

  - fix a few typos and update the example image in README.md
  - Make the script early exit with an error message if `config.ini` can't be located



**Full Changelog**: https://github.com/Drapersniper/Qbitrr/compare/v1.0.1...v1.0.2
---

## v.1.0.1 (11/12/2021)
**Full Changelog**: https://github.com/Drapersniper/Qbitrr/compare/v1.0.0...v1.0.1
---

## v1.0.0 (11/12/2021)
Push current version to PyPi

## What's Changed
* Create LICENSE by @Drapersniper in https://github.com/Drapersniper/Qbitrr/pull/7

## New Contributors
* @Drapersniper made their first contribution in https://github.com/Drapersniper/Qbitrr/pull/7

**Full Changelog**: https://github.com/Drapersniper/Qbitrr/commits/v1.0.0