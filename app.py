
import wx
from ui.main_frame import BrowserFrame

def main():
    app = wx.App(False)
    frame = BrowserFrame()
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()
