qbittorrent_ip = "127.0.0.1"
qbittorrent_port = "8080"
leave_free_space = "100G"
torrents_directory = r"C:\Torrents"

import re
import shutil

import requests

UNITS = {
    "k": 1e3,
    "m": 1e6,
    "g": 1e9,
    "t": 1e12,
}


def parse_size(size):
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)([kmgt]?)$", size, re.IGNORECASE)
    if not m:
        raise ValueError(f"Unsupported value for leave_free_space")
    val = float(m.group(1))
    unit = m.group(2)
    if unit:
        val *= UNITS[unit.lower()]
    return val


running_states = [
    "downloading",
    "stalledDL",
    "forcedDL",
    "allocating",
    "checkingResumeData",
    "moving",
]
paused_states = ["pausedDL"]
base_url = f"http://qbittorrent.shaunagius.com/api/v2"

disk_stats = shutil.disk_usage(torrents_directory)
free_space = disk_stats.free
free_space -= parse_size(leave_free_space)

request = requests.Session()
request.headers.update({"Accept": "application/json"})

torrents = request.get(f"{base_url}/torrents/info").json()
sorted_torrents = sorted(torrents, key=lambda t: t["priority"])

for torrent in sorted_torrents:
    if torrent["state"] in running_states:
        free_space -= torrent["amount_left"]
        print(free_space, torrent["amount_left"])

# resume_hashes = []
# for torrent in sorted_torrents:
#   if torrent['state'] in paused_states and free_space > torrent['amount_left']:
#     resume_hashes.append(torrent['hash'])
#     print(f'Resuming {torrent["name"]}')
#     free_space -= torrent['amount_left']

# if len(resume_hashes) > 0:
#   requests.post(f'{base_url}/torrents/resume', data = {'hashes': "|".join(resume_hashes)})
