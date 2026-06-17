# morefunction.py
import os
import re
from collections import defaultdict

from textual import on
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList, Input, Select, Button, Checkbox, TextArea
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

# ================= 📤 匯出套件列表跳窗 =================
class ExportModal(ModalScreen):
    """匯出套件清單的專屬視窗 (附帶過濾與即時預覽)"""
    
    CSS = """
    ExportModal { align: center middle; background: rgba(0, 0, 0, 0.7); }
    #export-container { width: 75; height: 35; background: #1f2335; border: thick #7aa2f7; padding: 1 2; }
    #export-title { text-align: center; text-style: bold; color: #7aa2f7; margin-bottom: 1; width: 100%; }
    .export-row { height: auto; margin-bottom: 1; align: left middle; }
    .export-label { width: 15; content-align: left middle; }
    .export-control { width: 1fr; }
    .export-checkboxes { height: auto; layout: horizontal; margin-bottom: 1; }
    .export-checkboxes Checkbox { margin-right: 2; }
    #export-preview { height: 1fr; border: solid #565f89; background: #1a1b26; color: #a9b1d6; margin-bottom: 1; }
    .export-btn-box { height: auto; align: right middle; }
    #export-cancel { margin-right: 2; }
    """

    # ✨ 這裡就是接收主程式「乾淨資料禮物」的地方
    def __init__(self, package_data: list = None) -> None:
        super().__init__()
        self.package_data = package_data or []

    def compose(self) -> ComposeResult:
        default_path = os.path.expanduser("~/lpm_packages.txt")
        
        with Vertical(id="export-container"):
            yield Label("📤 匯出系統套件列表", id="export-title")

            with Horizontal(classes="export-row"):
                yield Label("存放位置：", classes="export-label")
                yield Input(value=default_path, placeholder="例如: /home/xier/packages.txt", id="export-path", classes="export-control")
            
            with Horizontal(classes="export-row"):
                yield Label("篩選套件：", classes="export-label")
                yield Input(placeholder="輸入關鍵字 (留空代表全部匯出)...", id="export-filter", classes="export-control")

            with Horizontal(classes="export-checkboxes"):
                yield Checkbox("包含套件管理員", value=True, id="chk-mgr")
                yield Checkbox("包含安裝版本", value=True, id="chk-version")

            yield TextArea("載入預覽中...", id="export-preview", read_only=True)

            with Horizontal(classes="export-btn-box"):
                yield Button("取消", id="export-cancel", variant="error")
                yield Button("確認匯出 🚀", id="export-save", variant="success")

    def on_mount(self) -> None:
        self.update_preview()

    @on(Input.Changed, "#export-filter")
    @on(Checkbox.Changed)
    def handle_changes(self, event) -> None:
        self.update_preview()

    def update_preview(self) -> None:
        """直接使用記憶體裡的乾淨資料模擬樹狀圖，超快！"""
        filter_text = self.query_one("#export-filter").value.strip().lower()
        inc_mgr = self.query_one("#chk-mgr").value
        inc_version = self.query_one("#chk-version").value

        try:
            # 直接過濾主程式傳來的資料
            all_packages = []
            for pkg in self.package_data:
                if filter_text and filter_text not in pkg["name"].lower():
                    continue
                all_packages.append(pkg)

            groups = defaultdict(list)
            for pkg in all_packages:
                parts = pkg["name"].split("-", 1)
                prefix = parts[0]
                groups[prefix].append(pkg)

            preview_lines = []
            count = 0
            for prefix in sorted(groups.keys()):
                if count >= 20: 
                    preview_lines.append("...\n(資料過多，以下省略預覽)")
                    break

                items = sorted(groups[prefix], key=lambda x: x["name"])
                if len(items) == 1:
                    pkg = items[0]
                    line = pkg["name"]
                    if inc_version: line += f" ({pkg['version']})"
                    if inc_mgr: line = f"[{pkg['mgr']}] " + line
                    preview_lines.append(line)
                    count += 1
                else:
                    preview_lines.append(f"📁 {prefix}")
                    count += 1
                    for i, pkg in enumerate(items):
                        if count >= 20: break
                        is_last = (i == len(items) - 1)
                        branch = "└── " if is_last else "├── "
                        suffix = pkg["name"][len(prefix)+1:] if pkg["name"] != prefix else "(核心本體)"
                        line = suffix
                        if inc_version: line += f" ({pkg['version']})"
                        if inc_mgr: line = f" [{pkg['mgr']}] " + line
                        preview_lines.append(f"{branch}{line}")
                        count += 1

            preview_text = "\n".join(preview_lines)
            if not preview_text:
                preview_text = "⚠️ 找不到符合條件的套件"

            self.query_one("#export-preview").text = preview_text

        except Exception as e:
            self.query_one("#export-preview").text = f"無法產生預覽: {e}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-cancel":
            self.dismiss(None)
            return

        if event.button.id == "export-save":
            path = self.query_one("#export-path").value.strip()
            inc_mgr = self.query_one("#chk-mgr").value
            inc_version = self.query_one("#chk-version").value
            filter_text = self.query_one("#export-filter").value.strip().lower()
            
            self.dismiss({
                "path": path,
                "inc_mgr": inc_mgr,
                "inc_version": inc_version,
                "filter_text": filter_text
            })