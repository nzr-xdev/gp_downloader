"""

This is the core file for downloading music and data from Spotify, SoundCloud, and YT Music.
It uses yt_dlp for downloading. Currently, it only supports SoundCloud and YouTube Musiс,
while downloads from Spotify are redirected to YT Music.
It also uses FFmpeg for audio conversion and Mutagen for managing ID3 tags.
WW
"""

#Library
from yt_dlp import YoutubeDL
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

#YDL settings

def download_result(d):
    if d['status'] == 'finished':

        total_bytes = d.get('total_bytes', 0)
        size_mib = total_bytes / (1024*1024)

        elapsed_time = d.get('elapsed', 0)

        avg_speed = size_mib / elapsed_time if elapsed_time > 0 else 0

        path = d.get('filename', 'Unknown')

        print(f"[DWNLD] {os.path.basename(path)} \n     {size_mib:.2f}MiB in {elapsed_time:.2f}s at {avg_speed:.2f}MiB/s \n")

ydl_opts = {

        'format': 'bestaudio/best',
        'outtmpl': '.cache/%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'playlist_items': '1',
        'noplaylist': True,
        'progress_hooks': [download_result],

        'external_downloader_args': {'youtube': ['--js-runtimes', 'deno:bin/deno.exe']}
    }

# Spotify settings
auth_manager = SpotifyClientCredentials(client_id='Your_id', client_secret='Your_secret')
sp = spotipy.Spotify(auth_manager=auth_manager)


# Download music from YT Music or SoundCloud
def download_from_ytsc(urls:list):

    with YoutubeDL(ydl_opts) as ydl:

        try:
            ydl.download(urls)

        except:
            raise KeyError('An error occurred while trying to download music from YouTube or SoundCloud')

# Redirect Spotify downloads to YouTube
def download_from_sfy(url:str):

    track_info = sp.track(url)
    track_name = track_info['name']
    track_artist = track_info['artists'][0]['name']

    search_query = f"ytsearch: {track_artist} {track_name}"
    
    download_from_ytsc([search_query])


test_urls = ['', #Soundcloud/Youtube URLs (Spotify untested)
            '',  
        ]
try:
    download_from_ytsc(test_urls)
except Exception as e:
    print(f'[Error] details: {e}')