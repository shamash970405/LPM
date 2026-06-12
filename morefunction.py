# morefunction.py
from textual.app import ComposeResult
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option
from textual.containers import Vertical
from textual.screen import ModalScreen
import theme  # 引入剛改好的純字串 Theme.py
from textual.screen import ModalScreen
from textual.widgets import Input, Button
from textual.containers import Vertical, Horizontal

class ThemeMenuScreen(ModalScreen):
    """自訂的主題切換跳窗"""
    
    CSS = """
    ThemeMenuScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #theme-container {
        width: 40;
        height: auto;
        background: #1f2335;
        border: thick #7aa2f7;
        padding: 1;
    }
    #theme-title {
        text-align: center;
        text-style: bold;
        color: #e0af68;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-container"):
            yield Label("🎨 請選擇介面佈景主題", id="theme-title")
            yield OptionList(
                Option("🗼 Tokyo Night (東京暗夜)", id="tokyo"),
                Option("🧛 Dracula (吸血鬼暗黑)", id="dracula"),
                Option("❄️ Nord (北歐冰雪藍灰)", id="nord")
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        theme_choice = event.option.id
        
        # 🎯 滿血進化：只回傳安全的純文字字串，徹底拔除變數找不到的閃退引信！
        if theme_choice == "tokyo":
            self.dismiss("tokyonight")
        elif theme_choice == "dracula":
            self.dismiss("dracula")
        elif theme_choice == "nord":
            self.dismiss("nord")
        else:
            self.dismiss("")

# ================= 自訂的系統設定中心跳窗 =================
class SettingsScreen(ModalScreen):
    """彈出的系統設定視窗，用來輸入與儲存 Gemini API Token"""
    
    CSS = """
    SettingsScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #settings-container {
        width: 60;
        height: auto;
        background: #1f2335;
        border: thick #7aa2f7;
        padding: 1;
    }
    #settings-title {
        text-align: center;
        text-style: bold;
        color: #7aa2f7;
        margin-bottom: 1;
    }
    .settings-btn-box {
        layout: horizontal;
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    .settings-btn-box Button {
        width: 15;
        margin: 0 1;
    }
    """

    def __init__(self, current_token: str = "") -> None:
        super().__init__()
        self.current_token = current_token

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("⚙️ LPM 系統設定中心", id="settings-title")
            yield Label("請輸入您的 Gemini API 金鑰 (Token)：")
            yield Input(
                value=self.current_token, 
                placeholder="請貼上 AIzaSy...", 
                id="token-input",
                password=True  # 🔒 自動隱藏明文，防止旁人偷窺
            )
            with Horizontal(classes="settings-btn-box"):
                yield Button("儲存設定", id="save-settings", variant="success")
                yield Button("取消返回", id="cancel-settings", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-settings":
            new_token = self.query_one("#token-input", Input).value.strip()
            self.dismiss(new_token)  # 🚀 回傳輸入的 Token 給主程式
        elif event.button.id == "cancel-settings":
            self.dismiss(None)       # ↩️ 放棄修改