# Changelog

## v2.6.0 (09/10/2022)
- [[minor] Update to work with newer qbittorrent version](https://github.com/Feramance/Qbitrr/commit/c02c36d7d924cd8e54416568115ec495544c5136) - @Feramance
- [Bump to qbittorrent-api==2023.7.52](https://github.com/Feramance/Qbitrr/commit/bfe3af3f432e8870a89e616263ec8a3b2a9dc883) - @Feramance
- [Bump stefanzweifel/git-auto-commit-action from 4.14.1 to 4.15.0](https://github.com/Feramance/Qbitrr/commit/76cc5a1d5b1a1d6aa10eda625621cff62b25ae84) - @dependabot[bot]
- [De Morgan's laws](https://github.com/Feramance/Qbitrr/commit/e7cef49b912b611a934c679340ba7e4f2db00502) - @Feramance
- [Bump ujson from 5.2.0 to 5.4.0](https://github.com/Feramance/Qbitrr/commit/39cdf4c966bb349d1d3e896ab27db962fa5609c2) - @dependabot[bot]
- [Update README.md](https://github.com/Feramance/Qbitrr/commit/9c66b02ce131414aa51ac842ea43f717c41d4a24) - @Feramance

---

## v2.5.5 (19/06/2022)
- [[patch] allow qbitrr to run agaisnt qBitTorrent 4.4+](https://github.com/Feramance/Qbitrr/commit/542ba3b5557aa8a37759f7ea2d89e96eb447da92) - @Feramance
- [Closes #58 by allowing qbitrr to run against qBitTorrent 4.4+ - <4.5, Historically this has broken several things as the API for qbittorrent was returning bad values.](https://github.com/Feramance/Qbitrr/commit/7e0178eabfe7690fb06cf9fe9c12f5a8955c4561) - @Feramance
- [Bump ujson from 5.1.0 to 5.2.0](https://github.com/Feramance/Qbitrr/commit/e3483d7f9de4f23619e0387ae64c986c4290cb1b) - @dependabot[bot]
- [Bump crazy-max/ghaction-import-gpg from 4 to 5](https://github.com/Feramance/Qbitrr/commit/9b01efbdee7b3ebe02bc36dde5ea6bd7db79380d) - @dependabot[bot]
- [Bump actions/setup-python from 3 to 4](https://github.com/Feramance/Qbitrr/commit/cd24e366dee8a8e065883876577def8d74db76be) - @dependabot[bot]
- [Bump docker/login-action from 1 to 2](https://github.com/Feramance/Qbitrr/commit/146b18525d64bcde1443dbec484296bbb04d06a1) - @dependabot[bot]
- [Bump stefanzweifel/git-auto-commit-action from 4.13.1 to 4.14.1](https://github.com/Feramance/Qbitrr/commit/2c7ea60822f6032f6849b68adf3cbb24f196920b) - @dependabot[bot]
- [Bump actions/upload-artifact from 2 to 3](https://github.com/Feramance/Qbitrr/commit/05ca15f7d7c3a85dfcad2c6aa187a0e0068967ad) - @dependabot[bot]
- [Bump docker/setup-buildx-action from 1 to 2](https://github.com/Feramance/Qbitrr/commit/97933c295966d730a99f8bf0175d3d59393c6ec7) - @dependabot[bot]
- [Bump docker/setup-qemu-action from 1 to 2](https://github.com/Feramance/Qbitrr/commit/ec8a415f38643481da8a165c1149988189484e6d) - @dependabot[bot]
- [Bump github/codeql-action from 1 to 2](https://github.com/Feramance/Qbitrr/commit/a92376d60c9ab0091e697261bae9ba2035c59f44) - @dependabot[bot]
- [Bump docker/build-push-action from 2 to 3](https://github.com/Feramance/Qbitrr/commit/e6e718a52f2dcce278a7614dc17ae586d332e98a) - @dependabot[bot]
- [Bump actions/setup-python from 2 to 3](https://github.com/Feramance/Qbitrr/commit/cd4b2259bcfd7284f7e81d958493ffc232ba3d9e) - @dependabot[bot]
- [Bump actions/checkout from 2 to 3](https://github.com/Feramance/Qbitrr/commit/5913935447dad075fb9b45c0f1f98ca4cc4b1e13) - @dependabot[bot]
- [Bump actions/setup-node from 2 to 3](https://github.com/Feramance/Qbitrr/commit/bb548bbe9955357ed24353fbf0497b0f7ecf4750) - @dependabot[bot]

---

## v2.5.4 (26/02/2022)
- [[patch] properly accept empty `FolderExclusionRegex` and `FileNameExclusionRegex`](https://github.com/Feramance/Qbitrr/commit/a4eb4079599b04fd5ddee6fa5c19a4d69f503c30) - @Feramance

---

## v2.5.3 (26/02/2022)
- [[patch] allow setting `FileExtensionAllowlist` to an empty list to allow all file extensions](https://github.com/Feramance/Qbitrr/commit/e1f278533f2857dbc87dcbac4dcd9dcddfb2639b) - @Feramance

---

## v2.5.2 (18/02/2022)
- [[patch] hotfix stop crashing the script on an invalid config key for Arrs (it will still crash on invalid global values, i.e Log level), provide better logging when unable to load the config file.](https://github.com/Feramance/Qbitrr/commit/f7abf79cc0c86213fb01a07f3a2f3243aad66cd0) - @Feramance

---

## v2.5.1 (18/02/2022)
- [[patch] hotfix to handle edge case](https://github.com/Feramance/Qbitrr/commit/889ffbdb1b31f4d75300df56fb27f2445cafcf27) - @Feramance

---

## v2.5.0 (18/02/2022)
- [[minor] Catch `TypeError` when building an Arr instance and build an invalid path when required](https://github.com/Feramance/Qbitrr/commit/fef795d067f7a02ba2939389f104c0845e995214) - @Feramance

---

## v2.4.2 (01/02/2022)
- [[patch] apply "fix" in all relevant locations](https://github.com/Feramance/Qbitrr/commit/bb8d8919e3b89ab09a130e43a6776c59dfca93ef) - @Feramance

---

## v2.4.1 (01/02/2022)
- [[patch] the qbittorrent api is being weird af ... why is it returning non existing torrents with  missing attributes](https://github.com/Feramance/Qbitrr/commit/cace1010a757868fff7cf951e35aee0204e6e771) - @Feramance

---

## v2.4.0 (01/02/2022)
- [[minor] Add Environment variable support for some config as well as overrides for some variables](https://github.com/Feramance/Qbitrr/commit/56e77bb606d215ef8c9d4b30935824c4686174ab) - @Feramance

---

## v2.3.4 (31/01/2022)
- [[patch] Fix broken log line](https://github.com/Feramance/Qbitrr/commit/28475f3be23e6f44162ec031492db25c88f94c25) - @Feramance
- [[patch] Fix indentation which was causing a crash](https://github.com/Feramance/Qbitrr/commit/11aac0db33559abc785bedbc6d66907742fcf25f) - @Feramance
- [[patch] Improvements for docker build](https://github.com/Feramance/Qbitrr/commit/d5ede08c859a647432910d5988597b0d57589c37) - @Feramance
- [[Feature] Add the ability to run the search functionality without a running instant of qBitTorrent](https://github.com/Feramance/Qbitrr/commit/bb918d95d7a262cecd05a36ccbd7fdd770c0245e) - @Feramance
- [[Dep] Update black dev dependency to 22.1.0](https://github.com/Feramance/Qbitrr/commit/578a92266030a28479a8b9e8f2584623ee6ebf45) - @Feramance
- [[enhancement] a Significant improvement for missing episode searches](https://github.com/Feramance/Qbitrr/commit/6b825a4bb3e33547425aceee2d592feac599cc04) - @Feramance

---

## v2.3.3 (30/01/2022)
- [[patch] disable arm builds until i figure out why the wheels are not pre-build](https://github.com/Feramance/Qbitrr/commit/78f7e6fdb6024481800bc688aaa419ef088ba060) - @Feramance

---

## v2.3.2 (30/01/2022)


---

## v2.3.1 (30/01/2022)

---

## v2.3.0 (30/01/2022)
- [[minor] ensure the script does not run on unsupported version of qbittorrent.](https://github.com/Feramance/Qbitrr/commit/e07e8bcd78a7c810c56e396861fe7a9e7694264f) - @Feramance
- [[dev] Improve maintainability of requirements](https://github.com/Feramance/Qbitrr/commit/8bf53c1bf1780c70ae3824bdeead562d5300f1ba) - @Feramance

---

## v2.2.5 (28/01/2022)
- [[patch] Fixed seeding logic finally?](https://github.com/Feramance/Qbitrr/commit/2fcaa00d892ecd6c4f7eee3a606f00feb73763c1) - @Feramance
- [Merge remote-tracking branch 'origin/master'](https://github.com/Feramance/Qbitrr/commit/2c9b4576071e12cdf54899783c90003fede5e585) - @Feramance
- [[patch] Fix seeding logic to avoid these stupid ass conflicts](https://github.com/Feramance/Qbitrr/commit/ea397d8ea45fad8d7c974fce2f51d2cd33efeaed) - @Feramance

---

## v2.2.4 (28/01/2022)
- [[patch] Fixed both bugs reported by stats on discord](https://github.com/Feramance/Qbitrr/commit/4c67f5f92d78cfaac3b5f9151374a5dac8a3b3fb) - @Feramance
- [Ensure that binaries and docker contain the frozen version requirements](https://github.com/Feramance/Qbitrr/commit/a8ff848a27f58657c44c1490eef76bbfe4663256) - @Feramance
- [Fix a crash caused when attempting to get release data but the API didn't return a string as documented](https://github.com/Feramance/Qbitrr/commit/2a140fe9bd8c043e29d18cc49ba758e2d9449600) - @Feramance
- [[dep] Better docker env detection](https://github.com/Feramance/Qbitrr/commit/59c2824ad5f15f4bababb59ea8e9817b48ac2164) - @Feramance

---

## v2.2.3 (27/01/2022)
- [[patch] Push a tag with version to keep historical versions](https://github.com/Feramance/Qbitrr/commit/c340fefabe7271da1862908c3c7349f8b87d65f0) - @Feramance

---

## v2.2.2 (27/01/2022)
- [[patch] Hotfix a crash introduced by the last update and improve the seeding logic](https://github.com/Feramance/Qbitrr/commit/0ad0e4d8074ee7f0e885339717a8247c32df5d17) - @Feramance

---

## v2.2.1 (27/01/2022)
- [[patch] Query release date from overseerr to avoid searching movies/series that have not been released](https://github.com/Feramance/Qbitrr/commit/0d21cca8fc7f1105f32601a61702ca00deb838bc) - @Feramance
- [improve the code around GET requests to make it more maintainable](https://github.com/Feramance/Qbitrr/commit/a7d55ce9cca7a0bb458df006baba5d6cba282c92) - @Feramance
- [[Fix] Fix an issue where torrents were not allowed to seed regardless of the setting in config](https://github.com/Feramance/Qbitrr/commit/a32e7ff8fb6124f6939b83719122380b1f05011a) - @Feramance
- [[docs] Add tty:true key to docker compose example to ensure correct logs colour when using `docker-compose logs`](https://github.com/Feramance/Qbitrr/commit/67da2992fd50f1481b7e952662221072ef84db0e) - @Feramance
- [Bump stefanzweifel/git-auto-commit-action from 4.12.0 to 4.13.1](https://github.com/Feramance/Qbitrr/commit/ca61fce6d75ec1f66a5c657a264f7994380ce243) - @dependabot[bot]

---

## v2.2.0 (25/01/2022)
- [[minor] Add support for Docker and create a docker image (#26)](https://github.com/Feramance/Qbitrr/commit/635fd14c9cb7b7672ec301af3c388f62d78c051c) - @Feramance

---

## v2.1.20 (30/12/2021)
- [[patch] Fix yet another edge case around marking torrents as failed when they aren't actually failed](https://github.com/Feramance/Qbitrr/commit/d6752d1587fd98064b3c94c502587ae9458eb0b4) - @Feramance

---

## v2.1.19 (30/12/2021)


---

## v2.1.18 (30/12/2021)
- [[patch] Deploy release](https://github.com/Feramance/Qbitrr/commit/b102f849ecb4b2787b65c60bb87741703ad77188) - @Feramance
- [[Admin] Optimize GitHub workflows to reuse variables and depend on one another also add the binary workflow to pull requests](https://github.com/Feramance/Qbitrr/commit/aead207d3bc93f7cdb16d044f401b229986fe4af) - @Feramance
- [[fix] Make the loops sleep if qBitTorrent is unresponsive and raises an api error](https://github.com/Feramance/Qbitrr/commit/decc9492531042a103212aaca611df134d5897a0) - @Feramance

---

## v2.1.17 (30/12/2021)
- [[patch] Fix for #6](https://github.com/Feramance/Qbitrr/commit/45154415d52eb19a36fa63997a098bae5f7f954d) - @Feramance
- [[fix] Fix an issue that causes a specific log line to fail.](https://github.com/Feramance/Qbitrr/commit/e66ed28a2d4b22f5fd0eb0f2913a5c405ec0064d) - @Feramance
- [[fix] Fix an issue where an old table field was causing crashes with Radarr file searches](https://github.com/Feramance/Qbitrr/commit/6da841636059aeac3f89ab5c4b870373eac64ae4) - @Feramance

---

## v2.1.16 (23/12/2021)
- [[patch] Fix the previous issue properly](https://github.com/Feramance/Qbitrr/commit/34f231b2091f14c88c75a9274bcf7e9b1c671b6e) - @Feramance

---

## v2.1.15 (23/12/2021)
- [[patch] Resolve bad conflict resolution](https://github.com/Feramance/Qbitrr/commit/3448dd29c90b74bf81d1b3c3962ec8eba000c5ca) - @Feramance
- [[patch] Full fix for https://github.com/Feramance/Qbitrr/issues/19#issuecomment-999970944](https://github.com/Feramance/Qbitrr/commit/7c8f46d56701df7b938e5def82bd0b40b37e468e) - @Feramance

---

## v2.1.14 (23/12/2021)
- [[patch] Temp fix for https://github.com/Feramance/Qbitrr/issues/19#issuecomment-999970944](https://github.com/Feramance/Qbitrr/commit/746a769d44fc3ed8256adc3ca0f4a31599b07706) - @Feramance
- [Update setup instructions](https://github.com/Feramance/Qbitrr/commit/d59424239516be1c5513f2e4cea6c32e1eabba40) - @Feramance

---

## v2.1.13 (20/12/2021)
- [[patch] Hotfix - Remove ujson support for any python implementation that is not CPython due to the SystemError crash that occurred on PyPy](https://github.com/Feramance/Qbitrr/commit/0a3ff2da674076630e03a73e7f7782fbfa673697) - @Feramance

---

## v2.1.12 (20/12/2021)
- [[patch] replace requests complexjson with ujson if it is available (This affects the whole runtime meaning assuming the response isn't unsupported it should give a significant boost to requests performance.](https://github.com/Feramance/Qbitrr/commit/1ee15b5d3182251c6dcb127c7555205e95809ba1) - @Feramance
- [[deps] Add ujson as an optional dep](https://github.com/Feramance/Qbitrr/commit/320f785e9c79e18772355e064650cba0a93a15d3) - @Feramance
