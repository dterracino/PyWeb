
import os, sys, wx
from typing import List, Optional
from services.downloader import Downloader, DownloadItem

class DownloadsPanel(wx.Panel):
    def __init__(self, parent, theme_getter):
        super().__init__(parent)
        self._get_theme = theme_getter
        self.items: List[DownloadItem] = []
        self.downloader = Downloader(on_update=lambda it: wx.CallAfter(self._refresh_item, it))

        header = wx.BoxSizer(wx.HORIZONTAL)
        self.url_box = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.btn_add = wx.Button(self, label="Add")
        self.btn_scan = wx.Button(self, label="Scan Page Images")
        header.Add(self.url_box, 1, wx.ALL|wx.EXPAND, 4)
        header.Add(self.btn_add, 0, wx.ALL, 4)
        header.Add(self.btn_scan, 0, wx.ALL, 4)

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN)
        for i,(t,w) in enumerate([("File",240),("Status",100),("Progress",90),("Size",90),("From",260)]):
            self.list.InsertColumn(i,t,width=w)

        ctrls = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, label="Start")
        self.btn_open = wx.Button(self, label="Open Folder")
        ctrls.Add(self.btn_start, 0, wx.ALL, 4)
        ctrls.Add(self.btn_open, 0, wx.ALL, 4)

        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(header, 0, wx.EXPAND)
        s.Add(self.list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 4)
        s.Add(ctrls, 0)
        self.SetSizer(s)

        self.url_box.Bind(wx.EVT_TEXT_ENTER, self._on_add)
        self.btn_add.Bind(wx.EVT_BUTTON, self._on_add)
        self.btn_start.Bind(wx.EVT_BUTTON, self._on_start)
        self.btn_open.Bind(wx.EVT_BUTTON, self._on_open)
        self.btn_scan.Bind(wx.EVT_BUTTON, lambda _e: wx.MessageBox("Hook to BrowserTab.start_hover_pick + image scan", "TODO"))

    def apply_theme(self):
        t = self._get_theme()
        for w in (self, self.list, self.url_box, self.btn_add, self.btn_scan, self.btn_start, self.btn_open):
            w.SetBackgroundColour(t.ctrl_bg if w is not self else t.bg)
            w.SetForegroundColour(t.ctrl_fg)

    def add_download(self, url: str, dest_dir: Optional[str]=None):
        if not url: return
        dest_dir = dest_dir or os.path.join(os.getcwd(), 'downloads'); os.makedirs(dest_dir, exist_ok=True)
        name = os.path.basename(url.split('?')[0]) or 'download.bin'
        item = DownloadItem(url=url, dest=os.path.join(dest_dir, name))
        self.items.append(item)
        idx = self.list.InsertItem(self.list.GetItemCount(), name)
        self.list.SetItem(idx,1,item.status); self.list.SetItem(idx,2,f"{item.progress}%"); self.list.SetItem(idx,3,'?'); self.list.SetItem(idx,4,item.url)

    def _on_add(self, _): self.add_download(self.url_box.GetValue().strip()); self.url_box.SetValue("")

    def _on_start(self, _):
        for it in self.items:
            if it.status in ('queued','error','canceled'):
                self.downloader.start(it)

    def _on_open(self, _):
        if not self.items: return
        folder = os.path.dirname(self.items[0].dest)
        if os.name=='nt': os.startfile(folder)
        elif sys.platform=='darwin': os.system(f"open '{folder}'")
        else: os.system(f"xdg-open '{folder}'")

    def _refresh_item(self, it: DownloadItem):
        for row in range(self.list.GetItemCount()):
            if self.list.GetItemText(row) == os.path.basename(it.dest):
                self.list.SetItem(row,1,it.status)
                self.list.SetItem(row,2,f"{it.progress}%")
                self.list.SetItem(row,3, f"{(it.size_bytes or 0)/1024:.0f} KB" if it.size_bytes else '?')
                break
