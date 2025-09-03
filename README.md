# Video Downloader

Dieses CLI-Tool lädt Videos mit [yt-dlp](https://github.com/yt-dlp/yt-dlp) herunter. Falls direkte Links erst nach Klick auf "Play" erscheinen, wird optional ein Headless-Browser über Playwright gestartet, um `.m3u8`/`.mpd`/`.mp4`-URLs aus dem Netzwerkverkehr zu sniffen. Nach Abschluss werden die Dateien automatisch per WebDAV zu [Koofr](https://koofr.eu) hochgeladen. Auf Wunsch kann vor dem Download eine Surfshark-VPN-Verbindung aufgebaut und danach wieder getrennt werden.

## Setup

### Schnellstart

```bash
python setup.py
```

Der Befehl legt eine virtuelle Umgebung in `.venv` an, installiert alle
Abhängigkeiten (inklusive der Bibliotheken für Cloudflare-Impersonation
und Playwrights Firefox) und erzeugt ein Startskript (`run_gui.bat` bzw.
`run_gui.sh`), über das
die GUI per Doppelklick gestartet werden kann.

### Manuell

1. Python 3.11+ installieren
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   playwright install firefox
   ```
3. Die für Cloudflare-Impersonation nötige Bibliothek `curl_cffi` ist
   bereits in `requirements.txt` enthalten; zusätzliche Schritte sind
   nicht erforderlich. Das Tool übergibt `--extractor-args "generic:impersonate"`
   automatisch.

### Konfiguration

In `config.yaml` lässt sich die Mindestauflösung in Pixel festlegen, ab
der ein Stream akzeptiert wird. Standardmäßig steht der Wert auf 1080:

```yaml
min_height: 1080
```

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
