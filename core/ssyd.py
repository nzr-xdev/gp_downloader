"""
This is the core file for downloading music and data from Spotify, SoundCloud, and YT Music.
It uses yt_dlp for downloading. It natively supports SoundCloud and YouTube Music;
if a Spotify link is provided, it redirects the download to YT Music after retrieving the metadata via spotify_scraper.
It also uses FFmpeg for audio conversion and Mutagen for managing ID3 tags.
"""

from yt_dlp import YoutubeDL
from pathlib import Path
import os, requests, logging, subprocess, re, sys
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from spotify_scraper import SpotifyClient
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

logging.getLogger("spotify_scraper").setLevel(logging.CRITICAL)

# ==========================================
#            Advanced exceptions
# ==========================================

class GPError(Exception):
    def __init__(self, msg:str, payload: dict = None):
        super().__init__(msg)
        self.message = msg
        self.payload = payload or {}

class UnsupportedURLError(GPError): pass
class MetadataError(GPError): pass
class ErrorRetrievinginfo(GPError): pass
class ProcessError(GPError): pass
class LimitExceededError(GPError): pass
class NoLinksInText(GPError): pass

# ==========================================
#        Some preparations for Win/Linux
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
ffmpeg_name = 'ffmpeg.exe' if sys.platform.startswith('win') else 'ffmpeg'
FFMPEG_BIN = str(BASE_DIR / 'bin' / ffmpeg_name)

CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
deno_name = 'deno.exe' if sys.platform.startswith('win') else 'deno'
DENO_PATH = str(BASE_DIR / 'deno' / 'bin' / deno_name)

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

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
        logging.debug(f"[DWNLD] {os.path.basename(path)} \n     {size_mib:.2f}MiB in {elapsed_time:.2f}s at {avg_speed:.2f}MiB/s \n")

ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': str(CACHE_DIR / '%(title)s.%(ext)s'),
    'quiet': True,
    'no_warnings': True,
    'noprogress': True,
    'progress_hooks': [download_result],
    'external_downloader_args': {
        'youtube': ['--js-runtimes', f'deno:{DENO_PATH}']
    }
}

# ==========================================
#      Media Manager (conversion, tagging)
# ==========================================
class TrackMediaManager:
    @staticmethod
    def convert(track_data: dict, folder_dist: str, out_format: str = 'MP3') -> str:
        os.makedirs(folder_dist, exist_ok=True)
        old_path = track_data['path']
        filename = os.path.basename(os.path.splitext(old_path)[0]) + f'.{out_format.lower()}'
        new_path = os.path.join(folder_dist, filename)
        cmd = [FFMPEG_BIN, '-y', '-i', old_path, '-vn']
        
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
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    resp = requests.get(track_data['cover_url'], headers=headers, timeout=5).content
                    img = Image.open(BytesIO(resp)).convert('RGB')
                    img.thumbnail((500, 500))
                    
                    output_buffer = BytesIO()
                    img.save(output_buffer, format='JPEG', quality=85)
                    
                    tags[APIC] = APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=output_buffer.getvalue())
                    print(f"🎨 [TAGGER] Cover embedded into {os.path.basename(file_path)}")
                except Exception as cover_err:
                    print(f"⚠️ [TAGGER ERROR] Cover failed: {cover_err}")
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
            except Exception as e:
                print(f"⚠️ [TAGGER ERROR] FLAC/M4A tagging failed: {e}")

# ==========================================
#            Main download process
# ==========================================
class GPDownloader:
    def __init__(self):
        self.ydl_opts = ydl_opts
        self.spotify = SpotifyClient()
    
    def track_ytsc(self, url:str) -> dict:
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

                return {
                    'path': file_path,
                    'title': video_data.get('title', 'Unknown Title'),
                    'artist': video_data.get('creator') or video_data.get('uploader', "Unknown Artist"),
                    'album': video_data.get('album', 'Single'),
                    'cover_url': cover_url
                }
            except Exception:
                raise ProcessError(f"Extractor failed, probably the link is broken")

    def playlist_ytsc(self, url:str) -> list[dict]:
        with YoutubeDL(self.ydl_opts) as ydl:
            try:
                data = ydl.extract_info(url, download=True)
                tracks = []
                for entry in data.get('entries', []):
                    if not entry: continue
                    if entry.get('requested_downloads'):
                        file_path = entry['requested_downloads'][0]['filepath']
                    else:
                        file_path = ydl.prepare_filename(entry)
                        
                    thumbnails = entry.get('thumbnails', [])
                    cover_url = thumbnails[-1]['url'] if thumbnails else None

                    tracks.append({
                        'path': file_path,
                        'title': entry.get('title', 'Unknown Title'),
                        'artist': entry.get('creator') or entry.get('uploader', "Unknown Artist"),
                        'album': data.get('title', 'Playlist'),
                        'cover_url': cover_url
                    })
                return tracks
            except Exception:
                raise ProcessError(f"Extractor failed, probably the link is broken")

    def track_spfy(self, url:str):
        try:
            track = self.spotify.get_track_info(url)
            track_name = track.get('name')
            track_artist = track['artists'][0]['name'] if track.get('artists') else 'Unknown Artist'
            if not track_name:
                raise MetadataError(f"Failed to get track name from Spotify: {url}")
            return self.track_ytsc(f"ytsearch: {track_artist} {track_name}")
        except Exception as e:
            raise MetadataError(f"Spotify extractor failed: {e}")

    def collection_spfy(self, url:str, mediatype:str):
        if mediatype == 'album':
            data = self.spotify.get_album_info(url)
            album_artists = data.get('artists', [])
            global_artist = album_artists[0].get('name', 'Unknown Artist') if album_artists else 'Unknown Artist'
        elif mediatype == 'playlist':
            data = self.spotify.get_playlist_info(url)
            global_artist = 'Various Artists'
        else:
            raise UnsupportedURLError(f"Unsupported Spotify media type: {mediatype}")
        
        tracks = data.get('tracks', [])
        completed = []

        # Worker for parallel processing of Spotify tracks
        def process_spotify_track(track):
            track_name = track.get('name', 'Unknown Track')
            artist_name = global_artist if mediatype == 'album' else (track.get('artists', [{}])[0].get('name', 'Unknown Artist'))
            try:
                metadata = self.track_ytsc(f"ytsearch: {artist_name} {track_name}")
                if metadata and 'path' in metadata:
                    metadata['title'] = track_name
                    metadata['artist'] = artist_name
                    metadata['album'] = data.get('name', 'Unknown Album')
                    return metadata
            except Exception as e:
                logging.warning(f"Failed to process Spotify track '{artist_name} - {track_name}': {e}")
            return None

        # SPEED UP: Processing Spotify collection in 4 concurrent threads
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(process_spotify_track, tracks)
            for res in results:
                if res: completed.append(res)

        return completed

    def process(self, url:str, platform:str, mediatype:str, dformat:str = 'MP3'):
        if platform in ['Youtube', 'Soundcloud']:
            if mediatype == 'track':
                track_data = [self.track_ytsc(url)]
            elif mediatype == 'playlist':
                track_data = self.playlist_ytsc(url)
        elif platform == 'Spotify':
            if mediatype == 'track':
                track_data = [self.track_spfy(url)]
            elif mediatype in ['album', 'playlist']:
                track_data = self.collection_spfy(url, mediatype)
        else:
            raise UnsupportedURLError(f"Unknown platform: {platform}")

        if not track_data:
            raise ProcessError("Failed to retrieve track data.")
        
        files = []
        for track in track_data:
            file = TrackMediaManager.convert(track, OUTPUT_DIR, dformat)
            files.append(file)
            TrackMediaManager.apply_tags(file, track)
        return files

# ==========================================
#               URL Parser
# ==========================================
class URLParser:
    def __init__(self):
        self.spotify = SpotifyClient()

    @staticmethod
    def get_links(raw_text:str) -> list[str]:
        return re.findall(r'https?://[^\s]+', raw_text)

    def get_info_perlink(self, url:str) -> dict:
        try:
            if any(domain in url for domain in ["youtube.com", "music.youtube.com", "youtu.be", "soundcloud.com"]):
                platform = 'Soundcloud' if 'soundcloud.com' in url else 'Youtube'
                mediatype = 'playlist' if ('sets' in url or 'playlist' in url) else 'track'
                return (platform, mediatype, 1)

            elif "spotify.com" in url or "spotify.com" in url:
                platform = 'Spotify'
                if 'album' in url: 
                    return (platform, 'album', int(self.spotify.get_album_info(url).get('total_tracks', 1)))
                elif 'playlist' in url: 
                    return (platform, 'playlist', int(self.spotify.get_playlist_info(url).get('track_count', 1)))
                elif 'track' in url: 
                    return (platform, 'track', 1)
                
            raise UnsupportedURLError(f"URL not supported: {url}")
        except Exception as e: 
            raise ErrorRetrievinginfo(f'Failed to parse link data: {e}')
        
    def link_preparer(self, raw_text:str) -> dict:
        total_count = 0
        parsing_result = {}
        links = self.get_links(raw_text)
        if not links:
            raise NoLinksInText('No links found in the request')
        for url in links:
            platform, mediatype, count = self.get_info_perlink(url)
            total_count += count
            parsing_result[str(url)] = (platform, mediatype)
        return (parsing_result, total_count)