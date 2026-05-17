"""

This is the core file for downloading music and data from Spotify, SoundCloud, and YT Music.
It uses yt_dlp for downloading. It natively supports SoundCloud and YouTube Music;
if a Spotify link is provided, it redirects the download to YT Music after retrieving the metadata via spotify_scraper.
It also uses FFmpeg for audio conversion and Mutagen for managing ID3 tags.

"""

#Library
from yt_dlp import YoutubeDL
import os
from spotify_scraper import SpotifyClient

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

spotify_client = SpotifyClient()

# Download music from YT Music or SoundCloud
def downloadf_ytsc(urls:list):

    with YoutubeDL(ydl_opts) as ydl:

        try:
            ydl.download(urls)

        except:
            raise KeyError('An error occurred while trying to download music from YouTube or SoundCloud.')

# Redirect Spotify downloads to YouTube
def downloadf_sfy(urls:list):

    try:
        for url in urls:
            track = spotify_client.get_track_info(url)
            track_name = track.get('name')
            track_artist = track['artists'][0]['name'] if track.get('artists') else 'Unknown Artist'

            if not track_name:
                raise Exception(f"Failed to get the track name from metadata: {url}")
            
            print(f"[Spotify redirect] Found: {track_artist} — {track_name} \n")

            search_query = f"ytsearch: {track_artist} {track_name}"
            downloadf_ytsc([search_query])

    except Exception as e:
        print(f"[ERR] Spotify redirection failed: {e}")

    

test_urls = ['https://soundcloud.com/user-328360239/dozhd-po-shchekam-remix?si=7b6891ff47ae4ed2a56489a81a4143ec&utm_source=clipboard&utm_medium=text&utm_campaign=social_sharing', #Soundcloud/Youtube URLs (Spotify untested)
            'https://music.youtube.com/watch?v=XDzzKkLPRP4&si=HPc9zodp2_FMA-cZ',  
            'https://music.youtube.com/watch?v=4f6RBIvP7D4&si=JydaJA-7cny7hzqX'
        ]

test_spotify_urls = ['https://open.spotify.com/track/6qZra71fzsZOgmCPwzBKLt?si=JLya-piGToG0FdisQCxUwg',
                    'https://open.spotify.com/track/2bqS0QtnXGjOYs3z6VtSyW?si=3TsuoVNsQXCycauyS3X5WQ'
                    
                    ]
try:
    downloadf_ytsc(test_urls)
    downloadf_sfy(test_spotify_urls)
except Exception as e:
    print(f'[Error] details: {e}')