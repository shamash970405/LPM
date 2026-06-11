import os
from pathlib import Path

# 🎯 物理定位：設定主題資料夾的絕對路徑
# 這樣不論你在哪個目錄下執行 manager.py，路徑都絕對不會迷路
BASE_DIR = Path(__file__).parent
THEMES_DIR = BASE_DIR / "themes"

class ThemeManager:
    def __init__(self, theme_name="tokyonight"):
        self.current_theme = theme_name

    def get_css_path(self) -> str:
        """根據目前選定的主題名稱，返回對應的 themes/主題.css 路徑"""
        # 確保 themes 資料夾存在
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
        
        css_file = THEMES_DIR / f"{self.current_theme}.css"
        
        # 🛡️ 超強防禦：如果主題檔不存在，就自動 fallback 給它預設的 theme.css
        if not css_file.exists():
            return str(BASE_DIR / "theme.css")
        return str(css_file)

    def get_rich_color(self, element_type: str) -> str:
        """🎯 全新高亮引擎：用來動態更換你 table.add_row 裡的 [bold #xxxxxx] 顏色"""
        # 你可以把原本 theme.py 裡的那些十六進位顏色全部集中管理在這裡！
        theme_database = {
            "tokyonight": {
                "manager": "#e0af68",   # 橘黃
                "group": "#9ece6a",     # 亮綠
                "version": "#7aa2f7",   # 藍
                "size": "#bb9af7"       # 紫
            },
            "nord": {
                "manager": "#ebcb8b",   # 北歐金
                "group": "#a3be8c",     # 北歐綠
                "version": "#81a1c1",   # 北歐藍
                "size": "#b48ead"       # 北歐紫
            }
        }
        # 抓不到主題就 fallback 回 tokyonight
        colors = theme_database.get(self.current_theme, theme_database["tokyonight"])
        return colors.get(element_type, "#ffffff")