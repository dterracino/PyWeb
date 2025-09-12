import wx
import wx.html2 as webview
import threading
import urllib.request
import os
from dataclasses import dataclass, field
from typing import Optional, List, Deque, Tuple
from collections import deque

START_URL = "https://example.com"
HISTORY_MAX = 50
ICON_SIZE = (20, 20)

# Choose the Edge (WebView2) backend when available
WEBVIEW_BACKEND = getattr(webview, "WebViewBackendEdge", webview.WebViewBackendDefault)

# ------------------------- THEME -------------------------
@dataclass
class Theme:
    name: str
    bg: wx.Colour
    fg: wx.Colour
    ctrl_bg: wx.Colour
    ctrl_fg: wx.Colour
    accent: wx.Colour

LIGHT = Theme(
    name="light",
    bg=wx.Colour(250, 250, 250),
    fg=wx.Colour(20, 20, 20),
    ctrl_bg=wx.Colour(255, 255, 255),
    ctrl_fg=wx.Colour(20, 20, 20),
    accent=wx.Colour(0, 120, 215),
)

DARK = Theme(
    name="dark",
    bg=wx.Colour(32, 32, 36),
    fg=wx.Colour(230, 230, 235),
    ctrl_bg=wx.Colour(45, 45, 50),
    ctrl_fg=wx.Colour(230, 230, 235),
    accent=wx.Colour(0, 122, 204),
)

# ---------------------- DOWNLOAD MODEL ----------------------
@dataclass
class DownloadItem:
    url: str
    dest: str
    status: str = "queued"  # queued | downloading | done | error | canceled
    progress: int = 0        # 0-100
    size_bytes: Optional[int] = None
    error: Optional[str] = None

# ----------------------- BROWSER TAB -----------------------
class BrowserTab(wx.Panel):
    def __init__(self, parent: wx.Window, on_title_changed, on_new_window, history_sink):
        super().__init__(parent)
        self.on_title_changed = on_title_changed
        self.on_new_window = on_new_window
        self.history_sink = history_sink

        self.view = webview.WebView.New(self, backend=WEBVIEW_BACKEND)

        # Navigation / events
        self.view.Bind(webview.EVT_WEBVIEW_TITLE_CHANGED, self._ev_title)
        self.view.Bind(webview.EVT_WEBVIEW_NAVIGATED, self._ev_navigated)
        self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._ev_loaded)
        self.view.Bind(webview.EVT_WEBVIEW_ERROR, self._ev_error)
        self.view.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self._ev_new_window)

        # Some backends emit script results; we register a handler if present
        if hasattr(webview, "EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED"):
            # Not used yet, but reserved for future DOM collection
            pass

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(sizer)

    # Basic WebView API passthroughs
    def load(self, url: str) -> None:
        self.view.LoadURL(url)

    def reload(self) -> None:
        self.view.Reload()

    def stop(self) -> None:
        self.view.Stop()

    def can_go_back(self) -> bool:
        return bool(self.view.CanGoBack())

    def can_go_fwd(self) -> bool:
        return bool(self.view.CanGoForward())

    def go_back(self) -> None:
        self.view.GoBack()

    def go_fwd(self) -> None:
        self.view.GoForward()

    def get_url(self) -> str:
        return self.view.GetCurrentURL() or ""

    def get_title(self) -> str:
        return getattr(self.view, "GetCurrentTitle", lambda: "")[0]() if hasattr(self.view, "GetCurrentTitle") else ""

    # DOM helpers (future bulk actions)
    def eval_js(self, js: str, on_result=None) -> None:
        """Try to evaluate JS on the page. On WebView2, RunScript may be async.
        We call RunScript and, if a result event exists, caller should have bound to it.
        For now, we best-effort and call on_result(None)."""
        try:
            ok = self.view.RunScript(js)
            if on_result:
                on_result(None if ok else None)
        except Exception:
            if on_result:
                on_result(None)

    # Events
    def _ev_title(self, evt: webview.WebViewEvent) -> None:
        self.on_title_changed(self, evt.GetString())

    def _ev_navigated(self, evt: webview.WebViewEvent) -> None:
        frame = wx.GetTopLevelParent(self)
        if isinstance(frame, BrowserFrame):
            frame.set_address(evt.GetURL())
        evt.Skip()

    def _ev_loaded(self, evt: webview.WebViewEvent) -> None:
        # Record to history sink
        url = self.get_url()
        title = getattr(evt, "GetTarget", lambda: "")() or self.get_title() or url
        if self.history_sink:
            self.history_sink(title, url)
        evt.Skip()

    def _ev_error(self, evt: webview.WebViewEvent) -> None:
        frame = wx.GetTopLevelParent(self)
        if isinstance(frame, BrowserFrame):
            frame.set_status(f"Load error: {evt.GetString()}")

    def _ev_new_window(self, evt: webview.WebViewEvent) -> None:
        url = evt.GetURL()
        self.on_new_window(url)
        evt.Veto()

# ----------------------- DOWNLOADS UI -----------------------
class DownloadsPanel(wx.Panel):
    def __init__(self, parent: wx.Window, theme_getter):
        super().__init__(parent)
        self._get_theme = theme_getter
        self.items: List[DownloadItem] = []

        # Controls
        header = wx.BoxSizer(wx.HORIZONTAL)
        self.url_box = wx.TextCtrl(self, value="", style=wx.TE_PROCESS_ENTER)
        self.btn_add = wx.Button(self, label="Add")
        self.btn_scan_imgs = wx.Button(self, label="Scan Page Images")
        header.Add(self.url_box, 1, wx.ALL | wx.EXPAND, 4)
        header.Add(self.btn_add, 0, wx.ALL, 4)
        header.Add(self.btn_scan_imgs, 0, wx.ALL, 4)

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        for i, (title, width) in enumerate([
            ("File", 220), ("Status", 90), ("Progress", 90), ("Size", 90), ("From", 220)
        ]):
            self.list.InsertColumn(i, title, width=width)

        controls = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, label="Start")
        self.btn_cancel = wx.Button(self, label="Cancel")
        self.btn_open_folder = wx.Button(self, label="Open Folder")
        controls.Add(self.btn_start, 0, wx.ALL, 4)
        controls.Add(self.btn_cancel, 0, wx.ALL, 4)
        controls.Add(self.btn_open_folder, 0, wx.ALL, 4)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(header, 0, wx.EXPAND)
        root.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        root.Add(controls, 0, 0)
        self.SetSizer(root)

        # Bindings
        self.url_box.Bind(wx.EVT_TEXT_ENTER, self._on_add_single)
        self.btn_add.Bind(wx.EVT_BUTTON, self._on_add_single)
        self.btn_start.Bind(wx.EVT_BUTTON, self._on_start)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self._on_cancel)
        self.btn_open_folder.Bind(wx.EVT_BUTTON, self._on_open_folder)
        self.btn_scan_imgs.Bind(wx.EVT_BUTTON, self._on_scan_images)

        self.apply_theme()

    # --- Public API ---
    def apply_theme(self) -> None:
        t = self._get_theme()
        self.SetBackgroundColour(t.bg)
        for ctrl in (self.url_box, self.list, self.btn_add, self.btn_scan_imgs, self.btn_start, self.btn_cancel, self.btn_open_folder):
            ctrl.SetBackgroundColour(t.ctrl_bg)
            ctrl.SetForegroundColour(t.ctrl_fg)
        self.Refresh()

    def add_download(self, url: str, dest_dir: Optional[str] = None) -> None:
        if not url:
            return
        if not dest_dir:
            dest_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(dest_dir, exist_ok=True)
        filename = os.path.basename(url.split("?")[0]) or "download.bin"
        dest = os.path.join(dest_dir, filename)
        item = DownloadItem(url=url, dest=dest)
        self.items.append(item)
        idx = self.list.InsertItem(self.list.GetItemCount(), filename)
        self.list.SetItem(idx, 1, item.status)
        self.list.SetItem(idx, 2, f"{item.progress}%")
        self.list.SetItem(idx, 3, "?")
        self.list.SetItem(idx, 4, url)

    # --- Events ---
    def _on_add_single(self, _evt) -> None:
        self.add_download(self.url_box.GetValue().strip())
        self.url_box.SetValue("")

    def _on_scan_images(self, _evt) -> None:
        # Placeholder: real impl will call active tab's eval_js to collect image URLs
        wx.MessageBox(
            "Future feature: this will scan the active page's DOM for <img> src and offer a checklist to download.",
            "Scan Images", wx.OK | wx.ICON_INFORMATION, self
        )

    def _on_start(self, _evt) -> None:
        sel = self.list.GetFirstSelected()
        if sel == -1:
            # Start all queued
            for i, it in enumerate(self.items):
                if it.status in ("queued", "error", "canceled"):
                    self._start_download(i)
        else:
            self._start_download(sel)

    def _on_cancel(self, _evt) -> None:
        # For simplicity, not implementing mid-stream cancel in this preview
        wx.MessageBox("Cancel is a placeholder in this preview.", "Cancel", wx.OK | wx.ICON_INFORMATION, self)

    def _on_open_folder(self, _evt) -> None:
        if self.items:
            folder = os.path.dirname(self.items[0].dest)
            if os.name == "nt":
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f"open '{folder}'")
            else:
                os.system(f"xdg-open '{folder}'")

    def _start_download(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.items):
            return
        item = self.items[idx]
        if item.status == "downloading":
            return
        item.status = "downloading"
        self._refresh_row(idx)

        def worker():
            try:
                with urllib.request.urlopen(item.url) as resp:
                    total = resp.length if hasattr(resp, "length") else None
                    item.size_bytes = total
                    with open(item.dest, "wb") as f:
                        read = 0
                        while True:
                            chunk = resp.read(64 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            read += len(chunk)
                            if total:
                                item.progress = int(read * 100 / max(1, total))
                            else:
                                # Unknown size; show spinner-ish by modulo
                                item.progress = (item.progress + 5) % 100
                            wx.CallAfter(self._refresh_row, idx)
                item.progress = 100
                item.status = "done"
                wx.CallAfter(self._refresh_row, idx)
            except Exception as e:
                item.status = "error"
                item.error = str(e)
                wx.CallAfter(self._refresh_row, idx)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_row(self, idx: int) -> None:
        if 0 <= idx < self.list.GetItemCount():
            it = self.items[idx]
            filename = os.path.basename(it.dest)
            self.list.SetItem(idx, 0, filename)
            self.list.SetItem(idx, 1, it.status)
            self.list.SetItem(idx, 2, f"{it.progress}%")
            size_str = f"{it.size_bytes/1024:.0f} KB" if it.size_bytes else "?"
            self.list.SetItem(idx, 3, size_str)
            self.list.SetItem(idx, 4, it.url)

# ----------------------- MAIN FRAME -----------------------
class BrowserFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="wx WebView2 Mini Browser", size=wx.Size(1100, 750))

        self._theme: Theme = DARK if self._prefers_dark_default() else LIGHT
        self.history: Deque[Tuple[str, str]] = deque(maxlen=HISTORY_MAX)

        # ==== Docking layout (splitter) ====
        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.left_panel = wx.Panel(self.splitter)
        self.right_panel = DownloadsPanel(self.splitter, theme_getter=self.get_theme)
        self.splitter.SplitVertically(self.left_panel, self.right_panel, sashPosition=self.GetSize().width - 280)
        self.splitter.SetSashGravity(1.0)  # favor the left
        self.splitter.Unsplit(self.right_panel)  # start hidden

        # ==== Top chrome on left panel ====
        chrome = wx.Panel(self.left_panel)
        self.btn_back = self._icon_button(chrome, wx.ART_GO_BACK, tooltip="Back")
        self.btn_fwd = self._icon_button(chrome, wx.ART_GO_FORWARD, tooltip="Forward")
        self.btn_reload = self._icon_button(chrome, wx.ART_REDO, tooltip="Reload")
        self.btn_stop = self._icon_button(chrome, wx.ART_CROSS_MARK, tooltip="Stop")
        self.addr = wx.TextCtrl(chrome, style=wx.TE_PROCESS_ENTER)
        self.btn_go = self._icon_button(chrome, wx.ART_GO_DIR_RIGHT, tooltip="Go")
        self.btn_newtab = self._icon_button(chrome, wx.ART_NEW, tooltip="New Tab")
        self.btn_downloads = self._icon_button(chrome, wx.ART_LIST_VIEW, tooltip="Toggle Downloads Sidebar")
        self.btn_theme = wx.Button(chrome, label="☾")  # theme toggle
        self.btn_theme.SetToolTip("Toggle dark theme")

        top = wx.BoxSizer(wx.HORIZONTAL)
        for w in (self.btn_back, self.btn_fwd, self.btn_reload, self.btn_stop, self.addr, self.btn_go, self.btn_newtab, self.btn_downloads, self.btn_theme):
            expand = wx.EXPAND if w is self.addr else 0
            proportion = 1 if w is self.addr else 0
            top.Add(w, proportion, wx.ALL | expand, 4)

        # ==== Tabs ====
        self.nb = wx.Notebook(self.left_panel, style=wx.NB_TOP | wx.NB_NOPAGETHEME)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_switched)

        # ==== Layout left panel ====
        lp_sizer = wx.BoxSizer(wx.VERTICAL)
        lp_sizer.Add(chrome, 0, wx.EXPAND)
        lp_sizer.Add(self.nb, 1, wx.EXPAND)
        self.left_panel.SetSizer(lp_sizer)

        # Status bar
        self.CreateStatusBar()
        self.set_status("Ready")

        # Menus
        self._build_menu()

        # Wire buttons
        self.addr.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_go)
        self.btn_back.Bind(wx.EVT_BUTTON, self._on_back)
        self.btn_fwd.Bind(wx.EVT_BUTTON, self._on_forward)
        self.btn_reload.Bind(wx.EVT_BUTTON, self._on_reload)
        self.btn_stop.Bind(wx.EVT_BUTTON, self._on_stop)
        self.btn_newtab.Bind(wx.EVT_BUTTON, lambda _e: self.new_tab(START_URL))
        self.btn_downloads.Bind(wx.EVT_BUTTON, self._toggle_downloads)
        self.btn_theme.Bind(wx.EVT_BUTTON, self._toggle_theme)

        # Shortcuts
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("L"), wx.ID_FIND),
            (wx.ACCEL_CTRL, ord("T"), wx.ID_NEW),
            (wx.ACCEL_CTRL, ord("W"), wx.ID_CLOSE),
            (wx.ACCEL_CTRL, ord("R"), wx.ID_REFRESH),
            (wx.ACCEL_CTRL, ord("J"), wx.ID_JUMP_TO),  # downloads
            (wx.ACCEL_CTRL, ord("H"), wx.ID_HOME),     # history
        ])
        self.SetAcceleratorTable(accel_tbl)
        self.Bind(wx.EVT_MENU, lambda _e: self.addr.SetFocus(), id=wx.ID_FIND)
        self.Bind(wx.EVT_MENU, lambda _e: self.new_tab(START_URL), id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self._on_close_tab, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_MENU, self._on_reload, id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self._toggle_downloads, id=wx.ID_JUMP_TO)
        self.Bind(wx.EVT_MENU, self._show_history_menu, id=wx.ID_HOME)

        # Start with a tab
        self.new_tab(START_URL)
        self.apply_theme()

    # ---- Theme helpers ----
    def get_theme(self) -> Theme:
        return self._theme

    def _prefers_dark_default(self) -> bool:
        # Basic heuristic; can be extended to read OS pref
        return True

    def apply_theme(self) -> None:
        t = self._theme
        for panel in (self, self.left_panel, self.splitter):
            panel.SetBackgroundColour(t.bg)
            panel.SetForegroundColour(t.fg)
        for ctrl in (self.addr, self.btn_theme):
            ctrl.SetBackgroundColour(t.ctrl_bg)
            ctrl.SetForegroundColour(t.ctrl_fg)
        self.right_panel.apply_theme()
        self.Refresh()

    def _toggle_theme(self, _evt=None) -> None:
        self._theme = LIGHT if self._theme.name == "dark" else DARK
        self.apply_theme()

    def _icon_button(self, parent, art_id, tooltip: str = "") -> wx.BitmapButton:
        bmp = wx.ArtProvider.GetBitmap(art_id, wx.ART_TOOLBAR, ICON_SIZE)
        btn = wx.BitmapButton(parent, bitmap=bmp, style=wx.BU_AUTODRAW)
        if tooltip:
            btn.SetToolTip(tooltip)
        return btn

    # ---- Menu ----
    def _build_menu(self) -> None:
        bar = wx.MenuBar()
        filem = wx.Menu()
        filem.Append(wx.ID_NEW, "&New Tab	Ctrl+T")
        filem.Append(wx.ID_CLOSE, "&Close Tab	Ctrl+W")
        filem.AppendSeparator()
        quit_item = filem.Append(wx.ID_EXIT, "E&xit")
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), quit_item)

        navm = wx.Menu()
        navm.Append(wx.ID_BACKWARD, "Back")
        navm.Append(wx.ID_FORWARD, "Forward")
        navm.Append(wx.ID_REFRESH, "Reload	Ctrl+R")
        navm.Append(wx.ID_JUMP_TO, "Downloads	Ctrl+J")
        navm.Append(wx.ID_HOME, "History	Ctrl+H")
        self.Bind(wx.EVT_MENU, self._on_back, id=wx.ID_BACKWARD)
        self.Bind(wx.EVT_MENU, self._on_forward, id=wx.ID_FORWARD)
        self.Bind(wx.EVT_MENU, self._on_reload, id=wx.ID_REFRESH)
        self.Bind(wx.EVT_MENU, self._toggle_downloads, id=wx.ID_JUMP_TO)
        self.Bind(wx.EVT_MENU, self._show_history_menu, id=wx.ID_HOME)

        viewm = wx.Menu()
        self.menu_dark = viewm.AppendCheckItem(wx.ID_ANY, "Dark Theme")
        self.menu_dark.Check(self._theme.name == "dark")
        self.Bind(wx.EVT_MENU, lambda _e: self._toggle_theme(), self.menu_dark)

        bar.Append(filem, "&File")
        bar.Append(navm, "&Navigate")
        bar.Append(viewm, "&View")
        self.SetMenuBar(bar)

    # ---- Active tab helpers ----
    def _active(self) -> Optional[BrowserTab]:
        if self.nb.GetPageCount() == 0:
            return None
        page = self.nb.GetCurrentPage()
        return page if isinstance(page, BrowserTab) else None

    def _find_page_index(self, page: BrowserTab) -> Optional[int]:
        for i in range(self.nb.GetPageCount()):
            if self.nb.GetPage(i) is page:
                return i
        return None

    def set_status(self, text: str) -> None:
        self.SetStatusText(text)

    def set_address(self, url: str) -> None:
        self.addr.ChangeValue(url)

    # ---- History ----
    def _push_history(self, title: str, url: str) -> None:
        if not url:
            return
        self.history.appendleft((title or url, url))

    def _show_history_menu(self, _evt=None) -> None:
        if not self.history:
            wx.MessageBox("No history yet.", "History", wx.OK | wx.ICON_INFORMATION, self)
            return
        menu = wx.Menu()
        # show up to 15 recent
        for i, (title, url) in enumerate(list(self.history)[:15]):
            item = menu.Append(wx.ID_ANY, f"{title[:48]}" + ("…" if len(title) > 48 else ""))
            # capture url in default arg
            self.Bind(wx.EVT_MENU, lambda _e, u=url: self._open_history(u), item)
        self.PopupMenu(menu)
        menu.Destroy()

    def _open_history(self, url: str) -> None:
        active = self._active()
        if active:
            active.load(url)

    # ---- Downloads ----
    def _toggle_downloads(self, _evt=None) -> None:
        if self.splitter.IsSplit():
            # Hide sidebar
            self.splitter.Unsplit(self.right_panel)
        else:
            # Show sidebar
            if not self.splitter.IsSplit():
                self.splitter.SplitVertically(self.left_panel, self.right_panel, sashPosition=self.GetSize().width - 320)
            # Focus url box in sidebar
            self.right_panel.url_box.SetFocus()

    # ---- Actions wired to UI ----
    def new_tab(self, url: str, title: str = "New Tab") -> None:
        tab = BrowserTab(
            self.nb,
            on_title_changed=self._tab_title_changed,
            on_new_window=self._open_in_new_tab,
            history_sink=self._push_history,
        )
        self.nb.AddPage(tab, title, select=True)
        tab.load(url)
        self.set_address(url)
        self.set_status("Loading…")

    def close_current_tab(self) -> None:
        idx = self.nb.GetSelection()
        if idx != wx.NOT_FOUND:
            self.nb.DeletePage(idx)

    def _open_in_new_tab(self, url: str) -> None:
        self.new_tab(url)

    def _tab_title_changed(self, tab: BrowserTab, title: str) -> None:
        idx = self._find_page_index(tab)
        if idx is not None:
            shown = title if title else "Loading…"
            if len(shown) > 30:
                shown = shown[:27] + "…"
            self.nb.SetPageText(idx, shown)
        if tab is self._active():
            self.set_status(title or "")

    def _on_tab_switched(self, _evt: wx.BookCtrlEvent) -> None:
        active = self._active()
        if active:
            self.set_address(active.get_url())

    def _on_go(self, _evt: wx.CommandEvent) -> None:
        url = self.addr.GetValue().strip()
        if url and "://" not in url:
            url = "https://" + url
        active = self._active()
        if active and url:
            active.load(url)

    def _on_back(self, _evt: wx.CommandEvent) -> None:
        active = self._active()
        if active and active.can_go_back():
            active.go_back()

    def _on_forward(self, _evt: wx.CommandEvent) -> None:
        active = self._active()
        if active and active.can_go_fwd():
            active.go_fwd()

    def _on_reload(self, _evt: wx.CommandEvent) -> None:
        active = self._active()
        if active:
            active.reload()

    def _on_stop(self, _evt: wx.CommandEvent) -> None:
        active = self._active()
        if active:
            active.stop()

    def _on_close_tab(self, _evt: wx.CommandEvent) -> None:
        self.close_current_tab()

# --------------------------- APP ---------------------------
class App(wx.App):
    def OnInit(self) -> bool:  # type: ignore[override]
        frame = BrowserFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = App(False)
    app.MainLoop()
