A simple script to monitor [Qbit](https://github.com/qbittorrent/qBittorrent) and communicate
with [Radarr](https://github.com/Radarr/Radarr) and [Sonarr](https://github.com/Sonarr/Sonarr)

### Features
  - Monitor qBit for Stalled/bad entries and delete them then blacklist them on Arrs (Option to also trigger a re-search action)
  - Monitor qBit for completed entries and tell the appropriate Arr instance to import it ( 'DownloadedMoviesScan' or 'DownloadedEpisodesScan' commands)
  - Skip files in qBit entries by extention, folder or regex
  - Monitor completed folder and cleans it up
  - Uses [ffprobe](https://github.com/FFmpeg/FFmpeg) to ensure downloaded entries are valid media.
  - Trigger perioridc Rss Syncs on the appropriate Arr instances
  - Trigger Queue update on appropriate Arr instances
  
  __This section requires the Arr databases to be locally available.__
  - Monitor Arr's databases to trigger missing episode searches
  - Customizable year range to search for (at a later point will add more option here, for example search whole series/season instead of individual episodes, search by name, category etc)
  

### Important mentions.

Some things to know before using it.

-
    1. You need to copy the `config.example.ini` and rename it to `config.ini`
-
    2. I have Sonarr and Radarr both setup to add tags to all downloads.
-
    3. I have qBit setup to have to create subfolder for downloads and for the download folder to
       use subcategories.

![image](https://user-images.githubusercontent.com/27962761/139117102-ec1d321a-1e64-4880-8ad1-ee2c9b805f92.png)

-
    4. Make sure to have [`ffprobe`](https://www.ffmpeg.org/download.html) added to your PATH.

#### Install the requirements run:

- `python -m pip install -r requirements.text` (I would reccomend in a
  dedicated [venv](https://docs.python.org/3.3/library/venv.html) but thats out of scope.

#### Run the script

- Make sure to update the settings in `config.ini`
- Run `python main.py`

#### Contributions

- Im happy with any PRs and suggested changes to the logic i just put it together dirty for my own
  use case.

#### Example behaviour
![image](https://user-images.githubusercontent.com/27962761/139675283-f1b09955-d9b3-448c-b64c-1de58c1cddcb.png)


### Change Logs
 - Update 2021/11/30 
   - This update will require you to delete the existing databases in `~/.config/qBitManager` due to changes to the database format.
   - Several bug fixes and new functionality.