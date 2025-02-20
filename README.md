# <img src="assets/logo.png" width="32px"/> qBitrr

[![PyPI - License](https://img.shields.io/pypi/l/qbitrr)](https://github.com/Feramance/Qbitrr/blob/master/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/qBitrr2?label=PyPI)](https://pypi.org/project/qBitrr2/)
[![Downloads](https://img.shields.io/pypi/dm/qbitrr2)](https://pypi.org/project/qBitrr2/)
[![Pulls](https://img.shields.io/docker/pulls/feramance/qbitrr.svg)](https://hub.docker.com/r/feramance/qbitrr)

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/qbitrr)
[![Platforms](https://img.shields.io/badge/platform-linux--64%20%7C%20osx--64%20%7C%20win--32%20%7C%20win--64-lightgrey)](https://github.com/Feramance/qBitrr/releases/latest)

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/Feramance/qBitrr/master.svg)](https://results.pre-commit.ci/latest/github/Feramance/qBitrr/master)
[![CodeQL](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml)
[![Create a Release](https://github.com/Feramance/qBitrr/actions/workflows/release.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/release.yml)
[![Nightly Build](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml)

[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

A simple script to monitor [qBit](https://github.com/qbittorrent/qBittorrent) and communicate with [Radarr](https://github.com/Radarr/Radarr) and [Sonarr](https://github.com/Sonarr/Sonarr)

# POLL
[Request searches?](https://github.com/Feramance/qBitrr/discussions/149)

## Notice (slowly getting there, will take some time)

I am starting development on qBitrr+ which will be C# based for better overall performance and will also include a WebUI for better refined control on setting and what to search/upgrade etc. Hoping this will be the be all and end all application to manage your Radarr/Sonarr, Overseerr/Ombi and qBittorrent instances in one UI. This is still in it's very early stages and will likely be a couple months before a concrete alpha is rolled out (from start of February 2024). Once I have something solid I will remove this notice and  add a link to the new qBitrr+, in the meantime I will be sharing periodic updates on my [Patreon](https://patreon.com/qBitrr)

## Features

- Monitor qBit for Stalled/bad entries and delete them then blacklist them on Arrs (Option to also trigger a re-search action).
- Monitor qBit for completed entries and tell the appropriate Arr instance to import it:
  - `qbitrr DownloadedMoviesScan` for Radarr
  - `qbitrr DownloadedEpisodesScan` for Sonarr
- Skip files in qBit entries by extension, folder or regex.
- Monitor completed folder and clean it up.
- Usage of [ffprobe](https://github.com/FFmpeg/FFmpeg) to ensure downloaded entries are valid media.
- Trigger periodic Rss Syncs on the appropriate Arr instances.
- Trigger Queue update on appropriate Arr instances.
- Search requests from [Overseerr](https://github.com/sct/overseerr) or [Ombi](https://github.com/Ombi-app/Ombi).
- Auto add/remove trackers
- Set per tracker values
- **Sonarr v4 support**
- **Radarr v4 and v5 support**
- Monitor Arr's to trigger missing episode searches.
- Searches Radarr missing movies based on Minimum Availability
- Customizable searching by series or singular episodes
- Optionally searches year by year is ascending or descending order (config option available)
- Search for CF Score unmet and cancel torrents base on CF Score or Quality unmet search
- Set minimum free space in download directory and pause torrent downloads accordingly
- Change quality profile temporarily for missing items until found

## Tested with

Some things to know before using it.

- **Latest supported qbittorrent version is 4.6.7**
- qbittorrent v5 does not currently have a stable API. A config is available for those who wish to use it anyway but I will not be dealing with issues related to qbittorrent v5 for the time being
- qbittorrent >= 4.5.x
- [Sonarr](https://github.com/Sonarr/Sonarr) and [Radarr](https://github.com/Radarr/Radarr) both setup to add tags to all downloads.
- qBit set to create sub-folders for tag.

## Usage
### Native

- `python -m pip install qBitrr2` (I would recommend in a dedicated [venv](https://docs.python.org/3.3/library/venv.html) but that's out of scope.

Alternatively:
- Download the [latest release](https://github.com/Feramance/Qbitrr/releases/latest)

#### Run the script

1. Activate your venv
2. Run `qBitrr2`  to generate a config file
3. Edit the config file (located at `~/config/config.toml` (~ is your current directory)
4. Run `qBitrr2` if installed through pip again to start the script

Alternatively:
1. Unzip the downloaded release and run it
2. Run `qBitrr`  to generate a config file
3. Edit the config file (located at `~/config/config.toml` (~ is your current directory)
4. Run `qBitrr` if installed through pip again to start the script

#### How to update the script

1. Activate your venv
2. Run `python -m pip install -U qBitrr2`

Alternatively:
1. Download on the [latest release](https://github.com/Feramance/Qbitrr/releases/latest)
2. Unzip the downloaded release and run it
3. Run `qBitrr`  to generate a config file
4. Edit the config file (located at `~/config/config.toml` (~ is your current directory)
5. Run `qBitrr` if installed through pip again to start the script

***There is no auto-update feature, you will need to manually download the latest release and replace the old one.***

### Docker

#### Docker Image

- The docker image can be found on [DockerHub](https://hub.docker.com/r/feramance/qbitrr) or [Github](https://github.com/Feramance/qBitrr/pkgs/container/qbitrr)

#### Docker Run

```bash
docker run -d \
  --name=qbitrr \
  -e TZ=Europe/London \
  -v /etc/localtime:/etc/localtime:ro \
  -v /path/to/appdata/qbitrr:/config \
  -v /path/to/completed/downloads/folder:/completed_downloads:rw \
  --restart unless-stopped \
  feramance/qbitrr:latest
```

#### Docker Compose

```yaml
version: "3"
services:
  qbitrr:
    image: feramance/qbitrr:latest
    user: 1000:1000 # Required to ensure the container is run as the user who has perms to see the 2 mount points and the ability to write to the CompletedDownloadFolder mount
    tty: true # Ensure the output of docker-compose logs qBitrr are properly colored.
    restart: unless-stopped
    # networks: This container MUST share a network with your Sonarr/Radarr instances
    environment:
      - TZ=Europe/London
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /path/to/appdata/qbitrr:/config  # Config folder for qBitrr
      - /path/to/completed/downloads/folder:/completed_downloads:rw # The script will ALWAYS require write permission in this folder if mounted, this folder is used to monitor completed downloads and if not present will cause the script to ignore downloaded file monitoring.
      # Now just to make sure it is clean, when using this script in a docker you will need to ensure you config.toml values reflect the mounted folders.
      # The same would apply to Settings.CompletedDownloadFolder
      # e.g CompletedDownloadFolder = /completed_downloads/folder/in/container

    logging: # this script will generate a LOT of logs - so it is up to you to decide how much of it you want to store
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: 3
    depends_on: # Not needed but this ensures qBitrr only starts if the dependencies are up and running
      - qbittorrent
      - radarr-1080p
      - radarr-4k
      - sonarr-1080p
      - sonarr-anime
      - overseerr
      - ombi
```

##### Important mentions for docker

- The script will always expect a completed config.toml file
- When you first start the container a "config.rename_me.toml" will be added to `/path/to/appdata/qbitrr`
  - Make sure to rename it to 'config.toml' then edit it to your desired values

## Feature Suggestions

Please do not hesitate to open an issue for feature requests or any suggestions you may have. I plan on periodically adding any features I might feel I want to add but welcome to other suggestions I might not have thought of yet.

## Reporting an Issue

When reporting an issue, please ensure that log files are enabled while running qBitrr and attach them to the issue. Thank you.
