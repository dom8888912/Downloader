# Video Downloader

Dieses CLI-Tool lädt Videos mit [yt-dlp](https://github.com/yt-dlp/yt-dlp) herunter. Falls direkte Links erst nach Klick auf "Play" erscheinen, startet ein Headless-Browser über Playwright das Video automatisch und schnüffelt `.m3u8`/`.mpd`/`.mp4`-URLs aus dem Netzwerkverkehr. Gelingt das nicht, fällt das Tool auf die ursprüngliche URL zurück. Nach Abschluss werden die Dateien automatisch per WebDAV zu [Koofr](https://koofr.eu) hochgeladen. Auf Wunsch kann vor dem Download eine Surfshark-VPN-Verbindung aufgebaut und danach wieder getrennt werden.

## Setup

1. Python 3.11+ installieren
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
3. `.env` Datei anlegen (siehe `.env.example`)
   - Pflicht: `KOOFR_USER`, `KOOFR_PASSWORD`
   - Optional: `KOOFR_BASE`, `SURFSHARK_SERVER`
4. Beispielaufruf:
   ```bash
   python main.py --urls https://beispiel.de/video-seite
   ```

Das Tool zeigt den Fortschritt (Prozent, Geschwindigkeit, ETA) live an und lädt fertige Dateien nach Koofr hoch.
