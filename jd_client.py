import time

class JDClient:
    def __init__(self, cfg, ui):
        self.cfg = cfg
        self.ui = ui
        # hier würde Login zur MyJD API passieren

    def add_links(self, urls):
        for url in urls:
            self.ui.log(f"Added URL: {url}")
        # hier echte API-Calls

    def start_downloads(self):
        self.ui.log("Starting downloads...")
        # hier echte API-Calls

    def monitor_progress(self):
        for i in range(0, 101, 10):
            self.ui.update_progress("example_file.mp4", i, speed="2 MB/s", eta="1m")
            time.sleep(0.5)
        self.ui.log("All downloads finished.")
