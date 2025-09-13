
import threading, urllib.request
from dataclasses import dataclass
from typing import Optional, Callable

@dataclass
class DownloadItem:
    url: str
    dest: str
    progress: int = 0
    size_bytes: Optional[int] = None
    status: str = "queued"   # queued|downloading|done|error|canceled
    error: Optional[str] = None

ProgressCb = Callable[[DownloadItem], None]

class Downloader:
    def __init__(self, on_update: ProgressCb):
        self.on_update = on_update

    def start(self, item: DownloadItem):
        if item.status == "downloading":
            return
        item.status = "downloading"
        self.on_update(item)
        threading.Thread(target=self._worker, args=(item,), daemon=True).start()

    def _worker(self, item: DownloadItem):
        try:
            with urllib.request.urlopen(item.url) as resp:
                total = getattr(resp, 'length', None)
                item.size_bytes = total
                with open(item.dest, 'wb') as f:
                    read = 0
                    while True:
                        chunk = resp.read(64*1024)
                        if not chunk: break
                        f.write(chunk)
                        read += len(chunk)
                        item.progress = int(read*100/max(1, total)) if total else (item.progress+5) % 100
                        self.on_update(item)
            item.progress = 100; item.status = 'done'; self.on_update(item)
        except Exception as e:
            item.status = 'error'; item.error = str(e); self.on_update(item)
