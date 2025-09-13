import wx
import wx.html2 as webview
from typing import Callable, Optional

from services import dom_select

WebMessageHandler = Callable[[dict], None]

WEBVIEW_BACKEND = getattr(webview, 'WebViewBackendEdge', webview.WebViewBackendDefault)


class BrowserTab(wx.Panel):
    def __init__(
        self,
        parent: wx.Window,
        on_title_changed: Callable[["BrowserTab", str], None],
        on_new_window: Callable[[str], None],
        on_webmsg: Optional[WebMessageHandler] = None,
    ) -> None:
        super().__init__(parent)
        self.on_title_changed = on_title_changed
        self.on_new_window = on_new_window
        self.on_webmsg = on_webmsg

        self.view = webview.WebView.New(self, backend=WEBVIEW_BACKEND)
        self.view.Bind(webview.EVT_WEBVIEW_TITLE_CHANGED, lambda e: on_title_changed(self, e.GetString()))
        self.view.Bind(webview.EVT_WEBVIEW_NEWWINDOW, self._ev_new_window)

        # Page loaded → trigger favicon probe (bind to LOADED if present, else NAVIGATED)
        if hasattr(webview, 'EVT_WEBVIEW_LOADED'):
            self.view.Bind(webview.EVT_WEBVIEW_LOADED, self._on_loaded)
        else:
            self.view.Bind(webview.EVT_WEBVIEW_NAVIGATED, self._on_loaded)

        # Script message bridge (WebView2 supports this)
        if hasattr(self.view, 'AddScriptMessageHandler'):
            try:
                self.view.AddScriptMessageHandler('pyweb')
                self.view.Bind(webview.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self._on_script_message)
            except Exception:
                pass

        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(s)

    # ---- host helpers ----
    def load(self, url: str) -> None:
        self.view.LoadURL(url)

    def eval_js(self, js: str) -> None:
        try:
            self.view.RunScript(js)
        except Exception:
            pass

    def start_hover_pick(self) -> None:
        self.eval_js(dom_select.HOVER_JS)

    # ---- events ----
    def _ev_new_window(self, evt: webview.WebViewEvent) -> None:
        self.on_new_window(evt.GetURL())
        evt.Veto()

    def _on_script_message(self, evt) -> None:
        if not self.on_webmsg:
            return
        try:
            msg = evt.GetString()
            import json
            data = json.loads(msg) if msg and msg[0] in '{[' else {'text': msg}
            self.on_webmsg(data)
        except Exception:
            pass

    def _on_loaded(self, _evt) -> None:
        # Ask the page for its favicon, defaulting to /favicon.ico if no link tag
        js = (
            "(function(){"
            " var href='';"
            " var el=document.querySelector('link[rel~=\"icon\"]')"
            "        ||document.querySelector('link[rel=\"shortcut icon\"]')"
            "        ||document.querySelector('link[rel=\"apple-touch-icon\"]');"
            " if(el){ try{ href=new URL(el.href, location.href).href; }catch(e){ href=el.href; } }"
            " if(!href){ try{ href=new URL('/favicon.ico', location.href).href; }catch(e){ href='/favicon.ico'; } }"
            " if(window.chrome&&window.chrome.webview){ window.chrome.webview.postMessage({type:'pyweb/favicon', href}); }"
            " return true;"
            "})();"
        )
        self.eval_js(js)
