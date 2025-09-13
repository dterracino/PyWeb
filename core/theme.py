
from dataclasses import dataclass
import wx

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
    bg=wx.Colour(250, 250, 250), fg=wx.Colour(20, 20, 20),
    ctrl_bg=wx.Colour(255, 255, 255), ctrl_fg=wx.Colour(20, 20, 20),
    accent=wx.Colour(0, 120, 215)
)

DARK = Theme(
    name="dark",
    bg=wx.Colour(32, 32, 36), fg=wx.Colour(230, 230, 235),
    ctrl_bg=wx.Colour(45, 45, 50), ctrl_fg=wx.Colour(230, 230, 235),
    accent=wx.Colour(0, 122, 204)
)
