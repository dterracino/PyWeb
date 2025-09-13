
import wx, wx.html2 as webview
from typing import Callable, Optional
from services import dom_select

WebMessageHandler = Callable[[dict], None]

WEBVIEW_BACKEND = getattr(webview, 'WebViewBackendEdge', webview.WebViewBackendDefault)

class BrowserTab(wx.Panel):
    def __init__(self, parent: wx.Window, on_title_changed: Callable[['BrowserTab', str], None], on_new_window: Callable[[str], None], on_webmsg: Optional[WebMessageHandler]=None):
        super().__init__(parent)
        self.on_title_changed = on_title_changed
        self.on_new_window = on_new_window
        self.on_webmsg = on_webmsg

        self.view = webview.WebView.New(self, backend=WEBVIEW_BACKEND)
        self.view.Bind(webview.EVT_WEBVIEW_TITLE_CHANGED, lambda e: on_title_changed(self, e.GetString()))
        self.view.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self._ev_new_window)

        if hasattr(self.view, 'AddScriptMessageHandler'):
            try:
                self.view.AddScriptMessageHandler('pyweb')
                self.view.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message)
            except Exception:
                pass

        s = wx.BoxSizer(wx.VERTICAL); s.Add(self.view, 1, wx.EXPAND); self.SetSizer(s)

    def load(self, url: str): self.view.LoadURL(url)
    def eval_js(self, js: str):
        try: self.view.RunScript(js)
        except Exception: pass

    def start_hover_pick(self): self.eval_js(dom_select.HOVER_JS)

    def _ev_new_window(self, evt: webview.WebViewEvent):
        self.on_new_window(evt.GetURL()); evt.Veto()

    def _on_script_message(self, evt):
        if not self.on_webmsg: return
        try:
            msg = evt.GetString()
            import json
            data = json.loads(msg) if msg and msg[0] in '{[' else { 'text': msg }
            self.on_webmsg(data)
        except Exception:
            pass
