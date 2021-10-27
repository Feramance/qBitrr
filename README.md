
A simple script to monitor [Qbit](https://github.com/qbittorrent/qBittorrent) and communicate with [Radarr](https://github.com/Radarr/Radarr) and [Sonarr](https://github.com/Sonarr/Sonarr)


Some things to know before using it.
- 1. You need to copy the `config.example.ini` and rename it to `config.ini`
- 2. I have Sonarr and Radarr both setup to add tags to all downloads.
- 3. I have qBit setup to have to create subfolder for downloads and for the download folder to use subcategories.

![image](https://user-images.githubusercontent.com/27962761/139117102-ec1d321a-1e64-4880-8ad1-ee2c9b805f92.png)

Im happy with any prs and suggested changes to the logic i just put it together dirty for my own use case.



#### Install the requirements run:

- `python -m pip install -r requirements.text` (I would reccomend in a dedicated [venv](https://docs.python.org/3.3/library/venv.html) but thats out of scope.

### Run the script
- Make sure to update the settings in `config.ini`
- Run `python main.py` 
