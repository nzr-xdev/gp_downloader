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
import spotify_scraper
if hasattr(spotify_scraper, 'client'):
    spotify_scraper.client.logging.basicConfig(level=logging.CRITICAL)
    logging.getLogger("spotify_scraper.client").setLevel(logging.CRITICAL)

# ==========================================
#            Advanced exceptions
# ==========================================

class GPError(Exception):
    # Basic exception

    def __init__(self, msg:str, payload: dict = None):
        super().__init__(msg)
        self.message = msg
        self.payload = payload or {}

class UnsupportedURLError(GPError): 
    # Unsupported URL
    pass
class MetadataError(GPError):
    # metadata broken
    pass
class ErrorRetrievinginfo(GPError):
    # error retrieving information
    pass

class ProcessError(GPError):
    # FFmpeg conversion or downloading error
    pass
class LimitExceededError(GPError):
    # Limits error
    pass

class NoLinksInText(GPError):
    # No links found after processing user text
    pass

# ==========================================
#       Some preparations for Win/Linux
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
if sys.platform.startswith('win'):
    ffmpeg_name = 'ffmpeg.exe'
else:
    ffmpeg_name = 'ffmpeg'
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
#    Media Manager (conversion, tagging)
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
    def __init__(self):
        self.ydl_opts = ydl_opts
        self.spotify = SpotifyClient()
    
    # Download TRACK/PLAYLIST from YT Music or SoundCloud
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

    def playlist_ytsc(self, url:str) -> list[dict]:
        with YoutubeDL(self.ydl_opts) as ydl:
            try:
                data = ydl.extract_info(url, download=True)
                tracks = []
                for entry in data.get('entries', []):
                    if entry.get('requested_downloads'):
                        file_path = entry['requested_downloads'][0]['filepath']
                    else:
                        file_path = ydl.prepare_filename(entry)
                    thumbnails = entry.get('thumbnails', [])
                    cover_url = thumbnails[-1]['url'] if thumbnails else None

                    track_metadata = {
                        'path': file_path,
                        'title': entry.get('title', 'Unknown Title'),
                        'artist': entry.get('creator') or entry.get('uploader', "Unknown Artist"),
                        'album': data.get('title', 'Playlist'),
                        'cover_url': cover_url
                    }
                    tracks.append(track_metadata)
                return tracks
            except Exception as e:
                raise ProcessError(f"Extractor failed, probably the link is broken")

    # Redirect Spotify TRACK/Playlist(Album) download(s) to YouTube
    def track_spfy(self, url:str):

        try:
            track = self.spotify.get_track_info(url)
            track_name = track.get('name')
            track_artist = track['artists'][0]['name'] if track.get('artists') else 'Unknown Artist'

            if not track_name:
                raise MetadataError(f"Failed to get the track name from metadata: {url}")

            search_query = f"ytsearch: {track_artist} {track_name}"
            return self.track_ytsc(search_query)

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

        for track in tracks:
            track_name = track.get('name', 'Unknown Track')

            if mediatype == 'album':
                artist_name = global_artist
            else:
                track_artists = track.get('artists', [])
                artist_name = track_artists[0].get('name', 'Unknown Artist') if track_artists else 'Unknown Artist'

            search_query = f"ytsearch: {artist_name} {track_name}"

            try:
                track_metadata = self.track_ytsc(search_query)

                if track_metadata and 'path' in track_metadata:

                    track_metadata['title'] = track_name
                    track_metadata['artist'] = artist_name
                    track_metadata['album'] = data.get('name', 'Unknown Album')

                    completed.append(track_metadata)
            except Exception as e:
                logging.warning(f"Failed to process track '{artist_name} - {track_name}': {e}")
                continue

        return completed

    # Automatically selects the download method and manages the main process
    def process(self, url:str, platform:str, mediatype:str,  dformat:str = 'MP3'):
        
        if platform == 'Youtube' or platform == 'Soundcloud':

            if mediatype == 'track':
                track_data = [self.track_ytsc(url)]
            elif mediatype == 'playlist':
                track_data = self.playlist_ytsc(url)

            if not track_data:
                raise ProcessError("Failed to retrieve track data.")
            
            files = []
            for track in track_data:
                file = TrackMediaManager.convert(track, OUTPUT_DIR, dformat)
                files.append(file)
                TrackMediaManager.apply_tags(file, track)
            return files
        
        elif platform == 'Spotify':
            if mediatype == 'track':
                track_data = [self.track_spfy(url)]
            elif mediatype in ['album', 'playlist']:
                track_data = self.collection_spfy(url, mediatype)

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
        self.ydl_opts = {

            'extract_flat': True,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'playlist_items': '1-100',
            'external_downloader_args': {'youtube': ['--js-runtimes', 'deno:bin/deno.exe']}

        }
        self.spotify = SpotifyClient()

    @staticmethod
    def get_links(raw_text:str) -> list[str]:
        
        url_patern = r'https?://[^\s]+'
        return re.findall(url_patern, raw_text)

    def get_info_perlink(self, url:str) -> dict:
            try:
                if "youtube.com" in url or "music.youtube.com" in url or "youtu.be" in url or "soundcloud.com" in url:
                    platform = 'Soundcloud' if 'soundcloud.com' in url else 'Youtube'
                    info = YoutubeDL(ydl_opts).extract_info(url, download=False, process=False)
                    
                    if 'sets' in url or 'playlist' in url:
                        mediatype = 'playlist'
                    else:
                        mediatype = 'track'; return (platform, mediatype, 1)

                    if info.get('_type') == 'playlist' or 'entries' in info:
                        count = info.get('playlist_count') or len(info.get('entries', []))

                    return (platform, mediatype, count)

                elif "spotify.com" in url:
                    platform = 'Spotify'
                    if 'album' in url: 
                        mediatype = 'album'
                        album_info = self.spotify.get_album_info(url)
                        count = int(album_info.get('total_tracks', 0))
                        return (platform, mediatype, count)
                    elif 'playlist' in url: 
                        mediatype = 'playlist'
                        playlist_info = self.spotify.get_playlist_info(url)
                        count = int(playlist_info.get('track_count', 0))
                        return (platform, mediatype, count)
                    elif 'track' in url: mediatype = 'track'; return (platform, mediatype, 1)
                    else: raise UnsupportedURLError(f"URL is uncorrect: {url}")
                else:
                    raise UnsupportedURLError(f"URL not supported: {url}")
                

            except Exception as e: raise ErrorRetrievinginfo(f'Failed to get data from server: {e}')
        
    def link_preparer(self, raw_text:str) -> dict:
        total_count = 0
        parsing_result = {}
        links = self.get_links(raw_text)
        if not links:
            raise NoLinksInText('No links found in the request')
        for url in links:
            platform, mediatype, count = self.get_info_perlink(url)
            total_count+=count
            parsing_result[str(url)] = (platform, mediatype)
        
        return (parsing_result, total_count)

if __name__ == '__main__':

    # Just for testing purposes
    raw_text='Check this out: https://soundcloud.com/anysong'
    config = {'max_songs': 30}
    proc = URLParser()
    proccess = GPDownloader()
    try:
        result, total_count = proc.link_preparer(raw_text)
        if total_count > config['max_songs']:
            print('Too much songs')
        else: 
            
            for url, (platform, mediatype) in result.items():
                output_files = proccess.process(url, platform, mediatype)
                for file in output_files:
                    print(f"Uploaded: {file}")
                    #other logic for uploading to cloud or something
    except Exception as e:
        print(f"Error: {e}")