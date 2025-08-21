import os
from dotenv import load_dotenv
import argparse

def load_config():
    load_dotenv()

    parser = argparse.ArgumentParser(description="MyJDownloader CLI Tool")
    parser.add_argument("--urls", nargs="*", help="URLs to add")
    parser.add_argument("--urls-file", help="File containing URLs")
    parser.add_argument("--out", help="Output directory")
    parser.add_argument("--package-name", help="Package name")
    parser.add_argument("--autostart", action="store_true", help="Auto-start downloads")
    parser.add_argument("--jd-device", help="JDownloader device name")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    urls = args.urls or []
    if args.urls_file:
        with open(args.urls_file) as f:
            urls.extend([line.strip() for line in f if line.strip()])

    return type("Config", (), {
        "email": os.getenv("MYJD_EMAIL"),
        "password": os.getenv("MYJD_PASSWORD"),
        "device": args.jd_device or os.getenv("MYJD_DEVICE"),
        "urls": urls,
        "out": args.out,
        "package_name": args.package_name,
        "autostart": args.autostart,
        "dry_run": args.dry_run,
    })()
