import wx
import wx.html2 as webview
from typing import Optional

START_URL = "https://example.com"

# Choose the Edge (WebView2) backend when available
WEBVIEW_BACKEND = getattr(webview, "WebViewBackendEdge", webview.WebViewBackendDefault)


class BrowserTab(wx.Panel):
    def __init__(self, parent: wx.Window, on_title_changed, on_new_window):
        super().__init__(parent)
        self.on_title_changed = on_title_changed
        self.on_new_window = on_new_window

        self.view = webview.WebView.New(self, backend=WEBVIEW_BACKEND)

        # Status / navigation updates
        self.view.Bind(webview.EVT_WEBVIEW_TITLE_CHANGED, self._ev_title)
        self.view.Bind(webview.EVT_WEBVIEW_NAVIGATED, self._ev_navigated)
        self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._ev_loaded)
        self.view.Bind(webview.EVT_WEBVIEW_ERROR, self._ev_error)
        # Open target=_blank etc. in a new tab:
        self.view.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self._ev_new_window)

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

    # Events
    def _ev_title(self, evt: webview.WebViewEvent) -> None:
        self.on_title_changed(self, evt.GetString())

    def _ev_navigated(self, evt: webview.WebViewEvent) -> None:
        # Keep address bar in sync
        frame = wx.GetTopLevelParent(self)
        if isinstance(frame, BrowserFrame):
            frame.set_address(evt.GetURL())
        evt.Skip()

    def _ev_loaded(self, evt: webview.WebViewEvent) -> None:
        evt.Skip()

    def _ev_error(self, evt: webview.WebViewEvent) -> None:
        frame = wx.GetTopLevelParent(self)
        if isinstance(frame, BrowserFrame):
            frame.set_status(f"Load error: {evt.GetString()}")

    def _ev_new_window(self, evt: webview.WebViewEvent) -> None:
        # Open target in new tab instead of separate window
        url = evt.GetURL()
        self.on_new_window(url)
        evt.Veto()  # prevent default external window


class BrowserFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="wx WebView2 Mini Browser", size=wx.Size(1100, 750))

        # ==== Top chrome ====
        panel = wx.Panel(self)
        self.btn_back = wx.Button(panel, label="⟨")
        self.btn_fwd = wx.Button(panel, label="⟩")
        self.btn_reload = wx.Button(panel, label="⟳")
        self.btn_stop = wx.Button(panel, label="✕")
        self.addr = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.btn_go = wx.Button(panel, label="Go")
        self.btn_newtab = wx.Button(panel, label="+ Tab")

        top = wx.BoxSizer(wx.HORIZONTAL)
        for w in (self.btn_back, self.btn_fwd, self.btn_reload, self.btn_stop, self.addr, self.btn_go, self.btn_newtab):
            expand = wx.EXPAND if w is self.addr else 0
            proportion = 1 if w is self.addr else 0
            top.Add(w, proportion, wx.ALL | expand, 4)

        # ==== Tabs ====
        self.nb = wx.Notebook(panel, style=wx.NB_TOP | wx.NB_NOPAGETHEME)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_switched)

        # ==== Layout ====
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(top, 0, wx.EXPAND)
        root.Add(self.nb, 1, wx.EXPAND)
        panel.SetSizer(root)

        # Status bar
        self.CreateStatusBar()
        self.set_status("Ready")

        # Menu (optional niceties)
        self._build_menu()

        # Wire buttons safely (store active tab first so type checker is happy)
        self.addr.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_go)
        self.btn_back.Bind(wx.EVT_BUTTON, self._on_back)
        self.btn_fwd.Bind(wx.EVT_BUTTON, self._on_forward)
        self.btn_reload.Bind(wx.EVT_BUTTON, self._on_reload)
        self.btn_stop.Bind(wx.EVT_BUTTON, self._on_stop)
        self.btn_newtab.Bind(wx.EVT_BUTTON, lambda _e: self.new_tab(START_URL))

        # Keyboard shortcuts
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("L"), wx.ID_FIND),  # Focus address bar
            (wx.ACCEL_CTRL, ord("T"), wx.ID_NEW),  # New tab
            (wx.ACCEL_CTRL, ord("W"), wx.ID_CLOSE),  # Close tab
            (wx.ACCEL_CTRL, ord("R"), wx.ID_REFRESH),  # Reload
        ])
        self.SetAcceleratorTable(accel_tbl)
        self.Bind(wx.EVT_MENU, lambda _e: self.addr.SetFocus(), id=wx.ID_FIND)
        self.Bind(wx.EVT_MENU, lambda _e: self.new_tab(START_URL), id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self._on_close_tab, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_MENU, self._on_reload, id=wx.ID_REFRESH)

        # Start with one tab
        self.new_tab(START_URL)

    # ---- Menu helpers ----
    def _build_menu(self) -> None:
        bar = wx.MenuBar()
        filem = wx.Menu()
        filem.Append(wx.ID_NEW, "&New Tab\tCtrl+T")
        filem.Append(wx.ID_CLOSE, "&Close Tab\tCtrl+W")
        filem.AppendSeparator()
        quit_item = filem.Append(wx.ID_EXIT, "E&xit")
        self.Bind(wx.EVT_MENU, lambda _e: self.Close(), quit_item)

        navm = wx.Menu()
        navm.Append(wx.ID_BACKWARD, "Back")
        navm.Append(wx.ID_FORWARD, "Forward")
        navm.Append(wx.ID_REFRESH, "Reload\tCtrl+R")
        self.Bind(wx.EVT_MENU, self._on_back, id=wx.ID_BACKWARD)
        self.Bind(wx.EVT_MENU, self._on_forward, id=wx.ID_FORWARD)
        self.Bind(wx.EVT_MENU, self._on_reload, id=wx.ID_REFRESH)

        bar.Append(filem, "&File")
        bar.Append(navm, "&Navigate")
        self.SetMenuBar(bar)

    # ---- Active tab helpers ----
    def _active(self) -> Optional[BrowserTab]:
        if self.nb.GetPageCount() == 0:
            return None
        page = self.nb.GetCurrentPage()
        # Pylance-friendly: confirm the type
        if isinstance(page, BrowserTab):
            return page
        return None

    def _find_page_index(self, page: BrowserTab) -> Optional[int]:
        # Avoid stub issues with GetPageIndex by scanning
        for i in range(self.nb.GetPageCount()):
            if self.nb.GetPage(i) is page:
                return i
        return None

    # ---- Actions wired to UI ----
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

    # ---- Tab management ----
    def new_tab(self, url: str, title: str = "New Tab") -> None:
        tab = BrowserTab(self.nb, on_title_changed=self._tab_title_changed, on_new_window=self._open_in_new_tab)
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
        # Sync address bar when user changes tabs
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

    # ---- UI helpers ----
    def set_status(self, text: str) -> None:
        self.SetStatusText(text)

    def set_address(self, url: str) -> None:
        # ChangeValue avoids re-firing EVT_TEXT
        self.addr.ChangeValue(url)


class App(wx.App):
    def OnInit(self) -> bool:  # type: ignore[override]
        # On Windows, this will use Edge WebView2 if the runtime is present.
        frame = BrowserFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = App(False)
    app.MainLoop()
