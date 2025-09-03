from env import ensure_venv

ensure_venv()

from config import load_config
from ui import UI
from downloader import process, connect_vpn, disconnect_vpn


def main():
    cfg = load_config()
    ui = UI()

    if cfg.surfshark_server:
        connect_vpn(cfg.surfshark_server, ui)
    try:
        for url in cfg.urls:
            ui.set_phase("DOWNLOAD")
            process(url, cfg, ui)
    finally:
        if cfg.surfshark_server:
            disconnect_vpn(ui)
        ui.set_phase("DONE")
        ui.close()


if __name__ == "__main__":
    main()
