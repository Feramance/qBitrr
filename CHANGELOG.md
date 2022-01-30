# Changelog

## v2.3.0 (30/01/2022)
- [[minor] ensure the script does not run on unsupported version of qbittorrent.](https://github.com/Drapersniper/Qbitrr/commit/e07e8bcd78a7c810c56e396861fe7a9e7694264f) - @Drapersniper
- [[dev] Improve maintainability of requirements](https://github.com/Drapersniper/Qbitrr/commit/8bf53c1bf1780c70ae3824bdeead562d5300f1ba) - @Drapersniper

---

## v2.2.5 (28/01/2022)
- [[patch] Fixed seeding logic finally?](https://github.com/Drapersniper/Qbitrr/commit/2fcaa00d892ecd6c4f7eee3a606f00feb73763c1) - @Drapersniper
- [Merge remote-tracking branch 'origin/master'](https://github.com/Drapersniper/Qbitrr/commit/2c9b4576071e12cdf54899783c90003fede5e585) - @Drapersniper
- [[patch] Fix seeding logic to avoid these stupid ass conflicts](https://github.com/Drapersniper/Qbitrr/commit/ea397d8ea45fad8d7c974fce2f51d2cd33efeaed) - @Drapersniper

---

## v2.2.4 (28/01/2022)
- [[patch] Fixed both bugs reported by stats on discord](https://github.com/Drapersniper/Qbitrr/commit/4c67f5f92d78cfaac3b5f9151374a5dac8a3b3fb) - @Drapersniper
- [Ensure that binaries and docker contain the frozen version requirements](https://github.com/Drapersniper/Qbitrr/commit/a8ff848a27f58657c44c1490eef76bbfe4663256) - @Drapersniper
- [Fix a crash caused when attempting to get release data but the API didn't return a string as documented](https://github.com/Drapersniper/Qbitrr/commit/2a140fe9bd8c043e29d18cc49ba758e2d9449600) - @Drapersniper
- [[dep] Better docker env detection](https://github.com/Drapersniper/Qbitrr/commit/59c2824ad5f15f4bababb59ea8e9817b48ac2164) - @Drapersniper

---

## v2.2.3 (27/01/2022)
- [[patch] Push a tag with version to keep historical versions](https://github.com/Drapersniper/Qbitrr/commit/c340fefabe7271da1862908c3c7349f8b87d65f0) - @Drapersniper

---

## v2.2.2 (27/01/2022)
- [[patch] Hotfix a crash introduced by the last update and improve the seeding logic](https://github.com/Drapersniper/Qbitrr/commit/0ad0e4d8074ee7f0e885339717a8247c32df5d17) - @Drapersniper

---

## v2.2.1 (27/01/2022)
- [[patch] Query release date from overseerr to avoid searching movies/series that have not been released](https://github.com/Drapersniper/Qbitrr/commit/0d21cca8fc7f1105f32601a61702ca00deb838bc) - @Drapersniper
- [improve the code around GET requests to make it more maintainable](https://github.com/Drapersniper/Qbitrr/commit/a7d55ce9cca7a0bb458df006baba5d6cba282c92) - @Drapersniper
- [[Fix] Fix an issue where torrents were not allowed to seed regardless of the setting in config](https://github.com/Drapersniper/Qbitrr/commit/a32e7ff8fb6124f6939b83719122380b1f05011a) - @Drapersniper
- [[docs] Add tty:true key to docker compose example to ensure correct logs colour when using `docker-compose logs`](https://github.com/Drapersniper/Qbitrr/commit/67da2992fd50f1481b7e952662221072ef84db0e) - @Drapersniper
- [Bump stefanzweifel/git-auto-commit-action from 4.12.0 to 4.13.1](https://github.com/Drapersniper/Qbitrr/commit/ca61fce6d75ec1f66a5c657a264f7994380ce243) - @dependabot[bot]

---

## v2.2.0 (25/01/2022)
- [[minor] Add support for Docker and create a docker image (#26)](https://github.com/Drapersniper/Qbitrr/commit/635fd14c9cb7b7672ec301af3c388f62d78c051c) - @Drapersniper

---

## v2.1.20 (30/12/2021)
- [[patch] Fix yet another edge case around marking torrents as failed when they aren't actually failed](https://github.com/Drapersniper/Qbitrr/commit/d6752d1587fd98064b3c94c502587ae9458eb0b4) - @Drapersniper

---

## v2.1.19 (30/12/2021)


---

## v2.0.1 (30/12/2021)
- [[patch] Deploy release](https://github.com/Drapersniper/Qbitrr/commit/b102f849ecb4b2787b65c60bb87741703ad77188) - @Drapersniper
- [[Admin] Optimize GitHub workflows to reuse variables and depend on one another also add the binary workflow to pull requests](https://github.com/Drapersniper/Qbitrr/commit/aead207d3bc93f7cdb16d044f401b229986fe4af) - @Drapersniper
- [[fix] Make the loops sleep if qBitTorrent is unresponsive and raises an api error](https://github.com/Drapersniper/Qbitrr/commit/decc9492531042a103212aaca611df134d5897a0) - @Drapersniper
- [[patch] Fix for #6](https://github.com/Drapersniper/Qbitrr/commit/45154415d52eb19a36fa63997a098bae5f7f954d) - @Drapersniper
- [[fix] Fix an issue that causes a specific log line to fail.](https://github.com/Drapersniper/Qbitrr/commit/e66ed28a2d4b22f5fd0eb0f2913a5c405ec0064d) - @Drapersniper
- [[fix] Fix an issue where an old table field was causing crashes with Radarr file searches](https://github.com/Drapersniper/Qbitrr/commit/6da841636059aeac3f89ab5c4b870373eac64ae4) - @Drapersniper
- [[patch] Fix the previous issue properly](https://github.com/Drapersniper/Qbitrr/commit/34f231b2091f14c88c75a9274bcf7e9b1c671b6e) - @Drapersniper
- [[patch] Resolve bad conflict resolution](https://github.com/Drapersniper/Qbitrr/commit/3448dd29c90b74bf81d1b3c3962ec8eba000c5ca) - @Drapersniper
- [[patch] Full fix for https://github.com/Drapersniper/Qbitrr/issues/19#issuecomment-999970944](https://github.com/Drapersniper/Qbitrr/commit/7c8f46d56701df7b938e5def82bd0b40b37e468e) - @Drapersniper
- [[patch] Temp fix for https://github.com/Drapersniper/Qbitrr/issues/19#issuecomment-999970944](https://github.com/Drapersniper/Qbitrr/commit/746a769d44fc3ed8256adc3ca0f4a31599b07706) - @Drapersniper
- [Update setup instructions](https://github.com/Drapersniper/Qbitrr/commit/d59424239516be1c5513f2e4cea6c32e1eabba40) - @Drapersniper
- [[patch] Hotfix - Remove ujson support for any python implementation that is not CPython due to the SystemError crash that occurred on PyPy](https://github.com/Drapersniper/Qbitrr/commit/0a3ff2da674076630e03a73e7f7782fbfa673697) - @Drapersniper
- [[patch] replace requests complexjson with ujson if it is available (This affects the whole runtime meaning assuming the response isn't unsupported it should give a significant boost to requests performance.](https://github.com/Drapersniper/Qbitrr/commit/1ee15b5d3182251c6dcb127c7555205e95809ba1) - @Drapersniper
- [[deps] Add ujson as an optional dep](https://github.com/Drapersniper/Qbitrr/commit/320f785e9c79e18772355e064650cba0a93a15d3) - @Drapersniper
- [[patch] Make release](https://github.com/Drapersniper/Qbitrr/commit/441b54ec7eb294a919a00ba0b76e001aabd3ed35) - @Drapersniper
- [[patch] Fix an issue where you couldn't run any flags if the config file didn't exist in the app dir](https://github.com/Drapersniper/Qbitrr/commit/3dfb989bef624fa68e7730de9e91f93b2f3f51e3) - @Drapersniper
- [[patch] Make release](https://github.com/Drapersniper/Qbitrr/commit/7500811a97be6a7befdaeed347a32bec7895bdf6) - @Drapersniper
- [[patch] config file](https://github.com/Drapersniper/Qbitrr/commit/71a22ecf8038a6e6b8e16f27ecf14b542f4d7082) - @Drapersniper
- [[patch] Fix broken builds](https://github.com/Drapersniper/Qbitrr/commit/1e201e0b56fa3952aecfbbc3f9dfa297b552d935) - @Drapersniper
- [[patch] Hotfix](https://github.com/Drapersniper/Qbitrr/commit/9eeb34372ddd0ce680841f2ebc40c93ee4e6acf3) - @Drapersniper
- [[patch] clean up and fixes](https://github.com/Drapersniper/Qbitrr/commit/d3c7351a6d6e651c590dcbc54a6f93dbb9374703) - @Drapersniper
- [add `--license` and `--source` flags to the script](https://github.com/Drapersniper/Qbitrr/commit/f94c3e3c005ffd0df02a77bae310349e5a4a2f90) - @Drapersniper
- [add `--version` flag and update README.md](https://github.com/Drapersniper/Qbitrr/commit/7fa3e9d1b66fe871ddf72e77a6cdb48ef7832ae4) - @Drapersniper
- [Improve internet check so that it does not run if there is no torrents to check](https://github.com/Drapersniper/Qbitrr/commit/c201c535698a7e553b4ef90eb518c86f794d0e9c) - @Drapersniper
- [[patch] Improved startup logging](https://github.com/Drapersniper/Qbitrr/commit/d858027c2bfb004f3b9ddf9ba0e71b83e8a1c977) - @Drapersniper
- [Reduce the number of socket calls for the internet checks](https://github.com/Drapersniper/Qbitrr/commit/9c0686e5ae2957eeea71476d42303d77270cf422) - @Drapersniper
- [[patch] Fixed an issue that caused logs to show incorrect info](https://github.com/Drapersniper/Qbitrr/commit/6ed607e6d102c6937a14e357a331e2753f609087) - @Drapersniper
- [Ensure KeyboardInterrupt is caught correctly + fix an issue where logs where being duplicated](https://github.com/Drapersniper/Qbitrr/commit/313a26ffa21bfb0929921101d73cb39f65cbf002) - @Drapersniper
- [Fixed a bug where there would be a crash if the user attempted to add a torrent to the recheck or failed category](https://github.com/Drapersniper/Qbitrr/commit/e4da075d0e864ec4f23c19bb1caf87cd8070151e) - @Drapersniper
- [[patch] 2 enhancements and 1 bug fix.](https://github.com/Drapersniper/Qbitrr/commit/3e285bcf7dea29fa234508a8a920400f6b85e3f1) - @Drapersniper
- [[patch] Build binary for all platforms properly](https://github.com/Drapersniper/Qbitrr/commit/23a65f963341123024f85f2ef110689e492e6b89) - @Drapersniper
- [[patch] Fix an issue where logs where not shown correct + improve exiting logic](https://github.com/Drapersniper/Qbitrr/commit/3aa3f39c1d052e3b8201a7606fb3504077897ffc) - @Drapersniper
- [Fixed the build spec to generate a portable binary](https://github.com/Drapersniper/Qbitrr/commit/4d2db601905f756289b15bef5f5219e131580fcf) - @Drapersniper
- [[patch] Build binaries - properly this time v2](https://github.com/Drapersniper/Qbitrr/commit/da31cf5f135530cb7c2e0062f711f7b813b99f46) - @Drapersniper
- [[patch] Build binaries - properly this time](https://github.com/Drapersniper/Qbitrr/commit/27784e1a96fba4b19fcfc1ae1a6a4bd2ac88439f) - @Drapersniper
- [[patch] Build binaries](https://github.com/Drapersniper/Qbitrr/commit/9a4db8491deac9867975ecaab7f385d51eee8537) - @Drapersniper

---

## v2.1.18 (30/12/2021)
- [[patch] Deploy release](https://github.com/Drapersniper/Qbitrr/commit/b102f849ecb4b2787b65c60bb87741703ad77188) - @Drapersniper
- [[Admin] Optimize GitHub workflows to reuse variables and depend on one another also add the binary workflow to pull requests](https://github.com/Drapersniper/Qbitrr/commit/aead207d3bc93f7cdb16d044f401b229986fe4af) - @Drapersniper
- [[fix] Make the loops sleep if qBitTorrent is unresponsive and raises an api error](https://github.com/Drapersniper/Qbitrr/commit/decc9492531042a103212aaca611df134d5897a0) - @Drapersniper

---

## v2.1.17 (30/12/2021)
- [[patch] Fix for #6](https://github.com/Drapersniper/Qbitrr/commit/45154415d52eb19a36fa63997a098bae5f7f954d) - @Drapersniper
- [[fix] Fix an issue that causes a specific log line to fail.](https://github.com/Drapersniper/Qbitrr/commit/e66ed28a2d4b22f5fd0eb0f2913a5c405ec0064d) - @Drapersniper
- [[fix] Fix an issue where an old table field was causing crashes with Radarr file searches](https://github.com/Drapersniper/Qbitrr/commit/6da841636059aeac3f89ab5c4b870373eac64ae4) - @Drapersniper

---

## v2.1.16 (23/12/2021)
- [[patch] Fix the previous issue properly](https://github.com/Drapersniper/Qbitrr/commit/34f231b2091f14c88c75a9274bcf7e9b1c671b6e) - @Drapersniper

---

## v2.1.15 (23/12/2021)
- [[patch] Resolve bad conflict resolution](https://github.com/Drapersniper/Qbitrr/commit/3448dd29c90b74bf81d1b3c3962ec8eba000c5ca) - @Drapersniper
- [[patch] Full fix for https://github.com/Drapersniper/Qbitrr/issues/19#issuecomment-999970944](https://github.com/Drapersniper/Qbitrr/commit/7c8f46d56701df7b938e5def82bd0b40b37e468e) - @Drapersniper

---

## v2.1.14 (23/12/2021)
- [[patch] Temp fix for https://github.com/Drapersniper/Qbitrr/issues/19#issuecomment-999970944](https://github.com/Drapersniper/Qbitrr/commit/746a769d44fc3ed8256adc3ca0f4a31599b07706) - @Drapersniper
- [Update setup instructions](https://github.com/Drapersniper/Qbitrr/commit/d59424239516be1c5513f2e4cea6c32e1eabba40) - @Drapersniper

---

## v2.1.13 (20/12/2021)
- [[patch] Hotfix - Remove ujson support for any python implementation that is not CPython due to the SystemError crash that occurred on PyPy](https://github.com/Drapersniper/Qbitrr/commit/0a3ff2da674076630e03a73e7f7782fbfa673697) - @Drapersniper

---

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
- [[minor] Minor release to fix issue with config file across the separate processed - reason it is breaking is due to the removal of the `--config` flag](https://github.com/Drapersniper/Qbitrr/commit/2f51db77c3ef8c0bdd4d432454f02bd4b9f66f60) - @Drapersniper
- [Update config.example.toml](https://github.com/Drapersniper/Qbitrr/commit/eb4ce73af082cd918f389aee6611229f15192a8c) - @JacquesLG

---

## v2.0.4 (18/12/2021)
- [[patch] bump to deploy](https://github.com/Drapersniper/Qbitrr/commit/4867f2b9ebaa5941b2a879149f9146900817c03a) - @Drapersniper
