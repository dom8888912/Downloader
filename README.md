# Video Downloader

Dieses CLI-Tool lädt Videos mit [yt-dlp](https://github.com/yt-dlp/yt-dlp) herunter. Falls direkte Links erst nach Klick auf "Play" erscheinen, wird optional ein Headless-Browser über Playwright gestartet, um `.m3u8`/`.mpd`/`.mp4`-URLs aus dem Netzwerkverkehr zu sniffen. Nach Abschluss werden die Dateien automatisch per WebDAV zu [Koofr](https://koofr.eu) hochgeladen. Auf Wunsch kann vor dem Download eine Surfshark-VPN-Verbindung aufgebaut und danach wieder getrennt werden.

## Setup

### Schnellstart

```bash
python setup.py
```

Der Befehl legt eine virtuelle Umgebung in `.venv` an, installiert alle
Abhängigkeiten (inklusive `yt-dlp[cloudflare]` und Playwrights Firefox)
und erzeugt ein Startskript (`run_gui.bat` bzw. `run_gui.sh`), über das
die GUI per Doppelklick gestartet werden kann.

### Manuell

1. Python 3.11+ installieren
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   playwright install firefox
   ```
3. (Optional) Für Cloudflare-geschützte Hosts wie `supervideo.cc` die
   Impersonation-Abhängigkeit von yt-dlp installieren:
   ```bash
   pip install yt-dlp[cloudflare]
   ```
   Das Tool übergibt `--extractor-args "generic:impersonate"` automatisch.

Beim Download zeigt das Tool gefundene Stream-URLs an und sortiert sie nach Größe.
Sollte die erste URL von `yt-dlp` nicht unterstützt werden, versucht das Programm
automatisch die nächsten Kandidaten, bis ein Download gelingt.
Wenn ein Kandidat scheitert, wird die Seite mit Playwright erkundet, um darin
versteckte `.m3u8`/`.mpd`/`.mp4`-Streams zu finden. Gefundene direkte Streams
werden sofort an den Anfang der Kandidatenliste gestellt und beim nächsten
Schritt bevorzugt getestet.
Falls sämtliche Kandidaten fehlschlagen, endet der Download ohne Ergebnis.
Alle Meldungen von `yt-dlp` werden zusätzlich in `downloader.log`
gespeichert, um die Fehlersuche zu erleichtern.
