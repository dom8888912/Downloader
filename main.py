from config import load_config
from jd_client import JDClient
from ui import UI

def main():
    cfg = load_config()
    ui = UI()
    jd = JDClient(cfg, ui)

    ui.set_phase("JD_LINKGRABBER")
    jd.add_links(cfg.urls)

    if not cfg.dry_run:
        ui.set_phase("JD_DOWNLOAD")
        jd.start_downloads()
        jd.monitor_progress()

    ui.set_phase("DONE")

if __name__ == "__main__":
    main()
