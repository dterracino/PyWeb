import os
import tempfile
import urllib.request
import wx
from typing import Optional, Deque, Tuple, List
from collections import deque

from core.theme import Theme, LIGHT, DARK
from ui.browser_tab import BrowserTab
from ui.downloads_panel import DownloadsPanel
from ui.icons import Iconset
from services import dom_select

START_URL = "https://example.com"
ICON_SIZE = (20, 20)
TAB_ICON_SIZE = (16, 16)
HISTORY_MAX = 50


class BrowserFrame(wx.Frame):
    def __init__(self) -> None:
        super().__init__(None, title="PyWeb MiniBrowser", size=wx.Size(1100, 750))
        self._theme: Theme = DARK
        self.iconset = Iconset(self._theme.fg)
        self.history: Deque[Tuple[str, str]] = deque(maxlen=HISTORY_MAX)

        # Splitter: left (browser) | right (downloads sidebar)
        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.left = wx.Panel(self.splitter)
        self.right = DownloadsPanel(self.splitter, theme_getter=lambda: self._theme)
        self.splitter.SplitVertically(self.left, self.right, sashPosition=self.GetSize().width - 320)
        self.splitter.Unsplit(self.right)
        self.splitter.SetSashGravity(1.0)

        # Tabs + images
        self._tab_images = wx.ImageList(TAB_ICON_SIZE[0], TAB_ICON_SIZE[1])
        self.nb = wx.Notebook(self.left)
        self.nb.AssignImageList(self._tab_images)

        # Toolbar
        chrome = wx.Panel(self.left)

        def mkbtn(name: str, tip: str) -> wx.BitmapButton:
            bmp = self.iconset.load_svg(name, size=ICON_SIZE)
            bundle = wx.BitmapBundle.FromBitmap(bmp)
            btn = wx.BitmapButton(chrome, bitmap=bundle, style=wx.BU_AUTODRAW)
            btn.SetToolTip(tip)
            return btn

        self.btn_back = mkbtn("back.svg", "Back")
        self.btn_fwd = mkbtn("forward.svg", "Forward")
        self.btn_reload = mkbtn("reload.svg", "Reload")
        self.btn_stop = mkbtn("stop.svg", "Stop")
        self.addr = wx.TextCtrl(chrome, style=wx.TE_PROCESS_ENTER)
        self.btn_go = mkbtn("go.svg", "Go")
        self.btn_newtab = mkbtn("newtab.svg", "New Tab")
        self.btn_downloads = mkbtn("downloads.svg", "Toggle Downloads Sidebar")
        self.btn_history = mkbtn("history.svg", "History")
        self.btn_theme = wx.Button(chrome, label="☾")

        top = wx.BoxSizer(wx.HORIZONTAL)
        for w in (self.btn_back, self.btn_fwd, self.btn_reload, self.btn_stop, self.addr, self.btn_go,
                  self.btn_newtab, self.btn_downloads, self.btn_history, self.btn_theme):
            top.Add(w, 1 if w is self.addr else 0, wx.ALL | (wx.EXPAND if w is self.addr else 0), 4)
        chrome.SetSizer(top)

        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(chrome, 0, wx.EXPAND)
        left_sizer.Add(self.nb, 1, wx.EXPAND)
        self.left.SetSizer(left_sizer)

        self.CreateStatusBar()
        self.SetStatusText("Ready")

        self.addr.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_go)
        self.btn_theme.Bind(wx.EVT_BUTTON, self._toggle_theme)
        self.btn_newtab.Bind(wx.EVT_BUTTON, lambda _e: self.new_tab(START_URL))
        self.btn_downloads.Bind(wx.EVT_BUTTON, self._toggle_downloads)
        self.btn_history.Bind(wx.EVT_BUTTON, self._show_history_menu)
        self.btn_back.Bind(wx.EVT_BUTTON, self._on_back)
        self.btn_fwd.Bind(wx.EVT_BUTTON, self._on_forward)
        self.btn_reload.Bind(wx.EVT_BUTTON, self._on_reload)
        self.btn_stop.Bind(wx.EVT_BUTTON, self._on_stop)

        try:
            self.right.btn_scan.Bind(wx.EVT_BUTTON, self._start_image_pick)
        except Exception:
            pass

        self.new_tab(START_URL)
        self.apply_theme()

    def apply_theme(self) -> None:
        t = self._theme
        for w in (self, self.left, self.splitter, self.addr, self.right):
            w.SetBackgroundColour(t.bg)
            w.SetForegroundColour(t.fg)
        self.right.apply_theme()
        self.Refresh()

    def _toggle_theme(self, _evt=None) -> None:
        self._theme = LIGHT if self._theme.name == "dark" else DARK
        self.apply_theme()

    def _active(self) -> Optional[BrowserTab]:
        page = self.nb.GetCurrentPage()
        return page if isinstance(page, BrowserTab) else None

    def _generic_tab_icon_index(self) -> int:
        bmp = self.iconset.load_svg("newtab.svg", size=TAB_ICON_SIZE)
        return self._tab_images.Add(bmp)

    def new_tab(self, url: str) -> None:
        tab = BrowserTab(self.nb, on_title_changed=lambda _t, ttl: self.SetStatusText(ttl),
                         on_new_window=self._open_in_new_tab, on_webmsg=self._on_webmsg)
        idx_img = self._generic_tab_icon_index()
        self.nb.AddPage(tab, "", select=True, imageId=idx_img)
        tab.load(url)
        self.addr.ChangeValue(url)
        self._push_history(url, url)

    def _open_in_new_tab(self, url: str) -> None:
        self.new_tab(url)

    def _on_go(self, _evt) -> None:
        url = self.addr.GetValue().strip()
        if url and "://" not in url:
            url = "https://" + url
        a = self._active()
        if a and url:
            a.load(url)
            self._push_history(url, url)

    def _on_back(self, _evt): 
        a = self._active()
        if a and hasattr(a, "view") and a.view.CanGoBack():
            a.view.GoBack()

    def _on_forward(self, _evt):
        a = self._active()
        if a and hasattr(a, "view") and a.view.CanGoForward():
            a.view.GoForward()

    def _on_reload(self, _evt):
        a = self._active()
        if a and hasattr(a, "view"):
            a.view.Reload()

    def _on_stop(self, _evt):
        a = self._active()
        if a and hasattr(a, "view"):
            a.view.Stop()

    def _toggle_downloads(self, _evt=None) -> None:
        if self.splitter.IsSplit():
            self.splitter.Unsplit(self.right)
        else:
            self.splitter.SplitVertically(self.left, self.right, sashPosition=self.GetSize().width - 320)

    def _push_history(self, title: str, url: str) -> None:
        if url:
            self.history.appendleft(((title or url)[:128], url))

    def _show_history_menu(self, _evt=None) -> None:
        if not self.history:
            wx.MessageBox("No history yet.", "History", wx.OK | wx.ICON_INFORMATION, self)
            return
        menu = wx.Menu()
        for title, url in list(self.history)[:15]:
            item = menu.Append(wx.ID_ANY, title)
            self.Bind(wx.EVT_MENU, lambda _e, u=url: self._history_open(u), item)
        self.PopupMenu(menu)
        menu.Destroy()

    def _history_open(self, url: str) -> None:
        a = self._active()
        if a:
            a.load(url)
            self.addr.ChangeValue(url)

    def _start_image_pick(self, _evt=None) -> None:
        a = self._active()
        if not a: return
        self.SetStatusText("Pick an image…")
        a.start_hover_pick()

    def _on_webmsg(self, data: dict) -> None:
        t = data.get("type")
        if t == "pyweb/elementPicked":
            info = data.get("info") or {}
            self._request_image_candidates(info)
        elif t == "pyweb/imageCandidates":
            urls = [u for u in (data.get("urls") or []) if isinstance(u, str)]
            if urls:
                self._prompt_and_queue_urls(urls)
        elif t == "pyweb/favicon":
            href = data.get("href")
            if href:
                self._apply_favicon_to_active_tab(href)

    def _request_image_candidates(self, info: dict) -> None:
        a = self._active()
        if not a: return
        js = self._build_candidate_js(info)
        a.eval_js(js)

    def _build_candidate_js(self, info: dict) -> str:
        el_expr = "null"
        elem_id = (info.get("id") or "").strip()
        classes = info.get("classes") or []
        if elem_id:
            el_expr = f"document.getElementById({elem_id!r})"
        elif classes:
            cls = str(classes[0])
            el_expr = f"document.querySelector({('.' + cls).encode('unicode_escape').decode('utf-8')!r})"
        else:
            el_expr = "document.querySelector('img')"

        sibling_fn = dom_select.SIBLING_IMAGES_JS
        return (
            "(function(){"
            f"var el={el_expr};"
            "if(!el){el=document.querySelector('img');}"
            f"var __fn = {sibling_fn};"
            "var urls = __fn(el);"
            "if(window.chrome&&window.chrome.webview){window.chrome.webview.postMessage({type:'pyweb/imageCandidates', urls:urls});}"
            "return true;"
            "})();"
        )

    def _prompt_and_queue_urls(self, urls: List[str]) -> None:
        choices = [f"{i+1}. {u}" for i, u in enumerate(urls)]
        dlg = wx.MultiChoiceDialog(self, "Select images to download", "Images", choices)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                for i in dlg.GetSelections():
                    self.right.add_download(urls[i])
                if not self.splitter.IsSplit():
                    self._toggle_downloads()
        finally:
            dlg.Destroy()


    def _apply_favicon_to_active_tab(self, href: str) -> None:
        idx = self.nb.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        try:
            fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(href.split('?')[0])[1] or ".ico")
            os.close(fd)
            urllib.request.urlretrieve(href, tmp)
            img = wx.Image(tmp)
            if not img.IsOk():
                return
            img = img.Scale(TAB_ICON_SIZE[0], TAB_ICON_SIZE[1], wx.IMAGE_QUALITY_HIGH)
            bmp = wx.Bitmap(img)
            img_idx = self._tab_images.Add(bmp)
            self.nb.SetPageImage(idx, img_idx)
        except Exception:
            pass
