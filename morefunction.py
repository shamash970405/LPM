# morefunction.py
import os
import re
import asyncio
from textual import on
from collections import defaultdict
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets.option_list import Option
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, OptionList, Input, Select, Button, Checkbox, TextArea, RichLog

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
    """彈出的系統設定視窗，支援多重 AI 選擇、API Token 輸入與 SSH 模式"""
    
    CSS = """
    SettingsScreen { align: center middle; background: rgba(0, 0, 0, 0.7); }
    #settings-container { width: 75; height: auto; background: #1f2335; border: thick #7aa2f7; padding: 1 2; }
    #settings-title { text-align: center; text-style: bold; color: #7aa2f7; margin-bottom: 2; width: 100%; }
    .setting-row { height: auto; margin-bottom: 1; align: left middle; }
    .setting-label { width: 20; content-align: left middle; }
    .setting-control { width: 1fr; }
    .settings-btn-box { height: auto; align: right middle; margin-top: 1; }
    #setting-cancel { margin-right: 2; }
    """

    # ✨ 新增 sys_status 參數來接收系統狀態
    def __init__(self, current_token: str = "", ssh_mode: bool = False, preferred_mgr: str = "apt", sys_status: dict = None) -> None:
        super().__init__()
        self.current_token = current_token
        self.ssh_mode = ssh_mode
        self.preferred_mgr = preferred_mgr
        self.sys_status = sys_status or {} # 預設給個空字典防呆

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("⚙️ 系統設定中心", id="settings-title")

            with Horizontal(classes="setting-row"):
                yield Label("選擇要使用的 AI：", classes="setting-label")
                yield Select(
                    options=[("Gemini", "gemini"), ("DeepSeek", "deepseek"), ("ChatGPT", "chatgpt"), ("Grok", "grok")],
                    prompt="請選擇 AI 引擎", id="setting-ai-model", classes="setting-control"
                )
            
            with Horizontal(classes="setting-row"):
                yield Label("API Token：", classes="setting-label")
                yield Input(value=self.current_token, placeholder="請輸入對應的 API 密鑰...", password=True, id="setting-api-token", classes="setting-control")

            # ✨ 新增：SSH 模式開關
            with Horizontal(classes="setting-row"):
                yield Label("進階選項：", classes="setting-label")
                yield Checkbox("開啟 SSH 內建終端機模式 (解決遠端彈窗問題)", value=self.ssh_mode, id="setting-ssh-mode", classes="setting-control")

            # ✨ 動態生成系統支援的套件管理員清單字典
            mgr_labels = {
                "apt": "APT (Ubuntu/Debian 穩健)",
                "pacman": "Pacman (Arch 預設)",
                "yay": "Yay (AUR 助手)",
                "paru": "Paru (AUR 助手)",
                "dnf": "DNF (Fedora 預設)",
                "zypper": "Zypper (openSUSE 預設)",
                "apk": "APK (Alpine 預設)",
                "snap": "Snap (跨平台/最新)",
                "flatpak": "Flatpak (沙盒/跨平台)",
                "brew": "Homebrew (跨平台)"
            }
            
            # 依據 sys_status 過濾出真的有安裝的
            available_mgrs = []
            for mgr, is_installed in self.sys_status.items():
                if is_installed:
                    label = mgr_labels.get(mgr, mgr.upper())
                    available_mgrs.append((label, mgr))
                    
            if not available_mgrs:
                available_mgrs = [("系統預設", "apt")] # 極端情況防呆

            # 確保目前的偏好值真的存在於可用清單中，否則自動切換到清單第一個
            safe_pref_mgr = self.preferred_mgr if self.preferred_mgr in [m[1] for m in available_mgrs] else available_mgrs[0][1]

            # ✨ 動態下拉選單
            with Horizontal(classes="setting-row"):
                yield Label("偏好安裝來源：", classes="setting-label")
                yield Select(
                    options=available_mgrs,
                    value=safe_pref_mgr,
                    id="setting-pref-mgr", classes="setting-control"
                )

            with Horizontal(classes="settings-btn-box"):
                yield Button("取消", id="setting-cancel", variant="error")
                yield Button("儲存設定 💾", id="setting-save", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setting-cancel":
            self.dismiss(None)
            return

        if event.button.id == "setting-save":
            ai_choice = self.query_one("#setting-ai-model").value
            api_token = self.query_one("#setting-api-token").value
            ssh_mode = self.query_one("#setting-ssh-mode").value # 抓取開關狀態
            pref_mgr = self.query_one("#setting-pref-mgr").value
            
            if not ai_choice or ai_choice == Select.BLANK:
                self.notify("❌ 請先選擇一個 AI 引擎！", severity="error")
                return
            
            self.notify(f"✅ 設定已更新！SSH 模式: {'開啟' if ssh_mode else '關閉'}")
            # 將 ssh_mode 一起打包回傳
            self.dismiss({
                "ai_engine": ai_choice, 
                "api_token": api_token, 
                "ssh_mode": ssh_mode, 
                "preferred_mgr": pref_mgr
            })

# ================= 💻 內建終端機執行跳窗 (SSH 專用) =================
class CommandTerminalScreen(ModalScreen):
    """在 TUI 內部即時顯示執行指令輸出的終端機視窗 (支援密碼與互動輸入)"""
    
    CSS = """
    CommandTerminalScreen { align: center middle; background: rgba(0, 0, 0, 0.8); }
    
    /* ✨ 把整個視窗拉到最大 (90%) */
    #cmd-container { width: 90%; height: 90%; background: #1f2335; border: thick #7aa2f7; padding: 1 2; }
    #cmd-title { text-align: center; text-style: bold; color: #e0af68; margin-bottom: 1; height: auto; }
    
    /* 🚀 關鍵魔法：強制讓預覽框吃掉所有剩餘高度 (1fr) */
    #cmd-log { height: 1fr; border: solid #565f89; background: #1a1b26; margin-bottom: 1; }
    
    /* 🔒 鎖死輸入框與按鈕列的高度，不讓它們作怪 */
    #cmd-input { height: 3; margin-bottom: 1; border: solid #7aa2f7; background: #16161e; }
    .cmd-btn-box { height: 3; align: center middle; }
    """

    def __init__(self, command: str) -> None:
        super().__init__()
        self.command = command
        
    # ... (底下的 compose 與其他函式完全不用動，維持原樣即可) ...

    def compose(self) -> ComposeResult:
        with Vertical(id="cmd-container"):
            yield Label(f"🚀 正在執行: {self.command}", id="cmd-title")
            yield RichLog(id="cmd-log", markup=True, auto_scroll=True)
            
            # ✨ 核心升級：加入一個隱藏輸入內容的對話框，用來送 sudo 密碼或是回覆 [Y/n]
            yield Input(placeholder="若畫面卡住，請在此輸入 sudo 密碼或 y 並按 Enter 繼續...", id="cmd-input", password=True)
            
            with Horizontal(classes="cmd-btn-box"):
                yield Button("請稍候...", id="cmd-close", variant="warning", disabled=True)

    async def on_mount(self) -> None:
        self.query_one("#cmd-input").focus() # 一打開就自動對焦輸入框
        self.run_worker(self.execute_command())

    async def execute_command(self):
        log = self.query_one("#cmd-log")
        btn = self.query_one("#cmd-close")
        
        try:
            import asyncio
            # ✨ 關鍵魔法：把所有的 sudo 偷偷換成 sudo -S
            # -S 參數會強迫 sudo 從標準輸入 (stdin) 讀取密碼，而不是實體螢幕！
            cmd_to_run = self.command.replace("sudo ", "sudo -S ")
            
            self.process = await asyncio.create_subprocess_shell(
                cmd_to_run,
                stdin=asyncio.subprocess.PIPE,  # 🔗 打開標準輸入水管，準備把密碼灌進去
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                log.write(line.decode('utf-8', errors='replace').rstrip())

            await self.process.wait()
            
            if self.process.returncode == 0:
                log.write(f"\n[bold green]✅ 指令執行完畢 (Exit Code: 0)[/bold green]")
            else:
                log.write(f"\n[bold red]❌ 執行發生錯誤 (Exit Code: {self.process.returncode})[/bold red]")
                
        except Exception as e:
            log.write(f"\n[bold red]❌ 無法啟動指令: {str(e)}[/bold red]")

        # 執行完畢後，解鎖關閉按鈕，並把輸入框鎖起來
        btn.disabled = False
        btn.label = "關閉視窗"
        btn.variant = "success"
        self.query_one("#cmd-input").disabled = True

    # ✨ 攔截輸入框的 Enter 提交事件
    @on(Input.Submitted, "#cmd-input")
    async def submit_input(self, event: Input.Submitted) -> None:
        # 確保子行程還活著才寫入資料
        if hasattr(self, "process") and self.process.returncode is None:
            try:
                # 將密碼加上換行符號 (\n) 轉成二進位寫入水管中
                self.process.stdin.write((event.value + "\n").encode())
                await self.process.stdin.drain()
                event.input.value = "" # 送出後立刻清空輸入框，保護密碼
            except Exception:
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cmd-close":
            self.dismiss()
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
# ================= 📥 匯入套件列表跳窗 =================
import os
import re
from textual import on
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, Button, Checkbox, TextArea
from textual.app import ComposeResult

class ImportModal(ModalScreen):
    """匯入套件清單的專屬視窗 (附帶即時預覽與資安警告)"""
    
    CSS = """
    ImportModal { align: center middle; background: rgba(0, 0, 0, 0.7); }
    /* ✨ 調整了跳窗的高度與佈局，讓預覽框有足夠的空間 */
    #import-container { width: 75; height: 35; background: #1f2335; border: thick #9ece6a; padding: 1 2; }
    #import-title { text-align: center; text-style: bold; color: #9ece6a; margin-bottom: 1; width: 100%; }
    .import-row { height: auto; margin-bottom: 1; align: left middle; }
    .import-label { width: 15; content-align: left middle; }
    .import-control { width: 1fr; }
    #import-preview { height: 1fr; border: solid #565f89; background: #1a1b26; color: #a9b1d6; margin-bottom: 1; }
    .import-warning { color: #ff5555; text-style: bold; margin-bottom: 1; text-align: center; background: rgba(255, 85, 85, 0.1); padding: 1; }
    .import-btn-box { height: auto; align: right middle; }
    #import-cancel { margin-right: 2; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="import-container"):
            yield Label("📥 匯入系統套件列表", id="import-title")

            with Horizontal(classes="import-row"):
                yield Label("檔案位置：", classes="import-label")
                # ✨ 移除 value=default_path，讓它預設為空
                yield Input(placeholder="例如: /home/xier/lpm_packages.txt", id="import-path", classes="import-control")
            
            yield Checkbox("略過文件內套件版本 (推薦勾選，避免跨電腦版本衝突)", value=True, id="chk-ignore-version")
            
            # ✨ 新增：佔據剩餘空間的唯讀預覽框
            yield TextArea("請輸入檔案路徑以預覽即將匯入的套件...", id="import-preview", read_only=True)

            # 🚨 資安警告標語
            yield Label("⚠️ 警告：請不要相信他人給的套件列表文件，以免安裝到惡意軟體！", classes="import-warning")

            with Horizontal(classes="import-btn-box"):
                yield Button("取消", id="import-cancel", variant="error")
                yield Button("解析並匯入 🚀", id="import-save", variant="success")

    # ================= ⚡ 即時預覽引擎 =================
    @on(Input.Changed, "#import-path")
    @on(Checkbox.Changed, "#chk-ignore-version")
    def update_preview(self, event=None) -> None:
        path = self.query_one("#import-path").value.strip()
        ignore_ver = self.query_one("#chk-ignore-version").value
        preview_box = self.query_one("#import-preview")

        if not path:
            preview_box.text = "請輸入檔案路徑以預覽即將匯入的套件..."
            return

        if not os.path.exists(path):
            preview_box.text = "⚠️ 找不到檔案，請確認路徑是否正確。"
            return

        if not os.path.isfile(path):
            preview_box.text = "⚠️ 指定的路徑不是一個有效的文字檔。"
            return

        try:
            packages = []
            current_prefix = ""
            
            # 🧠 直接在打字時啟動解碼器，讓使用者看見拆解後的結果
            with open(path, 'r', encoding='utf-8') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith(('hostname:', '匯出時間:', '＝＝＝')):
                        continue
                    
                    if line.startswith('📁'):
                        current_prefix = line.replace('📁', '').strip()
                        continue
                    
                    is_tree_item = '├──' in raw_line or '└──' in raw_line
                    line = line.replace('├── ', '').replace('└── ', '').strip()
                    
                    mgr_match = re.match(r'^\[(.*?)\]\s*(.*)', line)
                    if mgr_match: line = mgr_match.group(2)
                    
                    ver_match = re.search(r'\((.*?)\)$', line)
                    version = None
                    if ver_match:
                        version = ver_match.group(1)
                        line = line[:ver_match.start()].strip()
                    
                    pkg_name = line
                    if is_tree_item and current_prefix:
                        if pkg_name == "(核心本體)": pkg_name = current_prefix
                        else: pkg_name = f"{current_prefix}-{pkg_name}"
                    
                    if not ignore_ver and version:
                        pkg_name = f"{pkg_name}={version}"
                        
                    if pkg_name:
                        packages.append(pkg_name)
                        
            if not packages:
                preview_box.text = "⚠️ 檔案內沒有找到任何有效的套件名稱！請確認檔案格式。"
            else:
                # 把解析成功的陣列變成美美的字串顯示出來
                preview_text = f"✅ 成功解析 {len(packages)} 個套件，即將準備安裝：\n"
                preview_text += "──────────────────────────\n"
                preview_text += "\n".join([f"📦 {p}" for p in packages])
                preview_box.text = preview_text

        except Exception as e:
            preview_box.text = f"❌ 檔案解析發生錯誤：\n{str(e)}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-cancel":
            self.dismiss(None)
            return

        if event.button.id == "import-save":
            path = self.query_one("#import-path").value.strip()
            ignore_version = self.query_one("#chk-ignore-version").value
            
            # ✨ 阻擋惡意送出：如果檔案不存在就不給匯入
            if not os.path.exists(path) or not os.path.isfile(path):
                self.app.notify("❌ 請輸入有效的檔案路徑！", severity="error")
                return
                
            self.dismiss({"path": path, "ignore_version": ignore_version})

# ================= 🔄 系統與套件更新選擇跳窗 =================
class UpdateChoiceModal(ModalScreen):
    """選擇全系統更新或個別套件更新"""
    CSS = """
    UpdateChoiceModal { align: center middle; background: rgba(0, 0, 0, 0.7); }
    #update-choice-container { width: 45; height: auto; background: #1f2335; border: thick #9ece6a; padding: 1; }
    #update-choice-title { text-align: center; text-style: bold; color: #9ece6a; margin-bottom: 1; }
    """
    def compose(self) -> ComposeResult:
        with Vertical(id="update-choice-container"):
            yield Label("🔄 系統與套件更新中心", id="update-choice-title")
            yield OptionList(
                Option("💻 全系統升級與垃圾回收 (推薦)", id="system_update"),
                Option("📦 選擇個別套件更新", id="package_update")
            )
            
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

# ================= 📦 個別套件更新清單跳窗 =================
from textual.widgets import Tree

class PackageUpdateModal(ModalScreen):
    """顯示已安裝套件列表，支援全選與個別勾選更新"""
    CSS = """
    PackageUpdateModal { align: center middle; background: rgba(0, 0, 0, 0.85); }
    #pkg-update-container { width: 75; height: 90%; background: #1f2335; border: thick #7aa2f7; padding: 2 4; }
    #pkg-update-tree { height: 1fr; border: solid #565f89; background: #1a1b26; margin-bottom: 1; margin-top: 1; }
    .pkg-btn-box { height: auto; align: right middle; margin-top: 1; }
    #btn-update-cancel { margin-right: 1; }
    #btn-select-all { margin-right: 1; }
    """
    def __init__(self, package_data):
        super().__init__()
        self.package_data = package_data
        self.all_leaf_nodes = []
        self.is_all_selected = False

    def compose(self) -> ComposeResult:
        with Vertical(id="pkg-update-container"):
            yield Label("📦 [bold #7aa2f7]請勾選要更新的套件[/] (可全選)：", classes="section-title")
            yield Tree("系統已安裝套件", id="pkg-update-tree")
            with Horizontal(classes="pkg-btn-box"):
                yield Button("全選 / 全不選", id="btn-select-all", variant="primary")
                yield Button("取消", id="btn-update-cancel", variant="error")
                yield Button("確認更新 🚀", id="btn-update-confirm", variant="success")

    def on_mount(self):
        tree = self.query_one("#pkg-update-tree", Tree)
        tree.root.expand()
        
        # 🧠 依管理員分組，避免 2000 個套件散成一團
        from collections import defaultdict
        groups = defaultdict(list)
        for pkg in self.package_data:
            groups[pkg["mgr"]].append(pkg["name"])
        
        for mgr in sorted(groups.keys()):
            # 預設先摺疊起來 (expand=False)，才不會一打開視窗就卡死
            mgr_node = tree.root.add(f"📂 {mgr.upper()} 來源", expand=False) 
            for pkg_name in sorted(groups[mgr]):
                leaf = mgr_node.add_leaf(f"[ ] {pkg_name}", data={"mgr": mgr, "name": pkg_name, "selected": False})
                self.all_leaf_nodes.append(leaf)

    @on(Tree.NodeSelected, "#pkg-update-tree")
    def toggle_node(self, event: Tree.NodeSelected):
        node = event.node
        if node.data is not None and "selected" in node.data:
            node.data["selected"] = not node.data["selected"]
            if node.data["selected"]:
                node.set_label(f"[bold #9ece6a][X] {node.data['name']}[/]")
            else:
                node.set_label(f"[ ] {node.data['name']}")

    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed):
        if event.button.id == "btn-update-cancel":
            self.dismiss(None)
        
        elif event.button.id == "btn-select-all":
            self.is_all_selected = not self.is_all_selected
            for leaf in self.all_leaf_nodes:
                leaf.data["selected"] = self.is_all_selected
                if self.is_all_selected:
                    leaf.set_label(f"[bold #9ece6a][X] {leaf.data['name']}[/]")
                else:
                    leaf.set_label(f"[ ] {leaf.data['name']}")
                    
        elif event.button.id == "btn-update-confirm":
            selected = {}
            for leaf in self.all_leaf_nodes:
                if leaf.data.get("selected"):
                    selected.setdefault(leaf.data["mgr"], []).append(leaf.data["name"])
            self.dismiss(selected)