# Video Downloader

Dieses CLI-Tool lädt Videos mit [yt-dlp](https://github.com/yt-dlp/yt-dlp) herunter. Falls direkte Links erst nach Klick auf "Play" erscheinen, wird optional ein Headless-Browser über Playwright gestartet, um `.m3u8`/`.mpd`/`.mp4`-URLs aus dem Netzwerkverkehr zu sniffen. Nach Abschluss werden die Dateien automatisch per WebDAV zu [Koofr](https://koofr.eu) hochgeladen. Auf Wunsch kann vor dem Download eine Surfshark-VPN-Verbindung aufgebaut und danach wieder getrennt werden.

## Setup

1. Python 3.11+ installieren
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
