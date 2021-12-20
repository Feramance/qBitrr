# Changelog

## v2.1.12 (20/12/2021)
- [[patch] replace requests complexjson with ujson if it is available (This affects the whole runtime meaning assuming the response isn't unsupported it should give a significant boost to requests performance.](https://github.com/Drapersniper/Qbitrr/commit/1ee15b5d3182251c6dcb127c7555205e95809ba1) - @Drapersniper
- [[deps] Add ujson as an optional dep](https://github.com/Drapersniper/Qbitrr/commit/320f785e9c79e18772355e064650cba0a93a15d3) - @Drapersniper

---

## v2.1.11 (20/12/2021)
- [[patch] Make release](https://github.com/Drapersniper/Qbitrr/commit/441b54ec7eb294a919a00ba0b76e001aabd3ed35) - @Drapersniper

---

## v2.1.10 (20/12/2021)
- [[patch] Fix an issue where you couldn't run any flags if the config file didn't exist in the app dir](https://github.com/Drapersniper/Qbitrr/commit/3dfb989bef624fa68e7730de9e91f93b2f3f51e3) - @Drapersniper

---

## v2.1.9 (20/12/2021)
- [[patch] Make release](https://github.com/Drapersniper/Qbitrr/commit/7500811a97be6a7befdaeed347a32bec7895bdf6) - @Drapersniper
- [[patch] config file](https://github.com/Drapersniper/Qbitrr/commit/71a22ecf8038a6e6b8e16f27ecf14b542f4d7082) - @Drapersniper
- [[patch] Fix broken builds](https://github.com/Drapersniper/Qbitrr/commit/1e201e0b56fa3952aecfbbc3f9dfa297b552d935) - @Drapersniper
- [[patch] Hotfix](https://github.com/Drapersniper/Qbitrr/commit/9eeb34372ddd0ce680841f2ebc40c93ee4e6acf3) - @Drapersniper
- [[patch] clean up and fixes](https://github.com/Drapersniper/Qbitrr/commit/d3c7351a6d6e651c590dcbc54a6f93dbb9374703) - @Drapersniper
- [add `--license` and `--source` flags to the script](https://github.com/Drapersniper/Qbitrr/commit/f94c3e3c005ffd0df02a77bae310349e5a4a2f90) - @Drapersniper
- [add `--version` flag and update README.md](https://github.com/Drapersniper/Qbitrr/commit/7fa3e9d1b66fe871ddf72e77a6cdb48ef7832ae4) - @Drapersniper
- [Improve internet check so that it does not run if there is no torrents to check](https://github.com/Drapersniper/Qbitrr/commit/c201c535698a7e553b4ef90eb518c86f794d0e9c) - @Drapersniper
- [[pre-commit.ci] pre-commit autoupdate](https://github.com/Drapersniper/Qbitrr/commit/9c4160529948477f6ad51f78a47bde6cb0127060) - @pre-commit-ci[bot]

---

## v2.1.8 (20/12/2021)
- [[patch] Improved startup logging](https://github.com/Drapersniper/Qbitrr/commit/d858027c2bfb004f3b9ddf9ba0e71b83e8a1c977) - @Drapersniper
- [Reduce the number of socket calls for the internet checks](https://github.com/Drapersniper/Qbitrr/commit/9c0686e5ae2957eeea71476d42303d77270cf422) - @Drapersniper

---

## v2.1.7 (20/12/2021)
- [[patch] Fixed an issue that caused logs to show incorrect info](https://github.com/Drapersniper/Qbitrr/commit/6ed607e6d102c6937a14e357a331e2753f609087) - @Drapersniper
- [Ensure KeyboardInterrupt is caught correctly + fix an issue where logs where being duplicated](https://github.com/Drapersniper/Qbitrr/commit/313a26ffa21bfb0929921101d73cb39f65cbf002) - @Drapersniper
- [Fixed a bug where there would be a crash if the user attempted to add a torrent to the recheck or failed category](https://github.com/Drapersniper/Qbitrr/commit/e4da075d0e864ec4f23c19bb1caf87cd8070151e) - @Drapersniper

---

## v2.1.6 (20/12/2021)
- [[patch] 2 enhancements and 1 bug fix.](https://github.com/Drapersniper/Qbitrr/commit/3e285bcf7dea29fa234508a8a920400f6b85e3f1) - @Drapersniper

---

## v2.1.5 (19/12/2021)
- [[patch] Build binary for all platforms properly](https://github.com/Drapersniper/Qbitrr/commit/23a65f963341123024f85f2ef110689e492e6b89) - @Drapersniper

---

## v2.1.4 (19/12/2021)
- [[patch] Fix an issue where logs where not shown correct + improve exiting logic](https://github.com/Drapersniper/Qbitrr/commit/3aa3f39c1d052e3b8201a7606fb3504077897ffc) - @Drapersniper
- [Fixed the build spec to generate a portable binary](https://github.com/Drapersniper/Qbitrr/commit/4d2db601905f756289b15bef5f5219e131580fcf) - @Drapersniper

---

## v2.1.3 (19/12/2021)
- [[patch] Build binaries - properly this time v2](https://github.com/Drapersniper/Qbitrr/commit/da31cf5f135530cb7c2e0062f711f7b813b99f46) - @Drapersniper

---

## v2.1.2 (19/12/2021)
- [[patch] Build binaries - properly this time](https://github.com/Drapersniper/Qbitrr/commit/27784e1a96fba4b19fcfc1ae1a6a4bd2ac88439f) - @Drapersniper

---

## v2.1.1 (19/12/2021)
- [[patch] Build binaries](https://github.com/Drapersniper/Qbitrr/commit/9a4db8491deac9867975ecaab7f385d51eee8537) - @Drapersniper

---

## v2.1.0 (19/12/2021)
- [[minor] Minor release to fix issue with config file across the separate processses - reason it is breaking is due to the removal of the `--config` flag](https://github.com/Drapersniper/Qbitrr/commit/2f51db77c3ef8c0bdd4d432454f02bd4b9f66f60) - @Drapersniper
- [Update config.example.toml](https://github.com/Drapersniper/Qbitrr/commit/eb4ce73af082cd918f389aee6611229f15192a8c) - @JacquesLG

---

## v2.0.4 (18/12/2021)
- [[patch] bump to deploy](https://github.com/Drapersniper/Qbitrr/commit/4867f2b9ebaa5941b2a879149f9146900817c03a) - @Drapersniper

---

## v2.0.3 (18/12/2021)

---

## v2.0.2 (18/12/2021)

---

## v1.0.6 (16/12/2021)
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
- [Create codeql-analysis.yml](https://github.com/Drapersniper/Qbitrr/commit/c5d8e82afae91220a6ae1a1302511d049856995a) - @Drapersniper
- [[deploy] Automated patch version bump: 1.1.3 >> 1.1.4](https://github.com/Drapersniper/Qbitrr/commit/093884ea7e27bbb5d9c5bdee6b58a736b35084ad) - @Drapersniper
- [[patch] Fix a wrong attribute access added by 1.1.2](https://github.com/Drapersniper/Qbitrr/commit/e37930e7bf4b5996b448286573cfd3541302613c) - @Drapersniper
- [[deploy] Automated patch version bump: 1.1.2 >> 1.1.3](https://github.com/Drapersniper/Qbitrr/commit/30c0acc2b90093aa7d2aa33c8c57f8997238c385) - @Drapersniper
- [[patch] force ci to run](https://github.com/Drapersniper/Qbitrr/commit/9f5c5ccc7044299ce8e0b59603e3f57c585dc83b) - @Drapersniper
- [[deploy] Automated patch version bump: 1.1.1 >> 1.1.2](https://github.com/Drapersniper/Qbitrr/commit/661f8a26643215b9ccf2404d9e008c02613cbbfe) - @Drapersniper
- [[patch] force ci to run](https://github.com/Drapersniper/Qbitrr/commit/e330f6340675e449bdc050b6c8db208e24641c06) - @Drapersniper
- [[patch] force ci to run](https://github.com/Drapersniper/Qbitrr/commit/b881e0d7a07406b4104fd2a2440d8ddceddd34a7) - @Drapersniper
- [[patch] ...](https://github.com/Drapersniper/Qbitrr/commit/b4f2e7e2a2e0669b3afa3aad841225dc247eb385) - @Drapersniper
- [[patch] Testing new work flows](https://github.com/Drapersniper/Qbitrr/commit/58b93775db1723aa271bea44a70a9acea9d1689a) - @Drapersniper
- [[deploy] Automated patch version bump: 1.1.0 >> 1.1.1](https://github.com/Drapersniper/Qbitrr/commit/8fd2f4c8f403ad5be4e5e9ca95bed89942819418) - @Drapersniper
- [[patch] Fix an attribute error introduced in v1.1.0](https://github.com/Drapersniper/Qbitrr/commit/42de5d1ad4639dbc5ed49f18b7ec5b8c4c68f404) - @Drapersniper
- [Add a few extra pre-commit hooks for code formatting.](https://github.com/Drapersniper/Qbitrr/commit/b436d0a367575dc654b4995e92311ecf18c6a6d7) - @Drapersniper
- [**Config file change**](https://github.com/Drapersniper/Qbitrr/commit/cabf2e98030cbb136a55b19df8d650088745c063) - @Drapersniper
- [improve/fix the Linux FFprobe value for linux](https://github.com/Drapersniper/Qbitrr/commit/af794b9155a1de29ae91e6c1f0aea0b33b12988c) - @Drapersniper
- [[deploy] Automated minor version bump: 1.0.9 >> 1.1.0](https://github.com/Drapersniper/Qbitrr/commit/1d357821e242d17b19c5688422a1af58c6f05969) - @Drapersniper
- [[minor] Self updating FFprobe dependency](https://github.com/Drapersniper/Qbitrr/commit/6b94299e3aa66a56a41347d156be163094a10751) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.8 >> 1.0.9](https://github.com/Drapersniper/Qbitrr/commit/45f1aaf6e80d2a0f5d7df41fae4cf353ad992d39) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/306fc219dfa87f47e5ffd3bbb19b7b48e109036a) - @Drapersniper
- [...](https://github.com/Drapersniper/Qbitrr/commit/943319758e118fb682679f6ebf343090c704fb62) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.7 >> 1.0.8](https://github.com/Drapersniper/Qbitrr/commit/6d18e4c471274b3c901468b764b6663647c4f676) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/ff6e722c80321c309824aafbd48be8786a531677) - @Drapersniper
- [lets not double publish](https://github.com/Drapersniper/Qbitrr/commit/687da80d4aad686625e2678d343e0a2c6c01589b) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/ff2dd081356f5a1ec3f350e9d3713c0c6bcd8723) - @Drapersniper
- [*sigh*](https://github.com/Drapersniper/Qbitrr/commit/38806e211b9c8c25b36e69fadde64197fbbd788b) - @Drapersniper
- [[patch] admin release](https://github.com/Drapersniper/Qbitrr/commit/c5e15f7ff4cb0c2e4263d8a9dc454ca44c7c8bc8) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/c816c65fb9d6f91b64d860bd2ba8b60c2dc97716) - @Drapersniper
- [separate workflows](https://github.com/Drapersniper/Qbitrr/commit/d279af46164972f0ff65532750e17a5884c6261e) - @Drapersniper
- [sign automated changes](https://github.com/Drapersniper/Qbitrr/commit/c9f7e4fcbfcffdf1b4d8595de0b50d09804e7a12) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.6 >> 1.0.7](https://github.com/Drapersniper/Qbitrr/commit/c4d668a0186e8f8ac96cc9b74a57341cd43fa7dd) - @Drapersniper
- [[patch] admin release](https://github.com/Drapersniper/Qbitrr/commit/c4df98e1144c9ac329f9397b335dd973c1c61985) - @Drapersniper
- [Automatically create releases](https://github.com/Drapersniper/Qbitrr/commit/a775772f6ce6903ea4ee9c4066190c1b125e3e75) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.5 >> 1.0.6](https://github.com/Drapersniper/Qbitrr/commit/ce738e74007ce6e0bd54d91b5cfda4f41562eac6) - @Drapersniper
- [[patch] admin release](https://github.com/Drapersniper/Qbitrr/commit/b082b0dfd8693ff5b40490b6db29a21d6c02fef7) - @Drapersniper
- [add tags](https://github.com/Drapersniper/Qbitrr/commit/2986e2eee6f4805f298958897144c6092a5de780) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.4 >> 1.0.5](https://github.com/Drapersniper/Qbitrr/commit/d8909a0135bf9f662d960051c89d8af5683f30e5) - @Drapersniper
- [[patch] Im a lil lazy - to this should be the version bump and depploy automated](https://github.com/Drapersniper/Qbitrr/commit/9e3d78ef10f2958815b1d4d6caad1542845ae349) - @Drapersniper
- [add version to commit](https://github.com/Drapersniper/Qbitrr/commit/f52ca6db0d613015031cd06e45a2c93c8c80a10c) - @Drapersniper
- [[deploy] Automated patch version bump](https://github.com/Drapersniper/Qbitrr/commit/e5d316093347c00540eac0fd89beee92052fb4d5) - @Drapersniper
- [[patch] Just a test](https://github.com/Drapersniper/Qbitrr/commit/4cdb41021d5486aa7fefc9c6b6ad648fe738145e) - @Drapersniper
- [fix actions](https://github.com/Drapersniper/Qbitrr/commit/f6a9af93c21ab0f220f73a202b91950e18fdada0) - @Drapersniper
- [finish setup of automated released based on tags](https://github.com/Drapersniper/Qbitrr/commit/a7417e8deda7955994430a6b7f4b016a4e55bce1) - @Drapersniper
- [prep2](https://github.com/Drapersniper/Qbitrr/commit/c6982c687f5c8bfe7ddf14ae0b6b02edb543135a) - @Drapersniper
- [prep](https://github.com/Drapersniper/Qbitrr/commit/1c9111cb7aa547e0484e9b2e13eb8d8a1d7b0c57) - @Drapersniper
- [version bump](https://github.com/Drapersniper/Qbitrr/commit/a86da56b58036e2cdbd9fd8a3d5edbee5cc0f627) - @Drapersniper
- [fix availability check + update "last added" section of logs to show when the "last added" is considered - this is the time a download starts if there is a queue of torrents.](https://github.com/Drapersniper/Qbitrr/commit/50a384078163698c94fce69a09d9d78a61cf1798) - @Drapersniper
- [bump version](https://github.com/Drapersniper/Qbitrr/commit/5d781b2180e1070663748e9948c7ba95d5594747) - @Drapersniper
- [make the script exit with an error message if `config.ini` cannot be located](https://github.com/Drapersniper/Qbitrr/commit/d867253a8e37da9f55a5b54e6f37150e8db58a58) - @Drapersniper
- [update README.md](https://github.com/Drapersniper/Qbitrr/commit/6bd5b8a91e29028d1e311d159b712ee46e8692a5) - @Drapersniper
- [make state show properly](https://github.com/Drapersniper/Qbitrr/commit/c19b5659a8de5777d1ae57149f4604ce5c2f2b65) - @Drapersniper
- [Add a lot more info and the same info to all torrent log lines such as state, when was it added etc](https://github.com/Drapersniper/Qbitrr/commit/e91c10135b176c038847fc9d8752a3f7723b3585) - @Drapersniper
- [Add update instructions](https://github.com/Drapersniper/Qbitrr/commit/0475220ed4d5154b447c92570643e6f1a014cecf) - @Drapersniper
- [update README.md with new install and exec instructions now that the script is available on PyPi](https://github.com/Drapersniper/Qbitrr/commit/4a7aa04d450c40a198e220199fe4a73ed317e64e) - @Drapersniper
- [hotfix pypi release](https://github.com/Drapersniper/Qbitrr/commit/eac1b375a62ffe597927a2d2e1e4c0c6dd89b9bd) - @Drapersniper
- [hotfix pypi release](https://github.com/Drapersniper/Qbitrr/commit/66eed16f431e59bac2640784cc96526f9117a70a) - @Drapersniper
- [update ignore and key in setup.cfg](https://github.com/Drapersniper/Qbitrr/commit/d6209e7f5474e312b5d95e42338ea4195441a1cf) - @Drapersniper
- [formatting changes](https://github.com/Drapersniper/Qbitrr/commit/93cb7d8a8c1f5aed4198e4c60535b978b9ea73de) - @Drapersniper
- [Merge branch 'master' of https://github.com/Drapersniper/Qbitrr](https://github.com/Drapersniper/Qbitrr/commit/718b4409ed817fc838ba21591c7c317bea2ba504) - @Drapersniper
- [prep for release on pypi](https://github.com/Drapersniper/Qbitrr/commit/29e4f03b2daad49d4f05740a03e71995c19049f6) - @Drapersniper
- [Create LICENSE](https://github.com/Drapersniper/Qbitrr/commit/06a9537806cb0b843fe34b127432bb703cd64484) - @Drapersniper
- [Create python-publish.yml](https://github.com/Drapersniper/Qbitrr/commit/ef176318a22a0ae8e648754fe720565cf5791b6a) - @Drapersniper
- [add Ombi and Overserr links to README.md](https://github.com/Drapersniper/Qbitrr/commit/bbf251147783033f6386ab3f78ba79b7f97258fc) - @Drapersniper
- [Set Ombi and Overserr logic off by default](https://github.com/Drapersniper/Qbitrr/commit/e0c5e183542467b174873e366be6420d2797b480) - @Drapersniper

---

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
- [[deploy] Automated patch version bump: 1.1.3 >> 1.1.4](https://github.com/Drapersniper/Qbitrr/commit/093884ea7e27bbb5d9c5bdee6b58a736b35084ad) - @Drapersniper

---

## v1.1.3 (14/12/2021)
- [[deploy] Automated patch version bump: 1.1.2 >> 1.1.3](https://github.com/Drapersniper/Qbitrr/commit/30c0acc2b90093aa7d2aa33c8c57f8997238c385) - @Drapersniper
- [[patch] force ci to run](https://github.com/Drapersniper/Qbitrr/commit/9f5c5ccc7044299ce8e0b59603e3f57c585dc83b) - @Drapersniper

---

## v1.1.2 (14/12/2021)
- [[deploy] Automated patch version bump: 1.1.1 >> 1.1.2](https://github.com/Drapersniper/Qbitrr/commit/661f8a26643215b9ccf2404d9e008c02613cbbfe) - @Drapersniper
- [[patch] force ci to run](https://github.com/Drapersniper/Qbitrr/commit/e330f6340675e449bdc050b6c8db208e24641c06) - @Drapersniper
- [[patch] force ci to run](https://github.com/Drapersniper/Qbitrr/commit/b881e0d7a07406b4104fd2a2440d8ddceddd34a7) - @Drapersniper
- [[patch] ...](https://github.com/Drapersniper/Qbitrr/commit/b4f2e7e2a2e0669b3afa3aad841225dc247eb385) - @Drapersniper
- [[patch] Testing new work flows](https://github.com/Drapersniper/Qbitrr/commit/58b93775db1723aa271bea44a70a9acea9d1689a) - @Drapersniper

---

## v1.1.1 (14/12/2021)
- [[deploy] Automated patch version bump: 1.1.0 >> 1.1.1](https://github.com/Drapersniper/Qbitrr/commit/8fd2f4c8f403ad5be4e5e9ca95bed89942819418) - @Drapersniper
- [[patch] Fix an attribute error introduced in v1.1.0](https://github.com/Drapersniper/Qbitrr/commit/42de5d1ad4639dbc5ed49f18b7ec5b8c4c68f404) - @Drapersniper
- [Add a few extra pre-commit hooks for code formatting.](https://github.com/Drapersniper/Qbitrr/commit/b436d0a367575dc654b4995e92311ecf18c6a6d7) - @Drapersniper
- [**Config file change**](https://github.com/Drapersniper/Qbitrr/commit/cabf2e98030cbb136a55b19df8d650088745c063) - @Drapersniper
- [improve/fix the Linux FFprobe value for linux](https://github.com/Drapersniper/Qbitrr/commit/af794b9155a1de29ae91e6c1f0aea0b33b12988c) - @Drapersniper

---

## v1.1.0 (14/12/2021)
- [[deploy] Automated minor version bump: 1.0.9 >> 1.1.0](https://github.com/Drapersniper/Qbitrr/commit/1d357821e242d17b19c5688422a1af58c6f05969) - @Drapersniper

---

## v1.0.9 (13/12/2021)
- [[deploy] Automated patch version bump: 1.0.8 >> 1.0.9](https://github.com/Drapersniper/Qbitrr/commit/45f1aaf6e80d2a0f5d7df41fae4cf353ad992d39) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/306fc219dfa87f47e5ffd3bbb19b7b48e109036a) - @Drapersniper

---

## v1.0.8 (13/12/2021)
- [[deploy] Automated patch version bump: 1.0.7 >> 1.0.8](https://github.com/Drapersniper/Qbitrr/commit/6d18e4c471274b3c901468b764b6663647c4f676) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/ff6e722c80321c309824aafbd48be8786a531677) - @Drapersniper
- [lets not double publish](https://github.com/Drapersniper/Qbitrr/commit/687da80d4aad686625e2678d343e0a2c6c01589b) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/ff2dd081356f5a1ec3f350e9d3713c0c6bcd8723) - @Drapersniper
- [*sigh*](https://github.com/Drapersniper/Qbitrr/commit/38806e211b9c8c25b36e69fadde64197fbbd788b) - @Drapersniper
- [[patch] admin release](https://github.com/Drapersniper/Qbitrr/commit/c5e15f7ff4cb0c2e4263d8a9dc454ca44c7c8bc8) - @Drapersniper
- [[patch] admin bump](https://github.com/Drapersniper/Qbitrr/commit/c816c65fb9d6f91b64d860bd2ba8b60c2dc97716) - @Drapersniper
- [separate workflows](https://github.com/Drapersniper/Qbitrr/commit/d279af46164972f0ff65532750e17a5884c6261e) - @Drapersniper

---

## v1.0.7 (12/12/2021)
- [[deploy] Automated patch version bump: 1.0.6 >> 1.0.7](https://github.com/Drapersniper/Qbitrr/commit/c4d668a0186e8f8ac96cc9b74a57341cd43fa7dd) - @Drapersniper
- [[patch] admin release](https://github.com/Drapersniper/Qbitrr/commit/c4df98e1144c9ac329f9397b335dd973c1c61985) - @Drapersniper
- [Automatically create releases](https://github.com/Drapersniper/Qbitrr/commit/a775772f6ce6903ea4ee9c4066190c1b125e3e75) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.5 >> 1.0.6](https://github.com/Drapersniper/Qbitrr/commit/ce738e74007ce6e0bd54d91b5cfda4f41562eac6) - @Drapersniper
- [[patch] admin release](https://github.com/Drapersniper/Qbitrr/commit/b082b0dfd8693ff5b40490b6db29a21d6c02fef7) - @Drapersniper
- [add tags](https://github.com/Drapersniper/Qbitrr/commit/2986e2eee6f4805f298958897144c6092a5de780) - @Drapersniper
- [[deploy] Automated patch version bump: 1.0.4 >> 1.0.5](https://github.com/Drapersniper/Qbitrr/commit/d8909a0135bf9f662d960051c89d8af5683f30e5) - @Drapersniper
- [[patch] Im a lil lazy - to this should be the version bump and depploy automated](https://github.com/Drapersniper/Qbitrr/commit/9e3d78ef10f2958815b1d4d6caad1542845ae349) - @Drapersniper
- [add version to commit](https://github.com/Drapersniper/Qbitrr/commit/f52ca6db0d613015031cd06e45a2c93c8c80a10c) - @Drapersniper
- [[deploy] Automated patch version bump](https://github.com/Drapersniper/Qbitrr/commit/e5d316093347c00540eac0fd89beee92052fb4d5) - @Drapersniper
- [[patch] Just a test](https://github.com/Drapersniper/Qbitrr/commit/4cdb41021d5486aa7fefc9c6b6ad648fe738145e) - @Drapersniper
- [fix actions](https://github.com/Drapersniper/Qbitrr/commit/f6a9af93c21ab0f220f73a202b91950e18fdada0) - @Drapersniper
- [finish setup of automated released based on tags](https://github.com/Drapersniper/Qbitrr/commit/a7417e8deda7955994430a6b7f4b016a4e55bce1) - @Drapersniper
- [prep2](https://github.com/Drapersniper/Qbitrr/commit/c6982c687f5c8bfe7ddf14ae0b6b02edb543135a) - @Drapersniper

---

## v1.0.3 (12/12/2021)
- [version bump](https://github.com/Drapersniper/Qbitrr/commit/a86da56b58036e2cdbd9fd8a3d5edbee5cc0f627) - @Drapersniper

---

## v1.0.2 (11/12/2021)
- [bump version](https://github.com/Drapersniper/Qbitrr/commit/5d781b2180e1070663748e9948c7ba95d5594747) - @Drapersniper
- [make the script exit with an error message if `config.ini` cannot be located](https://github.com/Drapersniper/Qbitrr/commit/d867253a8e37da9f55a5b54e6f37150e8db58a58) - @Drapersniper
- [update README.md](https://github.com/Drapersniper/Qbitrr/commit/6bd5b8a91e29028d1e311d159b712ee46e8692a5) - @Drapersniper
- [make state show properly](https://github.com/Drapersniper/Qbitrr/commit/c19b5659a8de5777d1ae57149f4604ce5c2f2b65) - @Drapersniper
- [Add a lot more info and the same info to all torrent log lines such as state, when was it added etc](https://github.com/Drapersniper/Qbitrr/commit/e91c10135b176c038847fc9d8752a3f7723b3585) - @Drapersniper
- [Add update instructions](https://github.com/Drapersniper/Qbitrr/commit/0475220ed4d5154b447c92570643e6f1a014cecf) - @Drapersniper

---

## v1.0.1 (11/12/2021)
- [hotfix pypi release](https://github.com/Drapersniper/Qbitrr/commit/eac1b375a62ffe597927a2d2e1e4c0c6dd89b9bd) - @Drapersniper

---

## v1.0.0 (11/12/2021)
- [update ignore and key in setup.cfg](https://github.com/Drapersniper/Qbitrr/commit/d6209e7f5474e312b5d95e42338ea4195441a1cf) - @Drapersniper
- [formatting changes](https://github.com/Drapersniper/Qbitrr/commit/93cb7d8a8c1f5aed4198e4c60535b978b9ea73de) - @Drapersniper
- [Merge branch 'master' of https://github.com/Drapersniper/Qbitrr](https://github.com/Drapersniper/Qbitrr/commit/718b4409ed817fc838ba21591c7c317bea2ba504) - @Drapersniper
- [prep for release on pypi](https://github.com/Drapersniper/Qbitrr/commit/29e4f03b2daad49d4f05740a03e71995c19049f6) - @Drapersniper
- [Create LICENSE](https://github.com/Drapersniper/Qbitrr/commit/06a9537806cb0b843fe34b127432bb703cd64484) - @Drapersniper
- [Create python-publish.yml](https://github.com/Drapersniper/Qbitrr/commit/ef176318a22a0ae8e648754fe720565cf5791b6a) - @Drapersniper
- [add Ombi and Overserr links to README.md](https://github.com/Drapersniper/Qbitrr/commit/bbf251147783033f6386ab3f78ba79b7f97258fc) - @Drapersniper
- [Set Ombi and Overserr logic off by default](https://github.com/Drapersniper/Qbitrr/commit/e0c5e183542467b174873e366be6420d2797b480) - @Drapersniper
- [update log string and undo a debug change that was accidentally commited](https://github.com/Drapersniper/Qbitrr/commit/2c7e8d35c9931b012d4404086571512fddc3619b) - @Drapersniper
- [fix typos in README.md](https://github.com/Drapersniper/Qbitrr/commit/013e5199559e36bb6a17ec0f9ef4035d5cb26374) - @Drapersniper
- [update README.md with discord and change logs](https://github.com/Drapersniper/Qbitrr/commit/db069cc25953aa05257fcc71fbee51ac47112495) - @Drapersniper
- [fix for issue#6?](https://github.com/Drapersniper/Qbitrr/commit/fefc3a6a6d328219b2a8276fde36f3a5787b1f00) - @Drapersniper
- [temp fix for issue#6](https://github.com/Drapersniper/Qbitrr/commit/b5d6febb76fcaafa3c301243b636e0fc3e190f0a) - @Drapersniper
- [fix to warn instead of throw exception when a folder queued for cleanup has been deleted (likely by the arr instance)](https://github.com/Drapersniper/Qbitrr/commit/bec44288eab71a02c07dbad63c1fc24325ca8a74) - @Drapersniper
- [this should pass both the blocklist and blacklist params and the arr instance should be smart enough to use the correct ones.](https://github.com/Drapersniper/Qbitrr/commit/a12c15e33d6c454b4ea52272d4faf47ec4b2486e) - @Drapersniper
- [add Ignore slow torrents config value -  Note this update will require you to delete the existing databases in `~/.config/qBitManager` due to changes to the database format.](https://github.com/Drapersniper/Qbitrr/commit/8230fec329d8037531cdeb330a0b34fd70e457c0) - @Drapersniper
- [add DoUpgradeSearch and QualityUnmetSearch and SearchBySeries also fix a bunch of things.](https://github.com/Drapersniper/Qbitrr/commit/0c60f2203e9086b285a40c5ff6d98ed536520cab) - @Drapersniper
- [bugfixes](https://github.com/Drapersniper/Qbitrr/commit/35147c45b8ea37e61ca977037bd89cf2f66a7c29) - @Drapersniper
- [bugfixes](https://github.com/Drapersniper/Qbitrr/commit/b367cd39932b9ce812e526a631ee227723f3c2c1) - @Drapersniper
- [ignore episodes without an absolute number since sonarr ignores it already](https://github.com/Drapersniper/Qbitrr/commit/825aafce2eb247d8a3eb247a365f10115fe3cc5a) - @Drapersniper
- [change](https://github.com/Drapersniper/Qbitrr/commit/aec82c3bb1203119e1b2011f548dc7a2ce744817) - @Drapersniper
- [Change Sonarrs queue end point over to api/v3, monitor queue of specific errors ("Not an upgrade. not a prefered word upgrade") so they can be flagged for deletion if auto delete is enabled](https://github.com/Drapersniper/Qbitrr/commit/aea676ac18f83001b2fd76ab07bd0f9e6acd8398) - @Drapersniper
- [Change Sonarrs queue end point over to api/v3, monitor queue of specific errors ("Not an upgrade. not a prefered word upgrade") so they can be flagged for deletion if auto delete is enabled](https://github.com/Drapersniper/Qbitrr/commit/0d134a31e0da7828cac9a0ac2db2aa07d401bc13) - @Drapersniper
- [Just tweak tags to show "[PRIORITY SEARCH - TODAY]: "](https://github.com/Drapersniper/Qbitrr/commit/ae04d3f11ab64659e37697c9e893bc1c7ad96cea) - @Drapersniper
- [Just tweak tags to show "[PRIORITY SEARCH - TODAY]: "](https://github.com/Drapersniper/Qbitrr/commit/7fcb28f5ff0d7accf996969b1a6905534d6aecb5) - @Drapersniper
- [Add new configs entries to the initial logs (for debugging purpose, APIKeys are always logged under DEBUG level)](https://github.com/Drapersniper/Qbitrr/commit/5fcf9657bafd6f037edecb42af959a862449bfd6) - @Drapersniper
- [add "PrioritizeTodaysReleases" key to Sonarr config, does what the name says.](https://github.com/Drapersniper/Qbitrr/commit/6ce4189246de69125bf72ab831ff53b48c1a01b9) - @Drapersniper
- [bug fixes](https://github.com/Drapersniper/Qbitrr/commit/d700e12bf3964c7450caaa09a454fc4a0f120a0a) - @Drapersniper
- [Add Overseerr Support (Mutually exclusive to Ombi)](https://github.com/Drapersniper/Qbitrr/commit/70010f88d16b0a6e9b3099ee293196ae562a81b7) - @Drapersniper
- [welp ...](https://github.com/Drapersniper/Qbitrr/commit/596754ba5821c127fb722ccf7dd54966b6980531) - @Drapersniper
- [Just some logging changes](https://github.com/Drapersniper/Qbitrr/commit/f8234cfcec0d36fb3fdab48d13b73e75dc493fac) - @Drapersniper
- [Fix a bug where torrent files will be constantly checked.](https://github.com/Drapersniper/Qbitrr/commit/9ba051de060d409d12b1f24dc3da34001fe8eab9) - @Drapersniper
- [bug fixes and edge cases](https://github.com/Drapersniper/Qbitrr/commit/64a22cfff912f9a0792311a17267ce0692753426) - @Drapersniper
- [add a timer config for ombi search frequency, and fix a bug or two.](https://github.com/Drapersniper/Qbitrr/commit/2159e42678043702e1a3ed2bba0a6069782c0244) - @Drapersniper
- [Increases how often Ombi request from every loop to every item in the loop (A loop can tak 1000's of iterations)](https://github.com/Drapersniper/Qbitrr/commit/7fd1b3da675e3a50324efb70c324f821d2ac603b) - @Drapersniper
- [Closes #3](https://github.com/Drapersniper/Qbitrr/commit/66c784057d4a358538e3a3611ea7bea4829efdeb) - @Drapersniper
- [isort](https://github.com/Drapersniper/Qbitrr/commit/7b89ff0052b08d86cf31ab7e25f2ecf4eeac92ba) - @Drapersniper
- [Fix a bug where the first and last day of the year weren't included on searches.](https://github.com/Drapersniper/Qbitrr/commit/4a98bb1ff278b15bbd28953b24e0a8f1ec5971d6) - @Drapersniper
- [Merge remote-tracking branch 'origin/master'](https://github.com/Drapersniper/Qbitrr/commit/6447007a40d2d0b0ec72cd12bfe8228c8161324e) - @Drapersniper
- [properly send completed command to Radarr instances](https://github.com/Drapersniper/Qbitrr/commit/eea0f6a6dec1f7d1f4050df900804011a87c4f37) - @Drapersniper
- [Update README.md](https://github.com/Drapersniper/Qbitrr/commit/34312b67ccaf623875b2cebe5978f2987ea21e1e) - @Drapersniper
- [Properly update Radarr's DB and fix a few outdated attribute access.](https://github.com/Drapersniper/Qbitrr/commit/de73418efd15bf91a1ed7f23a9fb6ebc17328a68) - @Drapersniper
- [Update example config](https://github.com/Drapersniper/Qbitrr/commit/de96b4b2c9ffbf43f4fb3a720f02b50e5fb178ba) - @Drapersniper
- [Make everything have its own process to monitor categories in parallel, also add the ability to search for missing episodes (Arrs MissingSearch only does one item at a time, this script does up to 3 at a time, assuming theres no other tasks in progress.)](https://github.com/Drapersniper/Qbitrr/commit/2069982aa527662e86577b029434c298ebc1afd5) - @Drapersniper
- [more logging](https://github.com/Drapersniper/Qbitrr/commit/2d6ea31a08db27ef48fa626ef79be80d02cc2fdc) - @Drapersniper
- [Improved error handled, add a `is_alive` check to arr instances and qBit client](https://github.com/Drapersniper/Qbitrr/commit/e955fef85b11c95346e4d22a0038c8e8d6985a19) - @Drapersniper
- [remove unnecessary part of logs](https://github.com/Drapersniper/Qbitrr/commit/da3f81bccafe0150c09d0164f0d16f8e24b8a43b) - @Drapersniper
- [fix a crash due to missing attribute](https://github.com/Drapersniper/Qbitrr/commit/2d1ac7d01c64cc26a42a7e1a18d9d09ea487bbed) - @Drapersniper
- [ffs](https://github.com/Drapersniper/Qbitrr/commit/3a0d9ac59369db219e36ac3b0905b810ee08476c) - @Drapersniper
- [Update logs so that the formatting is consistent.](https://github.com/Drapersniper/Qbitrr/commit/2a5fe9b6a496e5bd519e2742b5088de8c5eef443) - @Drapersniper
- [update folder cleanup to only run if the category performed some action in a given iteration](https://github.com/Drapersniper/Qbitrr/commit/51b77c3f9d3ac0c5ac1c4ba2bff657b0edd1c443) - @Drapersniper
- [improve logic to check for valid connectivity](https://github.com/Drapersniper/Qbitrr/commit/b0a4dcaa714dbd62bae52946cfcbbb67a4acd7d0) - @Drapersniper
- [the regex here is too greedy and was matching anything with "op" or "ed" in the name which was problematic, added word bound which should hopefully fix it.](https://github.com/Drapersniper/Qbitrr/commit/32ae089fb50a73cfba37d059aa598b5eab42291f) - @Drapersniper
- [missed these 2 logger namescapes](https://github.com/Drapersniper/Qbitrr/commit/e8750ed433f1ab38f80eb4b87b174c35bfacb60c) - @Drapersniper
- [add colorama dep, makes it so logs are colored and easier to read](https://github.com/Drapersniper/Qbitrr/commit/2975b5e9948bdf9e9fb989d151b95e039da54f02) - @Drapersniper
- [well fix this](https://github.com/Drapersniper/Qbitrr/commit/0d26ac6d2eb8398a808c804568080d46a175e5a6) - @Drapersniper
- [Add a new clause to delete torrents which have achieved "MaximumDeletablePercentage" but have stalled for longer than "MaximumETA", this is to avoid hundreds of 99.9% torrents, but still give them some time to try to complete.](https://github.com/Drapersniper/Qbitrr/commit/af664229096a5c641e06e91ffc509399d31657dd) - @Drapersniper
- [Allow much more granular control per category.  (Sonnar1 and sonarr 2 can have different file exclusions, or import motes or rss timers for example.)](https://github.com/Drapersniper/Qbitrr/commit/6395c6585b2e0cf553ba846ac0f6d01921826d63) - @Drapersniper
- [Improve logging name space and logic, also make smaller api calls to Qbit as large calls have the tendency to slow it down/freeze it (Calls are groupped by category)](https://github.com/Drapersniper/Qbitrr/commit/d45898a2157b68d88a513a7cb46ba7fb54dea9f8) - @Drapersniper
- [Fix logging namespace](https://github.com/Drapersniper/Qbitrr/commit/1dda3a3319177324bdf3e4a8381d47a19d4a1bfa) - @Drapersniper
- [Refeactor, allowing multiple (nth) number of Arr instances (Radarr and Sonarr only).](https://github.com/Drapersniper/Qbitrr/commit/0003544713a2cd4a40ab31b16c98cd22a411faaf) - @Drapersniper
- [Probably ignored Force Upload](https://github.com/Drapersniper/Qbitrr/commit/2e84b0eea13918b21aced53b3873d9c0473824e7) - @Drapersniper
- [handle a minor edge case which would keep a torrent paused indefinitely](https://github.com/Drapersniper/Qbitrr/commit/398bd31654458a1f017f3a0c044ba635ae95cdf1) - @Drapersniper
- [Force V3 Endpoint](https://github.com/Drapersniper/Qbitrr/commit/dadd88e2556853ccbbda05c99de454c14e699fde) - @Drapersniper
- [Add a 4K instance of Radarr ... yes i could make it more efficient but copy paste is king](https://github.com/Drapersniper/Qbitrr/commit/388095f4d0717a9acedfaa56bbf7cfe032d5c7db) - @Drapersniper
- [Few fixes and support for 2 Sonarr instances](https://github.com/Drapersniper/Qbitrr/commit/26d3f3bfcc9590dbe960d075af7861d2c18ea8f6) - @Drapersniper
- [refactor](https://github.com/Drapersniper/Qbitrr/commit/13a714c272954110bcdb5291a50a395f28916222) - @Drapersniper
- [Black formatting](https://github.com/Drapersniper/Qbitrr/commit/7cd108ff602c90ee9a94c764dbec46c2c65851c8) - @Drapersniper
- [Black formatting](https://github.com/Drapersniper/Qbitrr/commit/df623f8fd8513906d924c553e1a0c0fa17de75ea) - @Drapersniper
- [well should pay more attention to copy-paste](https://github.com/Drapersniper/Qbitrr/commit/bb0c1baa10fa75008b373c93c861b4fb1f3dafb3) - @Drapersniper
- [there is no reason for these to continue being global.](https://github.com/Drapersniper/Qbitrr/commit/1b095094acd383308cac667484b6dd8aaca5dc10) - @Drapersniper
- [Add controls to tell arr's tp RssSync amd RefreshMonitoredDownloads.](https://github.com/Drapersniper/Qbitrr/commit/085d7a4d333bdaad86034f2d53f0618bec3fc21b) - @Drapersniper
- [Improve the logic a little.](https://github.com/Drapersniper/Qbitrr/commit/03186161c624d7cae2de0cdeffbbad9346aae75a) - @Drapersniper
- [Allow you to manually mark a torrent as failure by changing its category to specified one.](https://github.com/Drapersniper/Qbitrr/commit/002005a492acbc9634690d0b657e7a45f846067e) - @Drapersniper
- [Add more trace logging, fix `folder_cleanup` logic, and allow multiple URLs to be specified for ping purposes.](https://github.com/Drapersniper/Qbitrr/commit/c3d17c7f921997743b4ed05f1a19d6fb7fe9d3a8) - @Drapersniper
- [Merge remote-tracking branch 'origin/master'](https://github.com/Drapersniper/Qbitrr/commit/2181d778f98cadbe394aaff8f953671aca33db2f) - @Drapersniper
- [fix wrong attribute access](https://github.com/Drapersniper/Qbitrr/commit/66a3e05865ae0a179d9060ff038fc1f43d029564) - @Drapersniper
- [Update README.md](https://github.com/Drapersniper/Qbitrr/commit/99a13e7d9d3d72ec9d9f42673523f40c8bdf4002) - @Drapersniper
- [Merge remote-tracking branch 'origin/master'](https://github.com/Drapersniper/Qbitrr/commit/6b3908014492c54e7134c4567c8695e3686d140b) - @Drapersniper
- [fix wrong attribute access](https://github.com/Drapersniper/Qbitrr/commit/a5ae638f19072965ac6c7e039e737e8263a805cd) - @Drapersniper
- [Update README.md](https://github.com/Drapersniper/Qbitrr/commit/28ddc55fb1628b70b9a0cc193a0bb6ad896cc27d) - @Drapersniper
- [Update README.md](https://github.com/Drapersniper/Qbitrr/commit/09a1050d784605a57d2544de6b318b4371c84a42) - @Drapersniper
- [Merge remote-tracking branch 'origin/master'](https://github.com/Drapersniper/Qbitrr/commit/606be0bb3212cf9424cb61858f14de66326003aa) - @Drapersniper
- [Better logging around no internet.](https://github.com/Drapersniper/Qbitrr/commit/bce287059d34683f65e1b8c4246c22134a4e525c) - @Drapersniper
- [delete old file](https://github.com/Drapersniper/Qbitrr/commit/9ed4083aa0a1b545e6966a577b6ec4a6e235d573) - @Drapersniper
- [Create README.md](https://github.com/Drapersniper/Qbitrr/commit/5c2a3e95dae17c6bb2cf4fe0c3cd5c8da50413c5) - @Drapersniper
- [gitignore](https://github.com/Drapersniper/Qbitrr/commit/181699433ac7db32e186cdb405e21573ea300cc4) - @Drapersniper
