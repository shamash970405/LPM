# morefunction.py
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Input, Select, Button
from textual.widgets.option_list import Option
from textual.containers import Vertical, Horizontal

# ================= 🎨 佈景主題切換跳窗 =================
class ThemeMenuScreen(ModalScreen):
    """自訂的主題切換跳窗"""
    
    CSS = """
    ThemeMenuScreen { align: center middle; background: rgba(0, 0, 0, 0.6); }
    #theme-container {
        width: 40; height: auto; background: #1f2335; border: thick #7aa2f7; padding: 1;
    }
    #theme-title { text-align: center; text-style: bold; color: #e0af68; margin-bottom: 1; }
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
        
        if theme_choice == "tokyo":
            self.dismiss("tokyonight")
        elif theme_choice == "dracula":
            self.dismiss("dracula")
        elif theme_choice == "nord":
            self.dismiss("nord")
        else:
            self.dismiss("")

# ================= ⚙️ 系統設定中心跳窗 =================
class SettingsScreen(ModalScreen):
    """彈出的系統設定視窗，支援多重 AI 選擇與 API Token 輸入"""
    
    CSS = """
    SettingsScreen { align: center middle; background: rgba(0, 0, 0, 0.7); }
    #settings-container {
        width: 70; height: auto; background: #1f2335; border: thick #7aa2f7; padding: 1 2;
    }
    #settings-title { text-align: center; text-style: bold; color: #7aa2f7; margin-bottom: 2; width: 100%; }

    /* 每一行的左右排版容器 */
    .setting-row { height: auto; margin-bottom: 1; align: left middle; }
    
    /* 左邊的選項名稱 (固定寬度) */
    .setting-label { width: 20; content-align: left middle; }
    
    /* 右邊的控制項 (自動彈性填滿剩下的空間) */
    .setting-control { width: 1fr; }

    /* 按鈕區靠右 */
    .settings-btn-box { height: auto; align: right middle; margin-top: 1; }
    #setting-cancel { margin-right: 2; }
    """

    def __init__(self, current_token: str = "") -> None:
        super().__init__()
        self.current_token = current_token

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("⚙️ 系統設定中心", id="settings-title")

            # 🛠️ 選項 1：選擇 AI
            with Horizontal(classes="setting-row"):
                yield Label("選擇要使用的 AI：", classes="setting-label")
                yield Select(
                    options=[
                        ("Gemini", "gemini"), 
                        ("DeepSeek", "deepseek"), 
                        ("ChatGPT", "chatgpt"), 
                        ("Grok", "grok")
                    ],
                    prompt="請選擇 AI 引擎",
                    id="setting-ai-model",
                    classes="setting-control"
                )
            
            # 🛠️ 選項 2：API Token
            with Horizontal(classes="setting-row"):
                yield Label("API Token：", classes="setting-label")
                yield Input(
                    value=self.current_token, 
                    placeholder="請輸入對應的 API 密鑰...", 
                    password=True, 
                    id="setting-api-token", 
                    classes="setting-control"
                )

            # 🛑 控制按鈕組
            with Horizontal(classes="settings-btn-box"):
                yield Button("取消", id="setting-cancel", variant="error")
                yield Button("儲存設定 💾", id="setting-save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setting-cancel":
            self.dismiss(None) # 放棄修改，直接關閉
            return

        if event.button.id == "setting-save":
            # 抓取下拉選單與輸入框的資料
            ai_choice = self.query_one("#setting-ai-model").value
            api_token = self.query_one("#setting-api-token").value
            
            if not ai_choice or ai_choice == Select.BLANK:
                self.notify("❌ 請先選擇一個 AI 引擎！", severity="error")
                return
            
            # 彈出成功通知
            hidden_token = "***" if api_token else "未輸入"
            self.notify(f"✅ 設定已更新！引擎: {str(ai_choice).upper()}, Token: {hidden_token}")
            
            # 🚀 將打包好的設定字典回傳給 manager.py (主程式)
            self.dismiss({"ai_engine": ai_choice, "api_token": api_token})