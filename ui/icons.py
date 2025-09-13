
import os, wx
try:
    import wx.svg as wxsvg  # wxPython >= 4.1
except Exception:
    wxsvg = None

ICON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources", "icons"))

class Iconset:
    def __init__(self, theme_fg: wx.Colour):
        self.fg = theme_fg

    def load_svg(self, name: str, size=(20,20)) -> wx.Bitmap:
        path = os.path.join(ICON_DIR, name)
        if wxsvg and os.path.exists(path):
            img = wxsvg.SVGimage.CreateFromFile(path)
            bmp = img.ConvertToBitmap(width=size[0], height=size[1])
            return bmp
        # fallback to PNG if present
        png_path = path.replace('.svg', '.png')
        if os.path.exists(png_path):
            img = wx.Image(png_path)
            img = img.Rescale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
            return wx.Bitmap(img)
        return wx.Bitmap(width=size[0], height=size[1])
