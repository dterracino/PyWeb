
import wx
from typing import Optional
from core.theme import Theme, LIGHT, DARK
from ui.browser_tab import BrowserTab
from ui.downloads_panel import DownloadsPanel
from ui.icons import Iconset

START_URL = "https://example.com"
ICON_SIZE = (20,20)

class BrowserFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="PyWeb MiniBrowser", size=wx.Size(1100,750))
        self._theme: Theme = DARK
        self.iconset = Iconset(self._theme.fg)

        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.left = wx.Panel(self.splitter)
        self.right = DownloadsPanel(self.splitter, theme_getter=lambda: self._theme)
        self.splitter.SplitVertically(self.left, self.right, sashPosition=self.GetSize().width - 320)
        self.splitter.Unsplit(self.right)

        chrome = wx.Panel(self.left)
        self.addr = wx.TextCtrl(chrome, style=wx.TE_PROCESS_ENTER)
        self.btn_theme = wx.Button(chrome, label='☾')

        top = wx.BoxSizer(wx.HORIZONTAL)
        for w in (self.addr, self.btn_theme):
            top.Add(w, 1 if w is self.addr else 0, wx.ALL | (wx.EXPAND if w is self.addr else 0), 4)

        chrome.SetSizer(top)  # attach the toolbar sizer to its parent panel

        self.nb = wx.Notebook(self.left)
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(chrome, 0, wx.EXPAND)   # add the *panel*, not the sizer
        s.Add(self.nb, 1, wx.EXPAND)
        self.left.SetSizer(s)

        self.CreateStatusBar(); self.SetStatusText("Ready")
        self.addr.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_theme.Bind(wx.EVT_BUTTON, self._toggle_theme)

        self.new_tab(START_URL)
        self.apply_theme()

    def apply_theme(self):
        t = self._theme
        for w in (self, self.left, self.splitter, self.addr, self.right):
            w.SetBackgroundColour(t.bg)
            w.SetForegroundColour(t.fg)
        self.right.apply_theme()
        self.Refresh()

    def _toggle_theme(self, _=None):
        self._theme = LIGHT if self._theme.name == 'dark' else DARK
        self.apply_theme()

    def _active(self) -> Optional[BrowserTab]:
        page = self.nb.GetCurrentPage()
        return page if isinstance(page, BrowserTab) else None

    def new_tab(self, url: str):
        tab = BrowserTab(self.nb, on_title_changed=lambda t,ttl: self.SetStatusText(ttl), on_new_window=self._open_in_new_tab)
        self.nb.AddPage(tab, "New Tab", select=True)
        tab.load(url)

    def _open_in_new_tab(self, url: str): self.new_tab(url)

    def _on_go(self, _):
        url = self.addr.GetValue().strip()
        if url and '://' not in url: url = 'https://' + url
        a = self._active();  a.load(url) if (a and url) else None
