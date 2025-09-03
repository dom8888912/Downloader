import os
from pathlib import Path
import argparse

import yaml
from dotenv import load_dotenv


def load_config(argv=None):
    load_dotenv()

    parser = argparse.ArgumentParser(description="Video Downloader")
    parser.add_argument("--urls", nargs="*", help="Seiten oder direkte Videolinks")
    parser.add_argument("--urls-file", help="Datei mit Links")
    parser.add_argument("--out", default="downloads", help="Ausgabeverzeichnis")
    args = parser.parse_args(argv)

    urls = args.urls or []
    if args.urls_file:
        with open(args.urls_file) as f:
            urls.extend([line.strip() for line in f if line.strip()])

    cfg = {}
    yaml_path = Path("config.yaml")
    if yaml_path.exists():
        with yaml_path.open() as f:
            cfg = yaml.safe_load(f) or {}

    min_height = int(cfg.get("min_height", 1080))

    return type("Config", (), {
        "urls": urls,
        "out": args.out,
        "koofr_user": os.getenv("KOOFR_USER"),
        "koofr_password": os.getenv("KOOFR_PASSWORD"),
        "koofr_base": os.getenv("KOOFR_BASE", ""),
        "surfshark_server": os.getenv("SURFSHARK_SERVER"),
        "min_height": min_height,
    })()
