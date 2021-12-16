# Changelog

## v2.0.0 (16/12/2021)
- [[Major] Update README.md to contain CodeQL tag](https://github.com/Drapersniper/Qbitrr/commit/13513644770b566f12188a94d2a4aed2c685192e) - @Drapersniper
- [update condition in code analysis workflow](https://github.com/Drapersniper/Qbitrr/commit/edf7425a5331a88bd3e26c10acca92ae50a07a38) - @Drapersniper
- [Break up workflows](https://github.com/Drapersniper/Qbitrr/commit/01d0004277cc511e306343b5522a36522313908a) - @Drapersniper
- [cleanup](https://github.com/Drapersniper/Qbitrr/commit/271aaf92afa3897f7770e4e6a1813438563372f6) - @Drapersniper
- [add a separator to stale log lines](https://github.com/Drapersniper/Qbitrr/commit/460fc6bbefc303b597ea4b861650c3d34cbe6de2) - @Drapersniper
- [set the log padding to be dynamically adjusted based on category names.](https://github.com/Drapersniper/Qbitrr/commit/8acc964904df7e66c5aa1283dddd4f1cebedfe9a) - @Drapersniper
- [update README.md image](https://github.com/Drapersniper/Qbitrr/commit/f575c502069378b1c46c00b49977336dd3ff9cdc) - @Drapersniper
- [Improve closing logic to gracefully close the script in a KeyboardInterrupt signal](https://github.com/Drapersniper/Qbitrr/commit/7a7ccf73a7a8696bfffae5d3bdeca31bf01a673a) - @Drapersniper
- [ - allow user to specify which are the bad msgs to remove trackers with the "RemoveTrackerWithMessage" setting field](https://github.com/Drapersniper/Qbitrr/commit/bd794380fc8a3ebf60229dcf1e95c1584af5c0e6) - @Drapersniper
- [Change logging library](https://github.com/Drapersniper/Qbitrr/commit/25d3c3c99058337f31c6ae3e0963b9cc6b251b07) - @Drapersniper
- [Change logging library](https://github.com/Drapersniper/Qbitrr/commit/75e891f1205fe510d7965f5bb6f6a9deb8805c84) - @Drapersniper
- [Fixes for bugs introduces by previous commits](https://github.com/Drapersniper/Qbitrr/commit/ee8fbafd7e54cd7355a0efa7ec409e37e85d09dd) - @Drapersniper
- [Fixes for bugs introduces by previous commits](https://github.com/Drapersniper/Qbitrr/commit/c374053e54544adfb3d3db238fcaa0a9d7e0f540) - @Drapersniper
- [Fixes for bugs introduces by previous commits](https://github.com/Drapersniper/Qbitrr/commit/8fb3be79b5286c5ac528eeffd979d065e14bc76b) - @Drapersniper
- [Clean up and finalize changes to new toml config format](https://github.com/Drapersniper/Qbitrr/commit/6f74db5b2c8b0b3141f22455a527ab00f9165fae) - @Drapersniper
- [Multiple enhancements and fixes](https://github.com/Drapersniper/Qbitrr/commit/0ea34c23337e10a0a40dc8437291c9964a88d45e) - @Drapersniper
- [add tomlkit dep now - remove toml_config before release](https://github.com/Drapersniper/Qbitrr/commit/73aff474c17de9d4fd23e7a26a7d5cca8759b3f1) - @Drapersniper
- [update config.ini references to config.toml](https://github.com/Drapersniper/Qbitrr/commit/bd2c579842bf5819d32bbda86374a448041441d6) - @Drapersniper
- [Part 1 - Migrate to TOML from INI](https://github.com/Drapersniper/Qbitrr/commit/292e692b8035c3c0f92ddea6fefa097d502b5a79) - @Drapersniper

---

## v1.1.4 (15/12/2021)


---

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