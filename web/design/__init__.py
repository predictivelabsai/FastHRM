"""FastSME shared design system.

Tokens, fonts and reusable public-page primitives shared across every FastSME
product. Product-specific colour is injected via a single ``--accent`` token so
FastHR, FastMail, FastDrive … can each set their own without forking the CSS.
"""
from .system import (
    Product,
    DESIGN_CSS,
    FONT_LINKS,
    accent_style,
    fs_button,
    fs_nav,
    fs_footer,
    fs_logo_strip,
    fs_eyebrow,
    MOBILE_NAV_JS,
)

__all__ = [
    "Product",
    "DESIGN_CSS",
    "FONT_LINKS",
    "accent_style",
    "fs_button",
    "fs_nav",
    "fs_footer",
    "fs_logo_strip",
    "fs_eyebrow",
    "MOBILE_NAV_JS",
]
