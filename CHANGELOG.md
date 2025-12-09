# Changelog

## v (09/12/2025)

### 🐛 Bug Fixes
- [[patch] Lidarr webui fixes](https://github.com/Feramance/qBitrr/commit/0884fc77e152c45057daaeb230a940217aeb4874) - @Feramance

### 🔧 Maintenance
- [Added some more assets and update release workflow](https://github.com/Feramance/qBitrr/commit/4a4f718163c472175994d33ec6f4e2d33ac31c65) - @Feramance

---

## v (28/11/2025)

### 🐛 Bug Fixes
- [[patch] Lidarr webui fixes](https://github.com/Feramance/qBitrr/commit/0884fc77e152c45057daaeb230a940217aeb4874) - @Feramance

### 🔧 Maintenance
- [Added some more assets and update release workflow](https://github.com/Feramance/qBitrr/commit/4a4f718163c472175994d33ec6f4e2d33ac31c65) - @Feramance

---

## v5.5.5 (25/11/2025)

### 🚀 Features
- [[patch] Add qBitrr logo to README, WebUI header, and favicon](https://github.com/Feramance/qBitrr/commit/3ed6e223e7de65e8c1483207338cc96ca020415f) - @Feramance

### 🐛 Bug Fixes
- [[patch] Automated DB recovery](https://github.com/Feramance/qBitrr/commit/40025aea9d5621dcbe7d5031b051fc6127def7ec) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/60e9e33e9a76582796b81d1ab8f3a111ca27d095) - @Feramance

### 🔧 Maintenance
- [Enhance database lock retry logic with automatic corruption recovery](https://github.com/Feramance/qBitrr/commit/c0308901a6d1d2cc6deeaf7e80dfc871895cd6a7) - @Feramance

---

## v5.5.3 (24/11/2025)

### 🚀 Features
- [fix: Add defensive error handling for API responses, database initialization, and process management](https://github.com/Feramance/qBitrr/commit/edd6897a016b25dc29e65f1508a418faa0d99ab6) - @Feramance
- [Add PyarrResourceNotFound handling for Sonarr episode and Lidarr album re-searches](https://github.com/Feramance/qBitrr/commit/3ad77ae2432974573bbea35daaba61d9e1f53448) - @Feramance

### 🐛 Bug Fixes
- [[patch] General updates and fixes](https://github.com/Feramance/qBitrr/commit/e55d1e36bfab87ed89c372bd87325e9b90a34006) - @Feramance
- [Fix excessive delay and memory leak when queue items are already removed from Arr](https://github.com/Feramance/qBitrr/commit/f1f2c58d65809e1b39467d051f95dd7123c10566) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/eb3e43997f64f94d8b08e915bdaa45f7ad2e036d) - @Feramance

### 🔧 Maintenance
- [Build(deps-dev): Bump typescript-eslint from 8.46.3 to 8.47.0 in /webui (#215)](https://github.com/Feramance/qBitrr/commit/64553a1187d1a74895c05efb73d9f1b8ff1cb593) - @Feramance
- [Build(deps-dev): Bump @vitejs/plugin-react from 5.1.0 to 5.1.1 in /webui (#217)](https://github.com/Feramance/qBitrr/commit/d71c4695aa4bb6a44a40ba1667803ebe058147c8) - @Feramance
- [Build(deps): Bump react-hook-form from 7.66.0 to 7.66.1 in /webui (#216)](https://github.com/Feramance/qBitrr/commit/db30128c62476812b158caacee59dadc23790053) - @Feramance
- [Build(deps-dev): Bump @types/node from 24.10.0 to 24.10.1 in /webui (#213)](https://github.com/Feramance/qBitrr/commit/71408a598cf7982a6b86219ffa22abdadf985a70) - @Feramance
- [Build(deps): Bump @mantine/dates from 8.3.7 to 8.3.9 in /webui (#214)](https://github.com/Feramance/qBitrr/commit/faabc6198dc89c137a791932d9c84db51fa3b508) - @Feramance
- [Build(deps): Bump @mantine/core from 8.3.7 to 8.3.9 in /webui (#212)](https://github.com/Feramance/qBitrr/commit/a17e6e2d038420356d6eabdec14943618f1edb41) - @Feramance
- [bug: Initialization with qbittorrent down failure](https://github.com/Feramance/qBitrr/commit/8bcaf89bf57a715b9c360e73eaae0ab8f43991ea) - @Feramance
- [Bump react and @types/react in /webui (#194)](https://github.com/Feramance/qBitrr/commit/29aa21b13f13cb53a9051929b97e2e01e0810fa9) - @Feramance
- [Bump react-dom and @types/react-dom in /webui (#196)](https://github.com/Feramance/qBitrr/commit/0a2858c36f836020e222067e7b9fcadafe0cc1a0) - @Feramance

---

## v5.5.2 (22/11/2025)

### 🐛 Bug Fixes
- [[patch] Trigger automated release workflow](https://github.com/Feramance/qBitrr/commit/b8b6c9533d23255acb6d872f0a5ebb8dfc985763) - @Feramance
- [Fix KeyError for missing 'customFormatScore' in Radarr movie file data](https://github.com/Feramance/qBitrr/commit/41f99b3add1d1b507e9fe20dfbc537bbfe3e1f46) - @Feramance

---

## v5.5.1 (22/11/2025)

### 🚀 Features
- [Add retry logic to database connection attempts](https://github.com/Feramance/qBitrr/commit/93239095b02c4ba306d2f9e095ab1c03f4a1f06f) - @Feramance
- [Add automated SQLite error handling and recovery system](https://github.com/Feramance/qBitrr/commit/a2ce47913ed816917444f7a48a4ea62f0331450a) - @Feramance
- [Add reason-based search ordering to Sonarr series searches](https://github.com/Feramance/qBitrr/commit/4ef2ad9be2e229681eac322aab978bf7755218fb) - @Feramance
- [Add reason-based prioritization to today's releases search](https://github.com/Feramance/qBitrr/commit/82f48999cafeff7b83ba9b2e10500af151ccc444) - @Feramance
- [Add reason-based search prioritization for Sonarr/Radarr/Lidarr](https://github.com/Feramance/qBitrr/commit/f72237da0c1b18eae6156c3c1d294ba4a10fdbdb) - @Feramance
- [docs: Add temp quality profile improvements to README](https://github.com/Feramance/qBitrr/commit/798c75da73e032940e6fa529894ebf2fad5959b0) - @Feramance
- [docs: Add branch-specific features to README](https://github.com/Feramance/qBitrr/commit/0abc7800784d19477b03ceea037aa884dc94a550) - @Feramance
- [Add automatic process restart with crash loop protection and WebUI configuration](https://github.com/Feramance/qBitrr/commit/9a47262fd9526abcf1ec9fd4c664b12443f4ff10) - @Feramance
- [Fix: Implement local pagination for grouped instance views](https://github.com/Feramance/qBitrr/commit/63092f0f14e252ea385f9fbb7b4a63b675096a02) - @Feramance
- [Fix: Implement proper artist-based pagination for Lidarr grouped view](https://github.com/Feramance/qBitrr/commit/b4ba800e72f3f3385af89725c649c4b267bc47ad) - @Feramance

### 🐛 Bug Fixes
- [Fix KeyError for missing 'hasFile' key in episode data](https://github.com/Feramance/qBitrr/commit/98d18ad7d5fdf552acc6ee7b135cd0aabcbf673e) - @Feramance
- [Fix AttributeError in PyarrResourceNotFound exception handling](https://github.com/Feramance/qBitrr/commit/29f7826ffb90e2409b1ff308830c2df95d25e8c6) - @Feramance
- [fix: Handle qBittorrent connection failures during Arr instance initialization](https://github.com/Feramance/qBitrr/commit/b8125e1858ca9795e8bd5e787549d10d96f1b65d) - @Feramance
- [fix: Simplify log view default selection to prioritize All Logs](https://github.com/Feramance/qBitrr/commit/1a4eba165c33c78e482321705e922e9d0e263024) - @Feramance
- [Fixed make process and python versioning](https://github.com/Feramance/qBitrr/commit/5ba1c9ffa68cd918f5851b4f2d6b4e9a9bbd24cf) - @Feramance
- [Frontend: Fix config view seeding fields and enforce Arr naming conventions](https://github.com/Feramance/qBitrr/commit/468824d343170d1238f4732a6255096b4d8332dc) - @Feramance
- [Frontend: Fix Lidarr tracks table column widths for consistency](https://github.com/Feramance/qBitrr/commit/7d90ef9b647c7785214ebb8ee4a3daa27f4e3a89) - @Feramance
- [Frontend: Fix Lidarr tracks table column widths for consistency](https://github.com/Feramance/qBitrr/commit/b6e182299c890c8b877ffad0a8074f841e2ee466) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/6360501f834a3ec6f166b48c4f369be5b2f19529) - @Feramance
- [docs: Integrate branch features into main README](https://github.com/Feramance/qBitrr/commit/9b0bcaa078d323bf148f00cdf29db1899d79f029) - @Feramance

### ♻️ Refactoring
- [Refactor: Use dictionary internally for quality profile mappings](https://github.com/Feramance/qBitrr/commit/85e10fa515290f23a35548611091037755e590e4) - @Feramance

### 🎨 Styling
- [Frontend: Bring instance views to feature parity with aggregate views](https://github.com/Feramance/qBitrr/commit/67828ca56197845691a827d7b2b3ebe01ac3e3d7) - @Feramance

### 🔧 Maintenance
- [Removed extra files](https://github.com/Feramance/qBitrr/commit/be4c39fd2c452cafbe2e03abdf08220d2673feeb) - @Feramance
- [Complete database connection retry coverage](https://github.com/Feramance/qBitrr/commit/e245e1a8948b080c29d96abaf89b12b45b80af04) - @Feramance
- [Bump actions/checkout from 5 to 6 (#209)](https://github.com/Feramance/qBitrr/commit/3107928ec31c943b4e403a83bf11351f04f9b881) - @Feramance
- [Fix: Correct Lidarr temp profile logic to operate at artist level, not album level](https://github.com/Feramance/qBitrr/commit/691aa5feff2aa3546e3030da94636e43a5909f78) - @Feramance
- [Fix: Only apply temp profiles to missing content, not quality/CF unmet searches](https://github.com/Feramance/qBitrr/commit/0ece118b31ec8caeb73376731dd8fca4bfe106d8) - @Feramance
- [Fix: Ensure QualityProfileMappings serializes as inline dict instead of TOML section](https://github.com/Feramance/qBitrr/commit/3b8b7961c8632918b3dbb574673be15ee5bd562c) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/2082d422abaac54d2d9f05498f6ec8550d0ac977) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/de3564be21e37385314d7181473d779a91f57679) - @Feramance
- [Fix: Support new QualityProfileMappings config format in addition to legacy lists](https://github.com/Feramance/qBitrr/commit/280ea784ee8e11363b57b7b64728336a4c4df155) - @Feramance
- [Apply black formatting to temp quality profile logging changes](https://github.com/Feramance/qBitrr/commit/88be7f3bd40e3daa974f531f48b09d01c68a644c) - @Feramance
- [Enhance logging for temp quality profile feature with detailed initialization, parsing, and switching logs](https://github.com/Feramance/qBitrr/commit/452554d0c470808f364df46d92bef9c4a25daede) - @Feramance
- [Apply read_uncommitted mode to search activity database and unignore log files](https://github.com/Feramance/qBitrr/commit/04be56d4e2b81a86eb5339218106fb4b7933f636) - @Feramance
- [Enable read_uncommitted mode for SQLite databases to reduce lock contention](https://github.com/Feramance/qBitrr/commit/b4b428eacec73eebebf76d137c001c086c11090c) - @Feramance
- [Simplify log viewer by removing 'All Logs' option and defaulting to 'All.log' file](https://github.com/Feramance/qBitrr/commit/2048fc7af6719d9ae49669d1c381bf3a6bef8933) - @Feramance
- [Enforce Arr instance naming format: (Rad|Son|Lid)arr-.+](https://github.com/Feramance/qBitrr/commit/e8b438ac05d55237e2662830af988053daf613c5) - @Feramance
- [Fix: Restore instance name field in Arr config modals](https://github.com/Feramance/qBitrr/commit/63e1fd17e6cce1ca01c0013b385950a8213fac0b) - @Feramance
- [Fix: Resolve Arr config data not loading in modal popups](https://github.com/Feramance/qBitrr/commit/639ca10253de39c40c9f12b4b4c981f164113528) - @Feramance
- [Lower minimum Python version requirement from 3.12 to 3.11 for broader compatibility](https://github.com/Feramance/qBitrr/commit/1c7838ac0b1ff9adccef0e5fc4514c4015873391) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/f1cffdfb092efb368a3c3f4e68a6873fc5da3737) - @Feramance
- [Fix: Update package-lock.json and broaden .dockerignore exclusions](https://github.com/Feramance/qBitrr/commit/6e77b180c906610cc72fc7abe73582eba7b710ea) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/35f9a543535c909c025c097b71bda43d7c328975) - @Feramance
- [Remove unecessary files](https://github.com/Feramance/qBitrr/commit/ec6da9bdb55a1b18aa3743ee2745da2f6e7365e3) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/40f3299c0c8221d127f257e460b5e07b00b8458f) - @Feramance
- [Bump js-yaml from 4.1.0 to 4.1.1 in /webui (#208)](https://github.com/Feramance/qBitrr/commit/dd03c806cfd6aa55c4ad4c3bf0c6520f21cabbcd) - @Feramance
- [Delete FINAL_TEST_RESULTS.md](https://github.com/Feramance/qBitrr/commit/01a4078062630377ebd8c40c5f4496550b9a2b3a) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/0ad31376335dce195d2dbce486ef2fcb807f5ad2) - @Feramance
- [Fix: Show Lidarr grouped view info even with single page](https://github.com/Feramance/qBitrr/commit/a945333eaeb5a7c1fbc18e38fdc6735b5fa71b02) - @Feramance
- [[pre-commit.ci] auto fixes from pre-commit.com hooks](https://github.com/Feramance/qBitrr/commit/f9020683afe36f371621d71b6da8dcfc28f28686) - @Feramance

---

## v5.4.5 (05/11/2025)

### 🐛 Bug Fixes
- [[patch] Sync changelog and release system improvements](https://github.com/Feramance/qBitrr/commit/dd7f7263026b05cdd7e5ed267d05565ecd173845) - @Feramance
- [[patch] Fix version](https://github.com/Feramance/qBitrr/commit/7be1c1bd2be57e79b1c4b57fd5ea5e1e0af3b05f) - @Feramance
- [Fix changelog generation with populated entries and robust fallback mechanism](https://github.com/Feramance/qBitrr/commit/23c27716abc019f5daabdafde5e0eb3c97397857) - @Feramance
- [Prevent duplicate release creation in workflow](https://github.com/Feramance/qBitrr/commit/a8e2c2dd60f7c6f3cca18b391674d011977528c5) - @Feramance

### 🚀 Features
- [Add automated GitHub release notes population from changelog](https://github.com/Feramance/qBitrr/commit/4c6b58a76eee1048cc5930ba30db81a74606941b) - @Feramance
- [Add grouped changelog with icons for features, fixes, and other commit types](https://github.com/Feramance/qBitrr/commit/f11382245a4561efe1d1b97e9ebf83032fbb732b) - @Feramance

---

## v5.4.4 (05/11/2025)
### 🚀 Features
- [Add binary download support for auto-updates](https://github.com/Feramance/qBitrr/commit/59421749450fca0f470f63a6094d358daa77d00b) - @Feramance
- [Implement GitHub release-based auto-update with installation type detection](https://github.com/Feramance/qBitrr/commit/1a3f9936a3f7beb7aaa3116c1d71b046109d2c4f) - @Feramance

### 🐛 Bug Fixes
- [[patch] Auto-update system improvements complete](https://github.com/Feramance/qBitrr/commit/d7a14a56e7963367f7b51cc9404a382be385d7c9) - @Feramance
- [[patch] Fix version comparison to normalize candidate before parsing](https://github.com/Feramance/qBitrr/commit/ed6d85ffc90bffb9f33eff967a12243d0f707f64) - @Feramance
- [[patch] Enhanced auto update flow](https://github.com/Feramance/qBitrr/commit/ea76e70bad19d12253768fd59dd5fb5a309742cf) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/b9120ef361299c6170679406aedaa78e299c14b2) - @Feramance
- [Document supported binary platforms and improve error messages](https://github.com/Feramance/qBitrr/commit/fb4f9b0dc28846bc2289ebe4e0e23405e58a110a) - @Feramance

### 🔧 Maintenance
- [Changelog fixes](https://github.com/Feramance/qBitrr/commit/1bb74b40d18813b7b3bb727b8e4809233606de1c) - @Feramance
---

## v5.4.3 (05/11/2025)
### 🐛 Bug Fixes
- [[patch] Service worker support for auth proxies and Docker](https://github.com/Feramance/qBitrr/commit/122bc909f9296aac25b4fe115d3438b5162d3c37) - @Feramance
- [Fix service worker detection behind authentication proxies](https://github.com/Feramance/qBitrr/commit/f097b52617d984a1fbff7d9fb2be42f502ac57dc) - @Feramance
- [[patch] Fix service worker registration for HTTPS reverse proxy](https://github.com/Feramance/qBitrr/commit/11767b0f6546397763d2b47420841ca58ffb4eda) - @Feramance

### 🔧 Maintenance
- [Serve service worker directly instead of redirecting](https://github.com/Feramance/qBitrr/commit/d8d162988e5578d159245227e6d71f7f9a16129b) - @Feramance
---

## v5.4.2 (05/11/2025)
### 🐛 Bug Fixes
- [[patch] Ensure static files are included in Docker pip install](https://github.com/Feramance/qBitrr/commit/c8edde2e6302dd841a136ded39ba6d9584b239eb) - @Feramance
- [[patch] Fix PyPI package missing WebUI static files](https://github.com/Feramance/qBitrr/commit/3c9a0475c267dad874b39383477f53c4fbeaf7bf) - @Feramance

### 🔧 Maintenance
- [PKG update](https://github.com/Feramance/qBitrr/commit/bc2d69aa9411478bb1af2eea5d0f98d5ba149ce5) - @Feramance
---

## v5.4.1 (05/11/2025)
### 🐛 Bug Fixes
- [[patch] Fix KeyError: 'monitored' when Sonarr API returns incomplete episode data](https://github.com/Feramance/qBitrr/commit/79216f5736409047832d868642ee5a719f224c1a) - @Feramance
- [[patch] Fix service worker 404 by adding /sw.js route](https://github.com/Feramance/qBitrr/commit/c428cbf902a4893271c26355d251e558f09f59d8) - @Feramance
---

## v5.4.0 (04/11/2025)
### 🚀 Features
- [[minor] Sonarr-filters-and-config-improvements (#197)](https://github.com/Feramance/qBitrr/commit/ee619ecced6f54cdb7f6a1b48dce1473c271405f) - @Feramance
---

## v5.3.3 (04/11/2025)
### 🐛 Bug Fixes
- [[patch] Fix version... again... again](https://github.com/Feramance/qBitrr/commit/16fd5dbf056cac111e148ca7aa1ef06a97df7084) - @Feramance
- [[patch] Fix version... again](https://github.com/Feramance/qBitrr/commit/cefeded5dcc8d29207b4576308411842db2966f5) - @Feramance
- [[patch] Fix version](https://github.com/Feramance/qBitrr/commit/2b3f2a194b4640b4361cc937c459262434048911) - @Feramance
- [[patch] workflow fixes](https://github.com/Feramance/qBitrr/commit/0c3d3be3c910c7d4e26baa6f032d973e4d983ba9) - @Feramance
- [[patch] Fix release flow](https://github.com/Feramance/qBitrr/commit/d9606cca38198988045c5fa4581c22f4b4be327d) - @Feramance
- [[patch] documentation and auto update fixes](https://github.com/Feramance/qBitrr/commit/d15763f881195e7edc4fd3967145b6f88293f243) - @Feramance
- [Fix version](https://github.com/Feramance/qBitrr/commit/17d93798b4b388bf4a272c93d8a7143f925a4add) - @Feramance
- [[patch] meta: enhance project metadata with comprehensive keywords and URLs](https://github.com/Feramance/qBitrr/commit/7b7f0bc76bed4d505df58e2f6f0143edfc8e33a6) - @Feramance
- [[patch] docs: comprehensive documentation overhaul with feature deep dives, API reference, and systemd guidance](https://github.com/Feramance/qBitrr/commit/1a41c4c0d579a48e7374a60d883fb01d17686c02) - @Feramance
- [Fix auto-update and manual update restart mechanism](https://github.com/Feramance/qBitrr/commit/4c3048849e6cb7e095cd63f726ad4b07857ffd49) - @Feramance
- [Fixed got it button on changelog screen](https://github.com/Feramance/qBitrr/commit/4e5ceb15576338c49a31195260f20b72e6441e83) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/ed650dc13eccc1904cb81d48f8d92c972e5746ab) - @Feramance
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/8dd7a3b19e9acf2a1e867a5b375d9cf4acd3d4ce) - @Feramance

### 🔧 Maintenance
- [Remove redundant button from update window](https://github.com/Feramance/qBitrr/commit/e40c919d0e93b8f329d2d8a414229f1d72d415ae) - @Feramance
- [Contribution documentation](https://github.com/Feramance/qBitrr/commit/ed3b4a0765e77a36b84b308f25a476bf32ccaece) - @Feramance
---

## v5.3.2 (04/11/2025)
### 🐛 Bug Fixes
- [[patch] Fix search reason filter not working in Sonarr view](https://github.com/Feramance/qBitrr/commit/a068d9b980e16ea4b77d81b84f7a816715d8fe93) - @Feramance
---

## v5.3.1 (04/11/2025)
### 🐛 Bug Fixes
- [[patch] fixed changelog fetch tag](https://github.com/Feramance/qBitrr/commit/20f30d7dfa90c2262d8196e6834a2e340d869171) - @Feramance
---

## v5.3.0 (04/11/2025)
### 🚀 Features
- [[minor] Fixed PyPi version](https://github.com/Feramance/qBitrr/commit/01aee8713cab1e899a50cd2a4da644edb818d7f7) - @Feramance
- [[minor] Prepare release with first-launch welcome popup feature](https://github.com/Feramance/qBitrr/commit/0b2cf6b2283c69323699f7dd3d7f2c89a0d87cd2) - @Feramance
- [[minor] Add comprehensive Lidarr support with full feature parity (#190)](https://github.com/Feramance/qBitrr/commit/37fef92d60ee908c966696d72568fb727344cb82) - @Feramance
- [Add first-launch welcome popup with version-specific changelog](https://github.com/Feramance/qBitrr/commit/b5d09050cc8be5f44860e93486890ad669045144) - @Feramance
- [Add visual feedback for Arr rebuild operations in process chips](https://github.com/Feramance/qBitrr/commit/24dc87ef741b41b045ec2323e4c1e61eaed8d92a) - @Feramance
- [Add filtered count display for manual search and reason filters in Arr views](https://github.com/Feramance/qBitrr/commit/3b266c7e1e4a1d45d9a870920b81e2fa661f16e0) - @Feramance
- [Add smart data refresh infrastructure for WebUI performance optimization](https://github.com/Feramance/qBitrr/commit/a2d5ea65efb6fec68ff0b81a7b912f29af136c0c) - @Feramance
- [Add Reason column to Lidarr track tables in grouped views](https://github.com/Feramance/qBitrr/commit/6084721f0cee9f55adcd3146eb1939f0e17d72c8) - @Feramance
- [Add comprehensive debug logging for track population](https://github.com/Feramance/qBitrr/commit/136010d950fe2a14e60836b68afd14654c84ea54) - @Feramance
- [Add detailed logging for Lidarr track storage](https://github.com/Feramance/qBitrr/commit/c3bcfbbbe84fff98baf0ddcfea8cb0df655add88) - @Feramance
- [Add missing TrackFilesModel import to fix Lidarr track storage](https://github.com/Feramance/qBitrr/commit/f3da6f15f0044aefb21825cc699b6245ca91565a) - @Feramance
- [Add flat mode track display for Lidarr views](https://github.com/Feramance/qBitrr/commit/57634bda1463053cbc11909b1a13a554d3766469) - @Feramance
- [Add database-backed track storage for Lidarr albums](https://github.com/Feramance/qBitrr/commit/02447456b694b7e120aacc5efa9549c561088241) - @Feramance
- [Add track-level display to Lidarr hierarchy view](https://github.com/Feramance/qBitrr/commit/f8658d9769bd6b50c662568ff2ee4b6c39c1568e) - @Feramance
- [Add live WebUI settings to Config view](https://github.com/Feramance/qBitrr/commit/776c9ae3c507ca6ab10adba1fdfdb40126154fa4) - @Feramance
- [Add Group by Artist configuration for Lidarr views](https://github.com/Feramance/qBitrr/commit/9d1bd0d7d8b28a8803140a65057378ebfa47003d) - @Feramance
- [Add Group by Artist configuration for Lidarr views](https://github.com/Feramance/qBitrr/commit/b580d610744f00d665f07e49dd4d44104fe05953) - @Feramance
- [Add 'All Logs' view to combine all log outputs](https://github.com/Feramance/qBitrr/commit/da412b9d1bc5b14eebee72194f26b90b1bc94914) - @Feramance
- [Add debug logging to diagnose auto-scroll issue](https://github.com/Feramance/qBitrr/commit/f809dfc5ad20cb9ddd7a40cff81965fabe18b2c0) - @Feramance
- [Add debug logging to diagnose scroll position issue](https://github.com/Feramance/qBitrr/commit/8009f8bd4e81aca549f0dea72495c99aa0f14b51) - @Feramance
- [Add MutationObserver and extensive debug logging for scroll investigation](https://github.com/Feramance/qBitrr/commit/7356123abc7926ee8b1fc74555f99a2fcb75f4a4) - @Feramance

### 🐛 Bug Fixes
- [Fix infinite loop in loadAggregate caused by circular dependencies](https://github.com/Feramance/qBitrr/commit/981fc639f4eaaf1591a93cbed77e15abd519468a) - @Feramance
- [Fix constant refreshing in Sonarr and Lidarr grouped views](https://github.com/Feramance/qBitrr/commit/06d39b30f44a2d25cfa86b6b044b1e6cb0acafaf) - @Feramance
- [Fix reason assignment logic and enhance WebUI with checkmarks and mobile responsiveness](https://github.com/Feramance/qBitrr/commit/2708fe7c4081b279c26de70b18285dd94757256d) - @Feramance
- [Fix missing database table creation for Radarr](https://github.com/Feramance/qBitrr/commit/6643a159b26414c468529567a5783727bdea571c) - @Feramance
- [Fix FreeSpaceManager._get_models() return tuple size](https://github.com/Feramance/qBitrr/commit/28e3b53d7bdda7fa8b04bd364a11cf34d66c3a35) - @Feramance
- [Fix Lidarr artist name extraction to support multiple API field names](https://github.com/Feramance/qBitrr/commit/8fb7da12634db4d8814b1cd669d61d55c39caeb9) - @Feramance
- [Fix track deletion to use bound model when removing albums](https://github.com/Feramance/qBitrr/commit/b295c748b8a9d320533dc57f3b313c334bb544da) - @Feramance
- [Fix WebUI to use bound TrackFilesModel from arr instance](https://github.com/Feramance/qBitrr/commit/d196fa5da123f29c69f95f131c7e737640ff6d96) - @Feramance
- [Fix TrackFilesModel database binding for Lidarr](https://github.com/Feramance/qBitrr/commit/e0614380774d94d59e98d1d07bafe3964d2bd151) - @Feramance
- [Fix Lidarr track fetching by using allArtistAlbums parameter](https://github.com/Feramance/qBitrr/commit/96370b87a939b174a1bcd07e3d42a926b9210e58) - @Feramance
- [Fix Lidarr track fetching to include media data during database sync](https://github.com/Feramance/qBitrr/commit/6f6686bbf62290091d48b491904929d034612384) - @Feramance
- [Fix Lidarr instance view to display track tables in grouped mode](https://github.com/Feramance/qBitrr/commit/4198f525c0bd1fd220389bed281f900325c6bed7) - @Feramance
- [Fix table re-rendering with StableTable component and React.memo optimization](https://github.com/Feramance/qBitrr/commit/b06a7d9c45375d41d3617f72a4d89ca3f89eb65c) - @Feramance
- [Fix table flashing on auto-refresh in arr views by skipping loading state for background updates](https://github.com/Feramance/qBitrr/commit/7af547f1b36e21c87b82a62c2ee88a8c87058e9c) - @Feramance
- [Fix All.log handler to work with propagate=False](https://github.com/Feramance/qBitrr/commit/e90131b16c8907ed238fed0c611123e10cb9616d) - @Feramance
- [Fix All Logs sorting for concatenated log entries](https://github.com/Feramance/qBitrr/commit/8903a8001d57ac8ee4c1c1dfcbfa79b142c03600) - @Feramance
- [Fix chronological sorting in 'All Logs' view](https://github.com/Feramance/qBitrr/commit/e4d687ce75d1b4d3b2f3457ad152a070c51cfb8c) - @Feramance
- [Fix auto-scroll by directly setting scrollTop to scrollHeight](https://github.com/Feramance/qBitrr/commit/df9edf19a827367d841a00f218ba392d13cf8115) - @Feramance
- [Fix logs view height and auto-scroll to properly display log tail](https://github.com/Feramance/qBitrr/commit/8af8e7b520d704ce9ca5fee0df84e4098f523f21) - @Feramance
- [Fix ANSI-to-HTML: preserve newlines instead of converting to br tags](https://github.com/Feramance/qBitrr/commit/f2de9f91f96a5b574f7da6ce5d51542d576e441b) - @Feramance
- [Fix TypeScript linting errors in LogsView](https://github.com/Feramance/qBitrr/commit/ce27d26d0ef88c82c31304f6888ad5bb283ecb5a) - @Feramance
- [Fix logs auto-scroll to reliably scroll to bottom](https://github.com/Feramance/qBitrr/commit/dbe387432549694c0e3302c63ffc36e2c3a5dfee) - @Feramance
- [Fix WebUI logs auto-scroll and add cache clearing on config save](https://github.com/Feramance/qBitrr/commit/74797853540e98b0b945b1f28bf6a0d5ccb7f108) - @Feramance
- [Fix Sonarr database population when using series search mode](https://github.com/Feramance/qBitrr/commit/4cc022c20282db9e583a5a6228bc80c5695d184e) - @Feramance
- [Fix SonarrView data loading - add missing useMemo dependency](https://github.com/Feramance/qBitrr/commit/917918c4c3c7f00480a786dcb0ced40ea2fa7094) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/08d8d1de566c0229e5da7545fbfe0ad767aaf35d) - @Feramance
- [docs: Document unified All.log file solution](https://github.com/Feramance/qBitrr/commit/4cdac57a55703cd81a06e80e6f4462605abb2a6c) - @Feramance
- [docs: Document concatenated log entries fix](https://github.com/Feramance/qBitrr/commit/35d546556567faef41900b2a4b8254dd46b7270c) - @Feramance
- [docs: Update progress log with All Logs chronological sorting fix](https://github.com/Feramance/qBitrr/commit/5fc63efbab8518dca429fb0246f507c9698b8137) - @Feramance
- [Document final Mantine hook solution](https://github.com/Feramance/qBitrr/commit/6f6d0cf35b9796d41a07bbba2b62b6352d2e923c) - @Feramance
- [Document root cause and fix for scroll overflow issue](https://github.com/Feramance/qBitrr/commit/5915df62d3dd241225563c80de46eaaf0985bd3b) - @Feramance
- [Document final status of LogsView fixes in progress log](https://github.com/Feramance/qBitrr/commit/c8e4042af2d7e89836f7c93a8d27fd945d882989) - @Feramance

### ♻️ Refactoring
- [Refactor: remove pointless variables that are always true](https://github.com/Feramance/qBitrr/commit/4b8ab456f6bd6f28aff295d275c666f7e2e60854) - @Feramance
- [Refactor database population to separate from search filtering](https://github.com/Feramance/qBitrr/commit/de8905efb8c1f38bb14131abd13b29155134f05f) - @Feramance

### 🎨 Styling
- [Make WebUI settings fully live and improve tab loading responsiveness](https://github.com/Feramance/qBitrr/commit/3f4e596ea3e5e7732549ab355877703438cdab34) - @Feramance

### 🔧 Maintenance
- [Merge branch 'master' of https://github.com/Feramance/qBitrr](https://github.com/Feramance/qBitrr/commit/110154577b3b715d28b0420192bc86a0b167d958) - @Feramance
- [Also delete WAL and SHM files when rebuilding Arr instances](https://github.com/Feramance/qBitrr/commit/dc4910d3b6c0617dda9878491430f825b42a118a) - @Feramance
- [Delete database files when rebuilding Arr instances](https://github.com/Feramance/qBitrr/commit/960f85133bb2a3bdf5a64658f96fd29b8395cfbd) - @Feramance
- [Remove 'Scheduled search' reason from frontend and backend](https://github.com/Feramance/qBitrr/commit/2720161f9d5845ba936990af58efeae581f7858e) - @Feramance
- [Integrate smart data refresh into Radarr, Sonarr, and Lidarr views](https://github.com/Feramance/qBitrr/commit/9bda9d93b5f8b54cc3f03921f88df1e1ef239e06) - @Feramance
- [Fix: Use get_tracks() API to fetch track data](https://github.com/Feramance/qBitrr/commit/6c9b1f2de5d450cb581b686e7498bf709b861f22) - @Feramance
- [Fix: Handle dict response from get_album API call](https://github.com/Feramance/qBitrr/commit/77ee6dfd231cb2b4e6f8576f1a64bbca839eccba) - @Feramance
- [Fix: Fetch full album details to populate track data](https://github.com/Feramance/qBitrr/commit/6a66be06b194024a273050572ba64c8f54d1f14e) - @Feramance
- [Fix: Set series_file_model to None for Lidarr](https://github.com/Feramance/qBitrr/commit/95011bd1af0ce7ed44f86ae1c2d57c6d3f64dedf) - @Feramance
- [Complete Lidarr artist database population](https://github.com/Feramance/qBitrr/commit/b4992613c5a9b5f08aafd70488222a458807dd0f) - @Feramance
- [Update Lidarr frontend to work with nested album structure matching Sonarr pattern](https://github.com/Feramance/qBitrr/commit/3b6941e815083968181846a4b73ceaeaf1caaab7) - @Feramance
- [Restructure Lidarr album API to match Sonarr's nested format with track totals](https://github.com/Feramance/qBitrr/commit/9dc6995d16a1de0b15cd5f947a29c689a8db3249) - @Feramance
- [Simplify Lidarr API by always including tracks](https://github.com/Feramance/qBitrr/commit/ecf729a091c6d275e499024b22587fc87f4798cf) - @Feramance
- [Prevent unnecessary re-renders by only updating timestamp when data changes](https://github.com/Feramance/qBitrr/commit/e3e4c99596b2f2f9e8c4209688540e3c18c4bf1d) - @Feramance
- [Style react-logviewer search bar to match dark theme](https://github.com/Feramance/qBitrr/commit/c425465ad975ba96c3151de219723ce6b5b7d775) - @Feramance
- [Merge branch 'master' into Lidarr-Support](https://github.com/Feramance/qBitrr/commit/89cb13a2db0bf8b13e89a1ed3d71d3c8a98c4fa8) - @Feramance
- [Bump react-hook-form from 7.65.0 to 7.66.0 in /webui (#195)](https://github.com/Feramance/qBitrr/commit/830a7e20b9cbaaee314e55d328b05c00e2d3017d) - @dependabot
- [Bump globals from 16.4.0 to 16.5.0 in /webui (#193)](https://github.com/Feramance/qBitrr/commit/ae3a1f7e077cf1fa50deefd15bc931cc84cedee8) - @dependabot
- [Bump eslint from 9.38.0 to 9.39.0 in /webui (#192)](https://github.com/Feramance/qBitrr/commit/101631806dccf1b5495348df114b9d93ae15cfa5) - @dependabot
- [Bump @eslint/js from 9.38.0 to 9.39.0 in /webui (#191)](https://github.com/Feramance/qBitrr/commit/048ea44489825e8787cb76f7a4159fc8c0081c62) - @dependabot
- [Replace runtime log merging with unified All.log file](https://github.com/Feramance/qBitrr/commit/ff8bf20d2bffb021891e0f3169073479ff449315) - @Feramance
- [Merge all log files chronologically for 'All Logs' view](https://github.com/Feramance/qBitrr/commit/eda1b67ae0a32fb51a84e9929d106bd0dc14afc9) - @Feramance
- [Change 'All Logs' to return Main.log (full combined output)](https://github.com/Feramance/qBitrr/commit/d67cdd0195ef99107c470e96cb48cd5e2e9b0ce4) - @Feramance
- [Remove build artifacts from git tracking](https://github.com/Feramance/qBitrr/commit/dc4f467fbc0037e407ae6f322f15d5612b0479d3) - @Feramance
- [Replace custom log viewer with @melloware/react-logviewer library](https://github.com/Feramance/qBitrr/commit/7ef977f96fdf92ef03476cfa07df9b22a841a118) - @Feramance
- [Simplify to basic scrollIntoView with flex layout for height](https://github.com/Feramance/qBitrr/commit/c10c5bd861316cd08b91ee10ba626c6b0464db96) - @Feramance
- [Use Mantine useScrollIntoView hook for reliable auto-scrolling](https://github.com/Feramance/qBitrr/commit/b923eacbcd1916a42fa5bba5d7dceb2443809a63) - @Feramance
- [Remove minHeight from pre to allow scrollable overflow](https://github.com/Feramance/qBitrr/commit/449e936028243997862f44bc0bdae9709bd07ba5) - @Feramance
- [Wrap pre element in div with minHeight to preserve container fill](https://github.com/Feramance/qBitrr/commit/a1b3fa112be5ae83fc6057672a7f30faddb27eff) - @Feramance
- [Remove minHeight constraint that was preventing log content from expanding](https://github.com/Feramance/qBitrr/commit/481ff27a291e6652832a9b4c178b4632a4a8422e) - @Feramance
- [Simplify debug logging to show actual scroll values inline](https://github.com/Feramance/qBitrr/commit/295d830cc8d41e8f531b649d106e4ddf893c6cf9) - @Feramance
- [Use multiple delayed scroll attempts up to 1 second for complex ANSI HTML](https://github.com/Feramance/qBitrr/commit/9c294f3fa419352e6774c9b0ce0866ca9e2d57df) - @Feramance
- [Use scrollIntoView for more reliable log tail scrolling with debug logging](https://github.com/Feramance/qBitrr/commit/d7020865ee91790511558242b88352e87b8d040f) - @Feramance
- [Use aggressive multi-strategy approach to force scroll to log tail](https://github.com/Feramance/qBitrr/commit/2bf7e5eedad09c405a5a53bd3e7f89c572c30060) - @Feramance
- [Simplify and fix logs auto-scroll to reliably tail to end](https://github.com/Feramance/qBitrr/commit/c44f153bcc4702ec93b784b575d27e17a050ad48) - @Feramance
- [Enable Lidarr quality cutoff checking for upgrade searches](https://github.com/Feramance/qBitrr/commit/ed40c39732c32753a6cc5cfa49943bb7ccdf80ad) - @Feramance
- [Revert cache-clearing changes that broke Arr views](https://github.com/Feramance/qBitrr/commit/5334701c9296ee24df0ff25c0e744d9befb4990e) - @Feramance
- [Improve logs auto-scroll reliability with timeout-based rendering](https://github.com/Feramance/qBitrr/commit/4e8330984bf9ee901d5475998cc5ebfcf87aa20b) - @Feramance
- [Enhance free space manager logging with human-readable byte formatting and improved context](https://github.com/Feramance/qBitrr/commit/7e8fe1437a633b82ed058b6c9fad1387bdcb6630) - @Feramance
- [Make theme config case-insensitive with normalized display](https://github.com/Feramance/qBitrr/commit/41595b505b45755bea2465dd6dfd995ec5945218) - @Feramance
- [Improve Sonarr view UX during backend initialization](https://github.com/Feramance/qBitrr/commit/cb97478ec151b937aff13a512e41b938df0ab380) - @Feramance
---

## v5.2.0 (31/10/2025)
### 🚀 Features
- [[minor] UI Updates (#188)](https://github.com/Feramance/qBitrr/commit/e02b5745050d81828fcbb68052b895abdd07d649) - @Feramance

### 🐛 Bug Fixes
- [Fix update flow](https://github.com/Feramance/qBitrr/commit/4f797617f61557ea41770e772b732381a1d63781) - @Feramance
---

## v5.1.1 (30/10/2025)
### 🐛 Bug Fixes
- [[patch] Fixed database issues](https://github.com/Feramance/qBitrr/commit/8ca7e3b277e4f7320d10233eb1559ad4d0915eda) - @Feramance

### 🔧 Maintenance
- [CHange update icon and undid database merging](https://github.com/Feramance/qBitrr/commit/ca5652cebd4eb660cccea6bd7ddee764d6e4bd51) - @Feramance
- [Database hotfix](https://github.com/Feramance/qBitrr/commit/7a587f05004a3388ae0ecfb3bbaef205cecf8951) - @Feramance
---

## v5.1.0 (29/10/2025)
### 🚀 Features
- [[minor] Combined databases rather than having multiple, fixed mobile UI and added tracker configs to web ui (#187)](https://github.com/Feramance/qBitrr/commit/44c938ac2ef308d80eceec2d5c9adf6adf5f44dd) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/3c3cb98c13ca6e0aea892f1b1f1e3ac7f373c1ce) - @Feramance

### 🔧 Maintenance
- [Bump actions/upload-artifact from 4 to 5 (#183)](https://github.com/Feramance/qBitrr/commit/1ff2635b45e0eab033c7c37fb5238d84c9e09521) - @dependabot
- [Bump actions/setup-node from 4 to 6 (#184)](https://github.com/Feramance/qBitrr/commit/749e38079527b139d37ea6e620724e120bbf4b6f) - @dependabot
- [Bump actions/checkout from 4 to 5 (#185)](https://github.com/Feramance/qBitrr/commit/1329d25c490608713564d92bce898c9b62ee620a) - @dependabot
---

## v5.0.2 (29/10/2025)
### 🐛 Bug Fixes
- [[patch] Hotfix](https://github.com/Feramance/qBitrr/commit/4774b40b96dca128e36d558a85130af471496e9b) - @Feramance

### 📝 Documentation
- [docs: sync PKG-INFO description](https://github.com/Feramance/qBitrr/commit/604a1e39b4f87127a22d418f09c1585f4d5e2e8d) - @Feramance

### 🔧 Maintenance
- [Update docker compose](https://github.com/Feramance/qBitrr/commit/5e8c09083a7b47b94c3f22fddc34f0ac08f6880c) - @Feramance
- [Update dependabot auto merge](https://github.com/Feramance/qBitrr/commit/683f06971962c54a61eedc8864eaba44b8bdbdc1) - @Feramance
---

## v5.0.1 (29/10/2025)
### 🐛 Bug Fixes
- [[patch] Request fixes (#186)](https://github.com/Feramance/qBitrr/commit/7d3ba50a164f8ac41f215e39cb1c2b28bc9c05a3) - @Feramance

### 🔧 Maintenance
- [Bump stefanzweifel/git-auto-commit-action from 5 to 7 (#172)](https://github.com/Feramance/qBitrr/commit/a023cd376739a4aacfc3fea3debe8d283173c250) - @dependabot
- [Bump peter-evans/dockerhub-description from 4 to 5 (#173)](https://github.com/Feramance/qBitrr/commit/f4d2e1d5b70552ee30a8f3651259625237bf71ab) - @dependabot
- [Bump python from 3.12 to 3.14 (#174)](https://github.com/Feramance/qBitrr/commit/c0948886a2188792f04f101a663ca118f2b2dbaa) - @dependabot
- [Bump node from 20-bookworm to 25-bookworm (#177)](https://github.com/Feramance/qBitrr/commit/061804cf633009a4026f47b8e13b9e1d725dfc1e) - @dependabot
- [Bump crazy-max/ghaction-import-gpg from 6.2.0 to 6.3.0 (#175)](https://github.com/Feramance/qBitrr/commit/338a220dcb6ababd5411663f2c9f0110e75c9439) - @dependabot
- [Bump github/codeql-action from 3 to 4 (#176)](https://github.com/Feramance/qBitrr/commit/6406cd782f299e0d1c7e851615466c91d25603ef) - @dependabot
- [Bump actions/setup-python from 5 to 6 (#178)](https://github.com/Feramance/qBitrr/commit/d25b3fd6fe94120cd241e5374d46fac2dd801f8a) - @dependabot
- [autofix workflow fixes](https://github.com/Feramance/qBitrr/commit/7ba97dc5706e0cae68819ead5c5e5dafaf5a13c2) - @Feramance
- [fix pr build checks](https://github.com/Feramance/qBitrr/commit/cf7118d261836fbf177edce8db151993960cba5d) - @Feramance
- [Bump @types/node from 24.9.1 to 24.9.2 in /webui (#180)](https://github.com/Feramance/qBitrr/commit/030ea6c4ecdf12832d928ffdfca4d303addf45cb) - @dependabot
- [Bump eslint-plugin-react-hooks from 5.2.0 to 7.0.1 in /webui (#181)](https://github.com/Feramance/qBitrr/commit/098c00a226ee5e3212c547fc651d2bc8c69ad77d) - @dependabot
- [Bump @vitejs/plugin-react from 5.0.4 to 5.1.0 in /webui (#182)](https://github.com/Feramance/qBitrr/commit/255f4596ab4cc006cc5a45a481c31031fe45a213) - @dependabot
---

## v5.0.0 (28/10/2025)
### 🚀 Features
- [[major] Prepare for major release](https://github.com/Feramance/qBitrr/commit/ad15112d36cc92ebb5032e8fefe6dd06e015fb5c) - @Feramance
- [[major] Merge pull request #171 from Feramance/React-updates](https://github.com/Feramance/qBitrr/commit/3675855f67569fde13576b05db915ee2c047fc89) - @Feramance
- [Add auto update feature and config changes](https://github.com/Feramance/qBitrr/commit/0a0c1cafaf2608c1d570fd686373513e7baf054d) - @Feramance
- [feat: Enhance WebUI logging and configuration](https://github.com/Feramance/qBitrr/commit/93a874d6ce87f8554d2ae9d12118a76a7151f212) - @Feramance

### 🐛 Bug Fixes
- [Fixed bad icons](https://github.com/Feramance/qBitrr/commit/0e01881b7e4c60b28f37edb93494b0754b8dcb78) - @Feramance
- [Fix sonarr filter](https://github.com/Feramance/qBitrr/commit/137e135aa6e6c8e274db69c512cde369b5009b6c) - @Feramance
- [Fix missing episodes in Sonarr view](https://github.com/Feramance/qBitrr/commit/ad9d084c4404656ff1cf4bef9547c89146c8c4f0) - @Feramance
- [Fixed available count for sonarr](https://github.com/Feramance/qBitrr/commit/e8acb9230609d4cb2b1510760c67117218b03714) - @Feramance
- [Fixed typescript errors](https://github.com/Feramance/qBitrr/commit/e36f00fa3865fad9c16ee29ff6f2a3ded872536c) - @Feramance
- [Fixed db update message](https://github.com/Feramance/qBitrr/commit/62e1bd0785ec4945ee2cfa70bd02b5e90c197d66) - @Feramance
- [Fix workflow error](https://github.com/Feramance/qBitrr/commit/c25d1839b3f401bd752cb90513a46b53c56835e2) - @Feramance
- [Fixed rsync in workflows](https://github.com/Feramance/qBitrr/commit/25e673423531cf2bda2f1eecb98947a0a691ebea) - @Feramance
- [Fixed search info](https://github.com/Feramance/qBitrr/commit/8e31ecb59c79626aa348854919a8641f3acf51b9) - @Feramance
- [Fixed duplicate data and api handling for radarr and sonarr instances](https://github.com/Feramance/qBitrr/commit/be212032d51fe22cd0a593c7739d3f6219e9f745) - @Feramance
- [Fixed config pop ups, added descriptions and live cron descriptor](https://github.com/Feramance/qBitrr/commit/b3c3339aeda359fc338b6f79b3f71c73f7f37d45) - @Feramance
- [Fix new env](https://github.com/Feramance/qBitrr/commit/d2892b4f3d8bb0dd901839ab40cbe6a87a983105) - @Feramance
- [Fixed config saving and added some QoL features](https://github.com/Feramance/qBitrr/commit/fb7e1b05720f8bec8fab4ef4958c89843303db3b) - @Feramance

### ♻️ Refactoring
- [refactor: Update configuration file instructions and improve UI status indicators](https://github.com/Feramance/qBitrr/commit/e7193b90df2eaf79123fabc618db2e04d6da493b) - @Feramance

### 🎨 Styling
- [UI Improvements](https://github.com/Feramance/qBitrr/commit/89aeaa2019e7203e42c6786110af2c7059ba9848) - @Feramance
- [UI improvements](https://github.com/Feramance/qBitrr/commit/62d0c58f8590c2c87c34fa2d3c32662b00f47a6f) - @Feramance

### 🔧 Maintenance
- [Bump vite from 7.1.11 to 7.1.12 in /webui (#179)](https://github.com/Feramance/qBitrr/commit/990fa34e6899293818aab27857925a996a19d0f2) - @dependabot
- [Workflow fixes](https://github.com/Feramance/qBitrr/commit/47b35c662dff0c672081913c3f06f942cf743a91) - @Feramance
- [fixed strbool](https://github.com/Feramance/qBitrr/commit/721e319793802d7280478ef08f96d1c86e6aed6b) - @Feramance
- [Updated to python 12 and updated autofix workflow](https://github.com/Feramance/qBitrr/commit/8be2aae409f65ba2ecd9a707b530eb4946d0cf10) - @Feramance
- [Updated done buttons and changed some release confgis](https://github.com/Feramance/qBitrr/commit/9620f65012ae71a8cecd2290ab76a9b16fa8ae73) - @Feramance
- [Icons update](https://github.com/Feramance/qBitrr/commit/d48d4332b819319383e88f8b18d80daa827515b7) - @Feramance
- [Changed icons](https://github.com/Feramance/qBitrr/commit/8cdb419f23a9d882bf748c1f1c3740a60e08a727) - @Feramance
- [Added icons](https://github.com/Feramance/qBitrr/commit/039188bd1b2e22c8d4b78de5c4dced040c300ada) - @Feramance
- [Ui improvmenets and more attempts to fix sonarr filtering](https://github.com/Feramance/qBitrr/commit/bd9c36e704053f3bebbc6a238d59fc698cc0bb24) - @Feramance
- [Major changes to arr views and filtering](https://github.com/Feramance/qBitrr/commit/a88a370c985d228a0ea047478244c07f6abb909e) - @Feramance
- [Removed duplicate messaging](https://github.com/Feramance/qBitrr/commit/6c54c011abb853728046322438e3f9e8ba32e6e3) - @Feramance
- [Updated reason text to always be populated](https://github.com/Feramance/qBitrr/commit/ca6cf355f72e6a27c48bdeaf084499bb4b49ed03) - @Feramance
- [Updated messaging for completed database update](https://github.com/Feramance/qBitrr/commit/de7c05b1b1af61de339c72dfe4140842001c85b8) - @Feramance
- [Added more messaging for process overview](https://github.com/Feramance/qBitrr/commit/5f8c3e0aa006f5b7f5574917a22b33dda0c892f7) - @Feramance
- [Added messaging in case a process failes to initialise](https://github.com/Feramance/qBitrr/commit/f945c916b961c0024f6fe9a51311842b15f1c9fe) - @Feramance
- [re-arranged start up order](https://github.com/Feramance/qBitrr/commit/3a14378ea71d5415866fe092d251cd23386a0b2d) - @Feramance
- [Added database update info](https://github.com/Feramance/qBitrr/commit/212c398ab8ddffa9dcb8ca399e948fa04beeb200) - @Feramance
- [More QoL](https://github.com/Feramance/qBitrr/commit/3e76f5412b98535c1d218115d68e8dbbc31ce09b) - @Feramance
- [Removed auth from webUI](https://github.com/Feramance/qBitrr/commit/8f637384498cf8da5840892b5fd14b2d4e7b0c2a) - @Feramance
- [Strengthened auth](https://github.com/Feramance/qBitrr/commit/0f686fb4479fd0155dc51661fb271fec69873c7a) - @Feramance
- [Process restart fixes](https://github.com/Feramance/qBitrr/commit/222f0da42f9125b5e1b56080c62f3cf11901cc17) - @Feramance
- [Ensured db creation](https://github.com/Feramance/qBitrr/commit/b18738ff952beb675ff94842b7437c84d232df07) - @Feramance
- [Further db testing](https://github.com/Feramance/qBitrr/commit/2f65520b305a9f775673d54057e55d22cf8bb80f) - @Feramance
- [ROlled back previous methods and went with a new database](https://github.com/Feramance/qBitrr/commit/3d7042454decce7c03b17c297979e7e93400a160) - @Feramance
- [Trying different methods](https://github.com/Feramance/qBitrr/commit/052f4883a01ec62ad3f6c89624249332f4d28b9f) - @Feramance
- [variable type adjustmenets and mapping](https://github.com/Feramance/qBitrr/commit/61e9bab3bd561b56c81031a7456dcbdaeb6e62b7) - @Feramance
- [Hopefully working search info](https://github.com/Feramance/qBitrr/commit/b059086056e45168c7ac1d205dfaff6b2158f46c) - @Feramance
- [More fixes and changes for process info](https://github.com/Feramance/qBitrr/commit/a8eb5ff275eeea8ef1cb473ad06de864c1d6cbc6) - @Feramance
- [Changed how data is grabbed for process info](https://github.com/Feramance/qBitrr/commit/49e9100b75b075f09c69b9e8849e412a152519fe) - @Feramance
- [More process info fixes](https://github.com/Feramance/qBitrr/commit/624034d9ee4ee09e24c351a5e76ba802666b8a2f) - @Feramance
- [Adjusted selector](https://github.com/Feramance/qBitrr/commit/5f5ea7cc068c5578aadae84256882787e040bf4b) - @Feramance
- [Added search summary to endpoints](https://github.com/Feramance/qBitrr/commit/e15115b6f8a168f47a339fcf96774c919240ee28) - @Feramance
- [Adjusted search state](https://github.com/Feramance/qBitrr/commit/bfa4beebb186797a99d1e8bc266861af46f09ab1) - @Feramance
- [Search process info fix attempt](https://github.com/Feramance/qBitrr/commit/94ed5d2373bec40b20ccd3cb3d7370ef2be4c79a) - @Feramance
- [More fix attempts for process info](https://github.com/Feramance/qBitrr/commit/5e17770bb9847dbd3c470a1ad6e7bf64eb3af1f4) - @Feramance
- [Removed statis files in repo](https://github.com/Feramance/qBitrr/commit/a05cb3e8b52fe936f776b07c006c879699be531c) - @Feramance
- [Improved process info](https://github.com/Feramance/qBitrr/commit/42876bf9cc4947ac65d4e8c4db239771cdbd44a9) - @Feramance
- [Process auto refresh](https://github.com/Feramance/qBitrr/commit/4355bf3a50505d521792cc39dd47b91b092a89a8) - @Feramance
- [Removed timestamps](https://github.com/Feramance/qBitrr/commit/377c2f01304464dab6ff28bbd708b7abe13929db) - @Feramance
- [More 500 fixes](https://github.com/Feramance/qBitrr/commit/4f03110d87a1c79ef36d3127715b0cc993d4b0a0) - @Feramance
- [More fixes](https://github.com/Feramance/qBitrr/commit/8f825125a5a47a862d4c5a52a40e52f3b1ed4674) - @Feramance
- [500 errors fixes](https://github.com/Feramance/qBitrr/commit/1e7ad296a6c873913bb5315e91d51b2c718b8ac0) - @Feramance
- [more process view fixes for refreshing info](https://github.com/Feramance/qBitrr/commit/8a972fa134d6db5c0463e55b16d45421d8339252) - @Feramance
- [Process view fixes](https://github.com/Feramance/qBitrr/commit/f1c72db3aa1a2ecd5a17964afe0f273cee4d7cfa) - @Feramance
- [Added static files build to pre-commit](https://github.com/Feramance/qBitrr/commit/c3bd306e0a27d1c0d688d1509b47fbef1dcf201c) - @Feramance
- [Process QoL updates](https://github.com/Feramance/qBitrr/commit/df4070d345ecc2fb6f69cfaa73a69f3c3835dcd2) - @Feramance
- [Further process view upgrades](https://github.com/Feramance/qBitrr/commit/0ccdcffc97c5a892908e4a8719bdbf669ffcf160) - @Feramance
- [Added some face value logging to the processes view](https://github.com/Feramance/qBitrr/commit/ab68489f36bda526c673b9960e0d0527beab9c04) - @Feramance
- [New workflow for fix automationa and corrected dependabot github token variable](https://github.com/Feramance/qBitrr/commit/bfde2087e66e4114acf5490779870d6ee12feaa4) - @Feramance
- [Make newenv fixes](https://github.com/Feramance/qBitrr/commit/1cae1077c2e11dc28589cab29a170c7088d027cc) - @Feramance
- [More config QoL updates](https://github.com/Feramance/qBitrr/commit/b1fcf68d77eebf84865633cbfc0590169f62262e) - @Feramance
- [Added config validation and fixed auto update reload](https://github.com/Feramance/qBitrr/commit/6a4b1e8bd317295d9af064e9e8630e2678b51a56) - @Feramance
- [Added auto update feature and adjust some more config view details](https://github.com/Feramance/qBitrr/commit/d5ce24da9f870e3ed118b451acd564ca73a97a48) - @Feramance
- [Removed dry run on PR](https://github.com/Feramance/qBitrr/commit/c38c2642e29d93c542fbb5deb997ddbae80f126a) - @Feramance
- [Further config view updates](https://github.com/Feramance/qBitrr/commit/30e7e9eeebb9509178f99b8df019729b9fbd345e) - @Feramance
- [Dependabot fixes](https://github.com/Feramance/qBitrr/commit/1c1b760c99f89178f438c4c6d7fd57afad35bd92) - @Feramance
- [pre-commit and dependabot updates and changed config to have the same style across all options](https://github.com/Feramance/qBitrr/commit/460ab980df5607b2522ce43a5797049e399c824f) - @Feramance
- [Config arr instance updates](https://github.com/Feramance/qBitrr/commit/19cc80f82ff1085297633fb1a8fa8e0e89cd0af2) - @Feramance
- [Release workflow update](https://github.com/Feramance/qBitrr/commit/8b1da6ef5127cf3083ceb7586bff96cad5215de0) - @Feramance
- [Update statis map](https://github.com/Feramance/qBitrr/commit/0b0a2bfc9195da9e12c437dbf58bdd0a3a281310) - @Feramance
- [pre-commit fixes](https://github.com/Feramance/qBitrr/commit/08f52ef84397bab30dda496ef86344442ade5681) - @Feramance
- [Binaries fixed attempt](https://github.com/Feramance/qBitrr/commit/b34b8b4b9e7137b322b5c564acf8577e8f2a9e42) - @Feramance
- [Workflow updates](https://github.com/Feramance/qBitrr/commit/3a4e06c6cc14bc3ed2d28b1cfee76fd40a047e66) - @Feramance
- [More workflow updates, binaries fixing attempts](https://github.com/Feramance/qBitrr/commit/dfc3a3d0d10cf90358a525f92704060ad8d5c21e) - @Feramance
- [Update workflows for new binaries](https://github.com/Feramance/qBitrr/commit/30a9c579257e8507e0b87f9059788cdda7dcfad9) - @Feramance
- [Updated config view](https://github.com/Feramance/qBitrr/commit/f18df108072ea2708174a5d7a5db2de0399e6d75) - @Feramance
- [Added some more styling and defaulted Sonarr view to collapsed](https://github.com/Feramance/qBitrr/commit/2b51312843898bbc585621881409ebe07d47a743) - @Feramance
- [Added show missing only](https://github.com/Feramance/qBitrr/commit/f4725770c1e6cf4044e78190474eb468b27746e0) - @Feramance
- [Adjust sonarr view to read data from episodes only if no series search](https://github.com/Feramance/qBitrr/commit/fe19a4ad5bdd6cdb69c2fe10c7f2a8f81076db75) - @Feramance
- [Sonarr view rewrite](https://github.com/Feramance/qBitrr/commit/6762235883728c1de78215c821e4ecceb0ea8f90) - @Feramance
- [Further fixes and changes to sonarr view](https://github.com/Feramance/qBitrr/commit/cdb9846a3c3852c04b7a93908b68d1ed56f1d001) - @Feramance
- [Updates to sonarr view](https://github.com/Feramance/qBitrr/commit/09295e683476b3ef126b2df5403a325e7f96f718) - @Feramance
---

## v4.10.28 (16/10/2025)
### 🐛 Bug Fixes
- [[patch] Fixed Arr has no attribute torrents](https://github.com/Feramance/qBitrr/commit/b4db5fa7987206d9e5cd203dcebe0b8933ebe0a8) - @Feramance

### 🔧 Maintenance
- [Removed v5 config](https://github.com/Feramance/qBitrr/commit/dc942c4adca4863ca7bea74b19aeca5d7f4bd419) - @Feramance
---

## v4.10.27 (15/10/2025)
### 🐛 Bug Fixes
- [[patch] Hotfix](https://github.com/Feramance/qBitrr/commit/f468e796c7568c359d2378bbc7727629ea533775) - @Feramance
---

## v4.10.26 (15/10/2025)
### 🐛 Bug Fixes
- [[patch] Dependency updates](https://github.com/Feramance/qBitrr/commit/4cd39849a2173f3b3dc2a9621d0f0c8f11fb1a88) - @Feramance
---

## v4.10.25 (14/10/2025)
### 🐛 Bug Fixes
- [[patch] Merge pull request #167 from Feramance/165-attributeerror-nonetype-object-has-no-attribute-hash](https://github.com/Feramance/qBitrr/commit/8d7061a4e0a1470e0e99546a3855571114635e3d) - @Feramance

### 🔧 Maintenance
- [Small fixes](https://github.com/Feramance/qBitrr/commit/bc288574e9ae9b73c3993c91645c9fe243679d9b) - @Feramance
- [Minor tweaks to torrents library call](https://github.com/Feramance/qBitrr/commit/64309436a69db2387eb65afa5fc2e539d3ac03db) - @Feramance
- [Added check before starting condition for `in tags`](https://github.com/Feramance/qBitrr/commit/1e08660a22856d1bc9bc9c1c31642c5476b9591a) - @Feramance
---

## v4.10.24 (03/06/2025)
### 🐛 Bug Fixes
- [[patch] Some logic updates for the Sonarr search command](https://github.com/Feramance/qBitrr/commit/80762778f4517cd8b167b5e5bc47120e2345525a) - @Feramance

### 🔧 Maintenance
- [Merge pull request #164 from christianha1111/master](https://github.com/Feramance/qBitrr/commit/8b92f3e3a7e0c339f44e3c0584d238c00151a59c) - @Feramance
- [Update arss.py](https://github.com/Feramance/qBitrr/commit/7d03fddde6f9201c4d64918084fc42460e45c6cd) - @Feramance
- [fix "SeriesSearch"](https://github.com/Feramance/qBitrr/commit/9d0a1b8ef7c1a0d64f155370aaf84624d7f9c713) - @christianha1111
- [use "SeriesSearch" in post_command. self.search_api_command was null unless. search_api_command is only set if self.search_missing:](https://github.com/Feramance/qBitrr/commit/753fc8b5bbed75d26cff9c2283f616614d2e873c) - @christianha1111
---

## v4.10.23 (29/05/2025)
### 🐛 Bug Fixes
- [[patch] Hotfix](https://github.com/Feramance/qBitrr/commit/ca816463818878164bee3b31f9c04576c300aeeb) - @Feramance

### 🔧 Maintenance
- [Update readme](https://github.com/Feramance/qBitrr/commit/cec04e271a9501a0b9f1fce46ab4d43563e9292e) - @Feramance
---

## v4.10.22 (29/05/2025)
### 🐛 Bug Fixes
- [[patch] Retry release workflow](https://github.com/Feramance/qBitrr/commit/20ffbe4d2dc678a33bce56e60456130739d803c9) - @Feramance
- [[patch] Updated tagging to handle all tags appropriately](https://github.com/Feramance/qBitrr/commit/7580e73d3889c687b1316987b5cc0aa81c43cc03) - @Feramance

### 🔧 Maintenance
- [Update release workflow](https://github.com/Feramance/qBitrr/commit/967e1bf002aba1d3a6a89159f72530b9ed0c05db) - @Feramance
---

## v4.10.21 (21/04/2025)
### 🐛 Bug Fixes
- [[patch] Merge pull request #162 from Feramance:160-question-regarding-the-initial-_monitored_tracker_urls-loading](https://github.com/Feramance/qBitrr/commit/ceb162cd1eee785c969cc07f0e9483b8bb74cab7) - @Feramance
- [Fix per @overlord73](https://github.com/Feramance/qBitrr/commit/f38baf50338b5a20db9657a574425f59b5fe68d0) - @Feramance
- [Fixed some typos](https://github.com/Feramance/qBitrr/commit/184f06550b360d46fdf1213577f9fad77eeb427d) - @bruvv

### 🔧 Maintenance
- [Update custom format unmet handling](https://github.com/Feramance/qBitrr/commit/189428a38f36b9ffd3273051fcdf872a8715273a) - @Feramance
- [Dependency bump and pyarr downgrade](https://github.com/Feramance/qBitrr/commit/254de97188a2f1ce3b98f2a0ecfe90fe003b7c0b) - @Feramance
- [Custom format logging](https://github.com/Feramance/qBitrr/commit/b543d394607e0e0caf6db8ab4735f5144e9121cd) - @Feramance
- [Merge pull request #159 from bruvv/patch-2](https://github.com/Feramance/qBitrr/commit/57b1f33148ee985d62b376722e9790bea045148c) - @Feramance
- [Update gen_config.py](https://github.com/Feramance/qBitrr/commit/2467ba9a639548e154c92d58d28c1ee40ef8a654) - @bruvv
- [Further logging updates for improved logs](https://github.com/Feramance/qBitrr/commit/d06c83c860251972cc4b05140db0ebc92a67248b) - @Feramance
- [Removed ansi colour formatting for neatness](https://github.com/Feramance/qBitrr/commit/83d0fc6fed9dcd1c4c37534bb4989e3c12db8870) - @Feramance
- [Coloured log files](https://github.com/Feramance/qBitrr/commit/1d7fd695eeb655a8fb628adcaae94b699b2c692b) - @Feramance
- [Logging changes](https://github.com/Feramance/qBitrr/commit/091d6234aa425833b59fa5b3dc3eb969773cce74) - @Feramance
- [Attempting to fix connection error](https://github.com/Feramance/qBitrr/commit/fb916f50881d65cbd32596e29d5c7336f6f889e7) - @Feramance
---

## v4.10.20 (12/03/2025)
### 🐛 Bug Fixes
- [[patch] Adjusted stalled delay fallback, logs, and stalled delay now acts on the last activity, rather than added on](https://github.com/Feramance/qBitrr/commit/a61080f740835600c02383376134b6157a024346) - @Feramance
---

## v4.10.19 (12/03/2025)
### 🐛 Bug Fixes
- [[patch] Enabled stalled delay default](https://github.com/Feramance/qBitrr/commit/e9df62d84372b997f399e52e0870150438191104) - @Feramance
---

## v4.10.18 (12/03/2025)
### 🐛 Bug Fixes
- [[patch] Free space fixes and remove stalled tag if recent](https://github.com/Feramance/qBitrr/commit/8bf7bb4366c0dc38fd2ff2ae430c7c8bf8a79cfb) - @Feramance
---

## v4.10.17 (12/03/2025)
### 🐛 Bug Fixes
- [[patch] Updated paused torrent handling](https://github.com/Feramance/qBitrr/commit/1b4be8ff27ec72132e29db1a96ff612dad8d9df5) - @Feramance

### 🔧 Maintenance
- [Free space adjustements](https://github.com/Feramance/qBitrr/commit/7805b27bc78a19ae27db7e0e19abe6c102ec396b) - @Feramance
---

## v4.10.16 (11/03/2025)
### 🐛 Bug Fixes
- [[patch] Stalled delay fixes](https://github.com/Feramance/qBitrr/commit/fd119edf95348a255b27968e9dc55304f0228389) - @Feramance

### 🔧 Maintenance
- [Further conditional adjustements for younger torrents and stalled delay](https://github.com/Feramance/qBitrr/commit/07a881e3496f49d93b63cf38549f8ba848eaf348) - @Feramance
- [Adjusted younger than conditions](https://github.com/Feramance/qBitrr/commit/737f295b58fc2be41a97e80fb21db20ebda82a1b) - @Feramance
- [Further stall handling checks](https://github.com/Feramance/qBitrr/commit/7c976a40b378243de5c7702deb0c1d41f106fb50) - @Feramance
- [Log updates](https://github.com/Feramance/qBitrr/commit/03fe74e35e85669e484c406045b776f60aa54f9b) - @Feramance
- [Adjusted stalled delay conditions](https://github.com/Feramance/qBitrr/commit/4b71295c58b502b8bcfe7da3ba4f1e4784165dbe) - @Feramance
- [Logging update](https://github.com/Feramance/qBitrr/commit/09fd554546c71968fd5a6df2e42755bd998da060) - @Feramance
- [Further update changes](https://github.com/Feramance/qBitrr/commit/83f10f33cb9260b889c2c54ccda31d1590297862) - @Feramance
- [Update log](https://github.com/Feramance/qBitrr/commit/ee30569a045482ec0c2f68b8ce81f6722cf24a7f) - @Feramance
- [Logging to check vars](https://github.com/Feramance/qBitrr/commit/386332cd00e33c4f5b9fa1936cde72bda7490727) - @Feramance
- [Removed recent queue to use added on torrent property instead](https://github.com/Feramance/qBitrr/commit/2a12cb4ae098dcf2d63e044ce7775b7914bc3867) - @Feramance
- [Adjusted recent queue check](https://github.com/Feramance/qBitrr/commit/cf7082fd937d91296d4c2b3f8da43bf5dfd69e47) - @Feramance
- [Adjust stalled delay behaviour](https://github.com/Feramance/qBitrr/commit/d9a76442fca5c2c41b643c6a8461cd3efe8d2f27) - @Feramance
- [Update README.md](https://github.com/Feramance/qBitrr/commit/eb98c8b5edee9ef846d79c0cbc9de41767c4512a) - @Feramance