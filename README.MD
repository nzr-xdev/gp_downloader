# 🎼 GP Downloader Core

![Python](https://img.shields.io/badge/python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Deno](https://img.shields.io/badge/deno-orange.svg?style=for-the-badge&logo=Deno&logoColor=white)
![FFmpeg](https://img.shields.io/badge/FFmpeg-blueviolet.svg?style=for-the-badge&logo=FFmpeg&logoColor=white)

A simple and lightweight backend module for downloading, converting, and tagging audio tracks from YouTube Music, SoundCloud, and Spotify. It is designed to work as a standalone core for CLI apps, Telegram bots, or web interfaces.

---

### 🚀 Core Features

* **Multi-Platform Support**: Works natively with YouTube Music and SoundCloud links.
* **Spotify Redirect**: Automatically extracts metadata from Spotify tracks and redirects the download to YouTube Music without needing heavy official API keys.
* **Auto-Conversion**: Automatically converts downloaded WebM/M4A audio files into high-quality MP3, FLAC, or M4A.
* **Automatic Tagging**: Automatically injects ID3 tags (title, artist, album) and converts cover art (WebP -> JPEG) so it displays correctly in any media player.
* **Error Handling**: Uses custom exceptions to catch bad links or system errors smoothly without crashing the app.

### 🔩 Tech Stack & Dependencies

* **Python 3.10+**
* **yt_dlp** — For extracting and downloading media streams.
* **Mutagen & Pillow** — For managing audio metadata and optimizing images.
* **FFmpeg** — Local binary used for fast audio decoding and conversion.
* **Deno** — JavaScript runtime required by yt_dlp extractors to bypass restrictions.

---

### 🔩 Installation & Usage

1. **Clone the repository:**
    ```bash
    git clone https://github.com/nzr-xdev/gp_downloader.git
    cd gp_downloader
2. **Install dependencies (inside your virtual environment):**
    ```bash
    pip install -r requirements.txt
3. **Add external binaries:**
To enable conversion and downloads, you need `ffmpeg` and `deno`
   Go to the **Releases** tab on the right side of this GitHub repository, download `bin.zip`, and extract the `bin/` folder directly into the root directory of this project.

*These files are already included in the binaries archive (`bin.zip`)*

4. **Try it out:**
    ```bash
    python ssyd.py

---

### 📂 File Structure

* `ssyd.py` — The core engine containing downloading logic, media managers, and configurations.
* `bin/deno` —  runtime required by yt_dlp extractors to bypass restrictions.
* `bin/ffmpeg` - *REQUIRED* Local binary used for fast audio decoding and conversion.
* `output/` - Output directory for files generated after processing.
* `.cache`- Cache directory for temporary files.
