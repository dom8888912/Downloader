import os
from dotenv import load_dotenv
import argparse


def load_config():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Video Downloader")
    parser.add_argument("--urls", nargs="*", help="Seiten oder direkte Videolinks")
    parser.add_argument("--urls-file", help="Datei mit Links")
    parser.add_argument("--out", default="downloads", help="Ausgabeverzeichnis")
    args = parser.parse_args()

    urls = args.urls or []
    if args.urls_file:
        with open(args.urls_file) as f:
            urls.extend([line.strip() for line in f if line.strip()])

    return type("Config", (), {
        "urls": urls,
        "out": args.out,
        "koofr_user": os.getenv("KOOFR_USER"),
        "koofr_password": os.getenv("KOOFR_PASSWORD"),
        "koofr_base": os.getenv("KOOFR_BASE", ""),
        "surfshark_server": os.getenv("SURFSHARK_SERVER"),
    })()
