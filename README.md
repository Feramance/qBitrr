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
  
  __This section requires the Arr databases to be locally available.__
  - Monitor Arr's databases to trigger missing episode searches.
  - Customizable year range to search for (at a later point will add more option here, for example search whole series/season instead of individual episodes, search by name, category etc).
  

### Important mentions.

Some things to know before using it.

-
    1. You need to copy the `config.example.ini` and rename it to `~/.config/qBitManager/config.ini` (~ is your home directory, i.e `C:\Users\{User}`)
-
    2. I have [Sonarr](https://github.com/Sonarr/Sonarr) and [Radarr](https://github.com/Radarr/Radarr) both setup to add tags to all downloads.
-
    3. I have qBit setup to have to create sub-folder for downloads and for the download folder to
       use subcategories.

    ![image](https://user-images.githubusercontent.com/27962761/139117102-ec1d321a-1e64-4880-8ad1-ee2c9b805f92.png)
-
    4. Make sure to have [`ffprobe`](https://www.ffmpeg.org/download.html) added to your PATH.

#### Install the requirements run:

- `python -m pip install qBitrr` (I would recommend in a dedicated [venv](https://docs.python.org/3.3/library/venv.html) but that's out of scope.

#### Run the script

- Make sure to update the settings in `~/.config/qBitManager/config.ini`
- Activate your venv
- Run `qbitrr`

#### How to update the script
- Activate your venv
- Run `python -m pip install -U qBitrr`

#### Contributions

- I'm happy with any PRs and suggested changes to the logic I just put it together dirty for my own use case.

#### Example behaviour
![image](https://user-images.githubusercontent.com/27962761/145682638-6c3a4c20-2756-4b42-a6b9-c7b95ad99b36.png)


### Change Logs
 - Update 2021-11-30 
   - This update will require you to delete the existing databases in `~/.config/qBitManager` due to changes to the database format.
   - Several bug fixes and new functionality.
 - Update 2021-12-11
   - Fix an edge case where the script would tell the Arr instance that the torrent couldn't be found too early resulting in its removal.
   - Make a release to PyPi
   - Add the script to your PATH via `pip install` allowing you to start it by just running `qbitrr`
   - Update logging and several typo fixes
   - Make the script listen for `~/.config/qBitManager/config.ini` and prioritize it if it exists - in a future release it will stop listening for `config.ini` in the current working dir.
 