"""

This is the core file for downloading music and data from Spotify, SoundCloud, and YT Music.
It uses yt_dlp for downloading. It natively supports SoundCloud and YouTube Music;
if a Spotify link is provided, it redirects the download to YT Music after retrieving the metadata via spotify_scraper.
It also uses FFmpeg for audio conversion and Mutagen for managing ID3 tags.

"""

from yt_dlp import YoutubeDL
import os, requests, logging, subprocess
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from spotify_scraper import SpotifyClient
from PIL import Image
from io import BytesIO
import spotify_scraper
if hasattr(spotify_scraper, 'client'):
    spotify_scraper.client.logging.basicConfig(level=logging.CRITICAL)
    logging.getLogger("spotify_scraper.client").setLevel(logging.CRITICAL)

# ==========================================
#            Advanced exceptions
# ==========================================

class GPError(Exception):
    #Basic exception

    def __init__(self, msg:str, payload: dict = None):
        super().__init__(msg)
        self.message = msg
        self.payload = payload or {}

class UnsupportedURLError(GPError): 
    #Unsupported url
    pass
class MetadataError(GPError):
    # Spotify scraper tags error 
    pass
class ProcessError(GPError):
    # FFmpeg convertation or downloading error
    pass
class LimitExceededError(GPError):
    # Limits error
    pass

# ==========================================
#           Dynamic settings
# ==========================================

config = {
    "is_maintenance": False,
    "max_duration_seconds": 900,
    "banned_users": [],
    "max_size_MiB": 100
}

# ==========================================
#             yt_dlp options
# ==========================================
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

# ==========================================
#    Media Manager (conversion, tagging)
# ==========================================
class TrackMediaManager:
    @staticmethod
    def convert(track_data: dict, folder_dist: str, out_format: str = 'MP3') -> str:
        os.makedirs(folder_dist, exist_ok=True)
        old_path = track_data['path']
        filename = os.path.basename(os.path.splitext(old_path)[0]) + f'.{out_format.lower()}'
        new_path = os.path.join(folder_dist, filename)
        
        ffmpeg_bin = os.path.join('bin', 'ffmpeg.exe')
        cmd = [ffmpeg_bin, '-y', '-i', old_path, '-vn']
        
        fmt = out_format.upper()
        if fmt == 'MP3':
            cmd += ['-ar', '44100', '-ac', '2', '-b:a', '192k']
        elif fmt == 'FLAC':
            cmd += ['-compression_level', '5']
        elif fmt == 'M4A':
            cmd += ['-c:a', 'aac', '-b:a', '192k']
            
        cmd.append(new_path)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        if os.path.exists(old_path) and old_path != new_path:
            os.remove(old_path)
            
        return new_path

    @staticmethod
    def apply_tags(file_path: str, track_data: dict):
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.mp3':
            try:
                tags = ID3(file_path)
            except Exception:
                tags = ID3()
            tags[TIT2] = TIT2(encoding=3, text=track_data['title'])
            tags[TPE1] = TPE1(encoding=3, text=track_data['artist'])
            tags[TALB] = TALB(encoding=3, text=track_data['album'])
            
            if track_data.get('cover_url'):
                try:
                    resp = requests.get(track_data['cover_url'], timeout=5).content
                    img = Image.open(BytesIO(resp))
                    img_converted = img.convert('RGB')
                    
                    output_buffer = BytesIO()
                    img_converted.save(output_buffer, format='JPEG')
                    jpeg_data = output_buffer.getvalue()
                    
                    tags[APIC] = APIC(
                        encoding=3, 
                        mime='image/jpeg', 
                        type=3, 
                        desc='Cover', 
                        data=jpeg_data
                    )
                except Exception:
                    pass
            tags.save(file_path)
            
        elif ext in ['.flac', '.m4a']:
            try:
                import mutagen
                audio = mutagen.File(file_path)
                if audio is not None:
                    audio['title'] = track_data['title']
                    audio['artist'] = track_data['artist']
                    audio['album'] = track_data['album']
                    audio.save()
            except Exception:
                pass

# ==========================================
#           Main download process
# ==========================================
class  GPDownloader:
    def __init__(self, ydl_options:dict):
        self.ydl_opts = ydl_options
        self.spotify = SpotifyClient()
    
    # Download music from YT Music or SoundCloud
    def downloadf_ytsc(self, url:str) -> dict:
        with YoutubeDL(self.ydl_opts) as ydl:
            try:
                data = ydl.extract_info(url, download=True)
                
                video_data = data['entries'][0] if 'entries' in data else data
                if video_data.get('requested_downloads'):
                    file_path = video_data['requested_downloads'][0]['filepath']
                else:
                    file_path = ydl.prepare_filename(video_data)
                thumbnails = video_data.get('thumbnails', [])
                cover_url = thumbnails[-1]['url'] if thumbnails else None

                track_metadata = {

                    'path': file_path,
                    'title': video_data.get('title', 'Unknown Title'),
                    'artist': video_data.get('creator') or video_data.get('uploader', "Unknown Artist"),
                    'album': video_data.get('album', 'Single'),
                    'cover_url': cover_url
                }

                return track_metadata
            except Exception as e:
                raise ProcessError(f"Extractor failed, probably the link is broken")

    # Redirect Spotify downloads to YouTube
    def downloadf_sfy(self, url:str):

        try:
            track = self.spotify.get_track_info(url)
            track_name = track.get('name')
            track_artist = track['artists'][0]['name'] if track.get('artists') else 'Unknown Artist'

            if not track_name:
                raise MetadataError(f"Failed to get the track name from metadata: {url}")
                
            print(f"[Spotify redirect] Found: {track_artist} — {track_name} \n")

            search_query = f"ytsearch: {track_artist} {track_name}"
            return self.downloadf_ytsc(search_query)

        except Exception as e:
            raise MetadataError(f"Spotify extractor failed: {e}")

    # Automatically selects the download method and manages the main process
    def process(self, mediatype:str, urls:list, folder_dist:str, dformat:str = 'MP3', user_id: int = None):
        
        if config["is_maintenance"]:
            raise LimitExceededError("Unavailable due to maintenance.")
        if user_id in config['banned_users']:
            raise LimitExceededError(f"Access denied for user {user_id}.")
        
        if mediatype == 'tracks':

            print(f'[INFO] Starting for download track(s) \nTarget folder: {folder_dist}')

            for url in urls:
                if "youtube.com" in url or "music.youtube.com" in url or "soundcloud.com" in url:
                    track_data = self.downloadf_ytsc(url)
                elif "spotify.com" in url:
                    track_data = self.downloadf_sfy(url)
                else:
                    raise UnsupportedURLError(f"URL not supported: {url}")

                if not track_data:
                    raise ProcessError("Failed to retrieve track data.")

                file = TrackMediaManager.convert(track_data, folder_dist, dformat)
                TrackMediaManager.apply_tags(file, track_data)

                print(f"[Success] Saved to dist: {file}\n")