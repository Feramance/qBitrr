[![PyPI](https://img.shields.io/pypi/v/qBitrr)](https://pypi.org/project/qBitrr/)
[![PyPI](https://img.shields.io/pypi/dm/qbitrr)](https://pypi.org/project/qBitrr/)
[![PyPI - License](https://img.shields.io/pypi/l/qbitrr)](https://github.com/Drapersniper/Qbitrr/blob/master/LICENSE)

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/qbitrr)
![Platforms](https://img.shields.io/badge/platform-linux--64%20%7C%20osx--64%20%7C%20win--32%20%7C%20win--64-lightgrey)

[![CodeQL status](https://github.com/Drapersniper/Qbitrr/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/Drapersniper/Qbitrr/actions/workflows/codeql-analysis.yml)
[![Generate Change Logs](https://github.com/Drapersniper/Qbitrr/actions/workflows/chane_logs.yml/badge.svg)](https://github.com/Drapersniper/Qbitrr/actions/workflows/chane_logs.yml)
[![Build Binaries](https://github.com/Drapersniper/Qbitrr/actions/workflows/upload_binaries.yml/badge.svg)](https://github.com/Drapersniper/Qbitrr/actions/workflows/upload_binaries.yml)
[![Publish to PyPi](https://github.com/Drapersniper/Qbitrr/actions/workflows/publish.yml/badge.svg)](https://github.com/Drapersniper/Qbitrr/actions/workflows/publish.yml)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Drapersniper/Qbitrr/master.svg)](https://results.pre-commit.ci/latest/github/Drapersniper/Qbitrr/master)

[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

A simple script to monitor [Qbit](https://github.com/qbittorrent/qBittorrent) and communicate with [Radarr](https://github.com/Radarr/Radarr) and [Sonarr](https://github.com/Sonarr/Sonarr)

Join the [Official Discord Server](https://discord.gg/FT3puape2A) for help.

### Features

- Monitor qBit for Stalled/bad entries and delete them then blacklist them on Arrs (Option to also trigger a re-search action).
- Monitor qBit for completed entries and tell the appropriate Arr instance to import it ( 'DownloadedMoviesScan' or 'DownloadedEpisodesScan' commands).
- Skip files in qBit entries by extension, folder or regex.
- Monitor completed folder and cleans it up.
- Uses [ffprobe](https://github.com/FFmpeg/FFmpeg) to ensure downloaded entries are valid media.
- Trigger periodic Rss Syncs on the appropriate Arr instances.
- Trigger Queue update on appropriate Arr instances.
- Search requests from [Overseerr](https://github.com/sct/overseerr) or [Ombi](https://github.com/Ombi-app/Ombi).

**This section requires the Arr databases to be locally available.**

- Monitor Arr's databases to trigger missing episode searches.
- Customizable year range to search for (at a later point will add more option here, for example search whole series/season instead of individual episodes, search by name, category etc).

### Important mentions

Some things to know before using it.

- 1. You need to run the `qbitrr --gen-config` move the generated file to `~/.config/qBitManager/config.toml` (~ is your home directory, i.e `C:\Users\{User}`)
- 2. I have [Sonarr](https://github.com/Sonarr/Sonarr) and [Radarr](https://github.com/Radarr/Radarr) both setup to add tags to all downloads.
- 3. I have qBit setup to have to create sub-folder for downloads and for the download folder to
     use subcategories.

  ![image](https://user-images.githubusercontent.com/27962761/139117102-ec1d321a-1e64-4880-8ad1-ee2c9b805f92.png)

- 4. Make sure to have [`ffprobe`](https://www.ffmpeg.org/download.html) added to your PATH.

#### Install the requirements run

- `python -m pip install qBitrr` (I would recommend in a dedicated [venv](https://docs.python.org/3.3/library/venv.html) but that's out of scope.

#### Run the script

- Make sure to update the settings in `~/.config/qBitManager/config.toml`
- Activate your venv
- Run `qbitrr`

#### How to update the script

- Activate your venv
- Run `python -m pip install -U qBitrr`

#### Contributions

- I'm happy with any PRs and suggested changes to the logic I just put it together dirty for my own use case.

#### Example behaviour

![image](https://user-images.githubusercontent.com/27962761/146447714-5309d3e6-51fd-472c-9587-9df491f121b3.png)
