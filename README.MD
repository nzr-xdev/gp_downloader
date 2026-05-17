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
To enable conversion and downloads, ensure you have the required executables. Download and place them inside the `bin/` folder of your project:

* [FFmpeg (ffmpeg.exe)](https://ffmpeg.org/download.html) — For audio conversion.
* [Deno (deno.exe)](https://docs.deno.com/runtime/getting_started/installation/) — For bypassing YouTube limits.

*These files are already included in the `bin` folder.*

4. **Run the CLI test:**
    ```bash
    python main_cli.py

---

### 📂 File Structure

* `ssyd.py` — The core engine containing downloading logic, media managers, and configurations.
* `main_cli.py` — A simple console interface used to test the downloader with a list of links.