import os
import shutil
import asyncio
import subprocess
from google import genai
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from theme import ThemeManager
from textual.widgets import Header, Footer, Input, Markdown, Label, DataTable, OptionList, Button 
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from morefunction import ThemeMenuScreen

# ================= 1. Gemini AI 模組 =================
class GeminiExplainer:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    def refresh_client(self, new_token: str) -> None:
        if new_token:
            self.client = genai.Client(api_key=new_token)
        else:
            self.client = None

    async def ask_gemini(self, package_name: str) -> str:
        if not self.client:
            return "⚠️ 未偵測到 `GEMINI_API_KEY` 環境變數。"
        prompt = f"請用繁體中文（台灣習慣用語）白話文解釋 Linux 套件 '{package_name}' 的用途，並列出 2 個核心特點。總字數限制在 80 字內。"
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            )
            return response.text
        except Exception as e:
            return f"❌ AI 查詢失敗: {str(e)}"

# ================= 2. ESC 按鍵彈出的控制選單 =================
class EscMenuScreen(ModalScreen):
    """按 ESC 鍵彈出的系統選單"""
    
    CSS = """
    EscMenuScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #esc-container {
        width: 45;
        height: auto;
        background: #1f2335;
        border: thick #ff5555;
        padding: 1;
    }
    #esc-title {
        text-align: center;
        text-style: bold;
        color: #ff9e64;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="esc-container"):
            yield Label("系統控制選單", id="esc-title")
            yield OptionList(
                Option("更改介面主題", id="change_theme"),
                Option("⚙️ 系統設定 (API Token)", id="open_settings"),  # 🎯 就是缺了這一行！把它補上去！
                Option("結束並退出程式", id="quit")
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

class PackageTable(DataTable):
    """專屬綁定 Enter 鍵的表格，徹底解決與其他輸入框的按鍵衝突"""
    BINDINGS = [
        ("enter", "uninstall", "Enter 刪除")
    ]
# ================= 3. 主介面模組 =================
class LinuxPackageManagerApp(App):
    BINDINGS = [
        ("Q", "quit", "系統離開"),
        ("f1", "focus_search", "搜尋選中套件"),
        ("escape", "open_esc_menu", "系統選單"),
        ("ctrl+left", "resize_left_pane(-2)", "縮小左欄"),
        ("ctrl+right", "resize_left_pane(2)", "放大左欄"),
        ("ctrl+up", "resize_bottom_pane(1)", "放大下欄"),
        ("ctrl+down", "resize_bottom_pane(-1)", "縮小下欄"),
    ]
    
    CSS = """
    Screen { background: #1a1b26; layout: vertical; }
    .top-box { height: 40%; layout: horizontal; border-bottom: solid #3b4261; }
    .left-pane { width: 40%; border-right: solid #3b4261; padding: 1; layout: vertical; }
    .right-pane { width: 1fr; padding: 1; background: #1f2335; }
    .bottom-pane { height: 60%; padding: 1; background: #16161e; }
    .status-label { color: #7aa2f7; }
    .disk-label { color: #e0af68; margin-top: 1; }
    .section-title { color: #bb9af3; text-style: bold; margin-bottom: 1; }
    #pkg-input { margin-bottom: 1; }
    DataTable { height: 1fr; border: solid #292e42; }
    
    /* 🎯 讓純文字標籤在滑鼠移上去時有手勢提示，並增加點擊回饋感 */
    .status-label:hover { color: #bb9af3; text-style: underline; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.ENABLE_COMMAND_PALETTE = False
        
        # 🎨 初始化主題管理與 AI 模組
        from theme import ThemeManager 
        self.theme_mgr = ThemeManager("tokyonight")
        self.ai = GeminiExplainer()
        self.current_gemini_token = os.environ.get("GEMINI_API_KEY", "")

        # 📦 核心資料庫暫存區與排序狀態
        self.raw_packages = []
        self.installed_packages = []
        self.current_sort = "name"
        self.sort_descending = False
        self.current_priority_manager = "apt"  # 🎯 預設優先置頂 Ubuntu APT

        # 全自動硬體環境偵測
        # 🌍 終極全自動硬體環境偵測
        self.sys_status = {
            "pacman": shutil.which("pacman") is not None,  # Arch
            "yay": shutil.which("yay") is not None,        # Arch (AUR)
            "paru": shutil.which("paru") is not None,      # Arch (AUR 另一主流)
            "apt": shutil.which("apt") is not None,        # Ubuntu/Debian
            "dnf": shutil.which("dnf") is not None,        # Fedora/RHEL
            "zypper": shutil.which("zypper") is not None,  # openSUSE
            "apk": shutil.which("apk") is not None,        # Alpine Linux
            "emerge": shutil.which("emerge") is not None,  # Gentoo
            "xbps": shutil.which("xbps-install") is not None, # Void Linux
            "snap": shutil.which("snap") is not None,      # 跨平台沙盒
            "flatpak": shutil.which("flatpak") is not None,# 跨平台沙盒
            "brew": shutil.which("brew") is not None       # Homebrew (Linuxbrew)
        }
        self.left_pane_width = 40
        self.bottom_pane_height = 60
        self.ai_task = None

   # 🎯 物理分流：完全不使用 RowSelected 事件，改用精準的鍵盤事件
    def on_key(self, event: __import__("textual").events.Key) -> None:

        if event.key == 'escape':
            return

        # 🚪 經典 Linux 快捷鍵：按 Q 退出程式
        if event.key.lower() == "q":
            # 🛡️ 焦點檢查：如果游標「不在」搜尋輸入框裡，才執行退出
            if not (self.focused and getattr(self.focused, "id", None) == "pkg-input"):
                self.exit()

        # 🔑 當使用者按下實體 Enter 鍵時！
        if event.key == "enter":
            
            # 🛡️ 焦點防呆攔截：如果游標停在搜尋框，立刻中斷，絕對不觸發卸載！
            if self.focused and getattr(self.focused, "id", None) == "pkg-input":
                return

            # 🛡️ 防呆雷達：如果在設定視窗裡找不到表格，就「安靜跳出」不要噴錯！
            try:
                table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
            except Exception:
                return # 找不到表格代表正在輸入金鑰或搜尋，直接放行！

            # 🎯 抓取目前游標停留在哪一行
            if table.cursor_coordinate:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                row_data = table.get_row(row_key)
                
                import re
                def clean_markup(text_str: str) -> str:
                    return re.sub(r'\[.*?\]', '', str(text_str)).strip()
                
                raw_mgr = clean_markup(row_data[0])
                package_name = clean_markup(row_data[1])
                
                self.notify(f"🚀 鍵盤觸發: 準備解除安裝 {raw_mgr.upper()} 套件: {package_name}...")
                
                # 🛠️ 根據來源判定刪除指令 (12 大通路終極支援)
                if raw_mgr == "pacman": uninstall_cmd = f"sudo pacman -Rns {package_name}"
                elif raw_mgr == "yay": uninstall_cmd = f"yay -Rns {package_name}"
                elif raw_mgr == "paru": uninstall_cmd = f"paru -Rns {package_name}"
                elif raw_mgr == "apt": uninstall_cmd = f"sudo apt purge -y {package_name}"
                elif raw_mgr == "dnf": uninstall_cmd = f"sudo dnf remove -y {package_name}"
                elif raw_mgr == "zypper": uninstall_cmd = f"sudo zypper remove -y {package_name}"
                elif raw_mgr == "apk": uninstall_cmd = f"sudo apk del {package_name}"
                elif raw_mgr == "emerge": uninstall_cmd = f"sudo emerge --deselect {package_name}"
                elif raw_mgr == "xbps": uninstall_cmd = f"sudo xbps-remove -R {package_name}"
                elif raw_mgr == "snap": uninstall_cmd = f"sudo snap remove {package_name}"
                elif raw_mgr == "flatpak": uninstall_cmd = f"flatpak uninstall -y {package_name}"
                elif raw_mgr == "brew": uninstall_cmd = f"brew uninstall {package_name}"
                else: return
                
                import shutil, subprocess, asyncio
                
                # 🚀 自動偵測桌面環境可用的終端機
                terminal_cmd = None
                for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                    if shutil.which(term) is not None:
                        terminal_cmd = term
                        break
                
                # 🛡️ 物理喚醒外部終端機執行卸載，並套用錯誤防護罩
                try:
                    if terminal_cmd == "gnome-terminal":
                        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"{uninstall_cmd}; read -p '執行完畢，按 [Enter] 關閉視窗...'"])
                    elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                        subprocess.Popen([terminal_cmd, "-e", f"bash -c '{uninstall_cmd}; read -p \"執行完畢，按 [Enter] 關閉視窗...\"'"])
                    else:
                        subprocess.Popen(["bash", "-c", uninstall_cmd])
                except Exception as e:
                    self.notify(f"❌ 啟動卸載程序失敗: {str(e)}", severity="error")

                # ⏳ 延遲刷新數據管線
                async def delayed_refresh():
                    await asyncio.sleep(5) # 給系統 5 秒卸載時間
                    try:
                        await self.load_installed_packages()
                        self.notify("已安裝套件清單！")
                    except Exception: pass
                
                asyncio.create_task(delayed_refresh())

    def get_os_name(self) -> str:
        """讀取系統 /etc/os-release 來獲取準確的 Linux 發行版名稱"""
        try:
            import platform
            if hasattr(platform, 'freedesktop_os_release'):
                return platform.freedesktop_os_release().get('PRETTY_NAME', 'Linux')
        except Exception: pass
        
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=")[1].strip().strip('"')
        except Exception: pass
        return "未知 Linux 發行版"


    def parse_size_to_bytes(self, size_str: str) -> float:
        clean_str = size_str.replace("[bold #e0af68]", "").replace("[/bold #e0af68]", "")
        clean_str = clean_str.replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip().lower()
        if "未知" in clean_str or not clean_str: return 0.0
        try:
            parts = clean_str.split()
            number = float(parts[0])
            unit = parts[1] if len(parts) > 1 else ""
            if "tb" in unit or "t" == unit: return number * (1024 ** 4)
            elif "gb" in unit or "g" == unit: return number * (1024 ** 3)
            elif "mb" in unit or "m" == unit: return number * (1024 ** 2)
            elif "kb" in unit or "k" in unit: return number * 1024
            return number
        except Exception: return 0.0

    def get_disk_info(self) -> str:
        try:
            total, used, free = shutil.disk_usage("/")
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            free_gb = free / (1024 ** 3)
            used_percent = (used / total) * 100
            bar_length = 20
            filled_length = int(round(bar_length * used / float(total)))
            bar_color = "red" if used_percent > 85 else ("yellow" if used_percent > 60 else "green")
            bar = f"[{bar_color}]" + "█" * filled_length + f"[/{bar_color}]" + "░" * (bar_length - filled_length)
            return (
                f"💾 系統容量狀態 (根目錄 / block)：\n"
                f"  {bar}  {used_percent:.1f}%\n"
                f"  - 總大小: {total_gb:.1f} GB\n"
                f"  - 已使用: {used_gb:.1f} GB\n"
                f"  - 剩餘可用: [bold green]{free_gb:.1f} GB[/bold green]"
            )
        except Exception: return "💾 系統容量狀態: 無法讀取"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # 📦 上半部：左右兩欄並排的水平容器
        with Horizontal(classes="top-box", id="top-box"):
            
            # ⬅️ 左欄：系統狀態與硬碟資訊
            with Vertical(classes="left-pane", id="left-pane"):
                yield Label("🔍 系統環境偵測：", classes="section-title")
                yield Label(f"  發行版：[bold #9ece6a]{self.get_os_name()}[/]", classes="status-label")
                yield Label("  套件管理員：", classes="status-label")
                
                # 這裡只預留標籤位置，讓底下的 load_installed_packages 去更新數字
                for mgr, avail in self.sys_status.items():
                    if avail:
                        yield Label(f"   - {mgr} (計算中...)", id=f"lbl-{mgr}", classes="status-label")
                
                yield Label(self.get_disk_info(), classes="disk-label")
            
            # ➡️ 右欄：Gemini AI 查詢面板 (就是你剛剛不小心弄不見的這塊！)
            with Vertical(classes="right-pane"):
                yield Label("線上Gemini查詢：", classes="section-title")
                yield Input(placeholder="在此輸入套件名稱", id="pkg-input")
                yield Markdown("等待輸入中...", id="ai-output")
                
        # 📦 下半部：套件表格
        with Vertical(classes="bottom-pane", id="bottom-pane"):
            yield Label("套件列表", classes="section-title")
            
            # 確保你使用的是 DataTable (如果你先前改成 PackageTable，這裡請維持 PackageTable)
            yield DataTable(id="installed-packages-table")
            
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        
        # 🎯 只保留合法的選取模式設定
        table.click_to_select = True
        table.cursor_type = "row"
        
        import asyncio
        asyncio.create_task(self.load_installed_packages())

    # 鼠标隐形点击术事件接收器
    def on_click(self, event: __import__("textual").events.Click) -> None:
        # 🎯 透過 event.control 安全撈取觸發點擊的組件
        if hasattr(event, "control") and event.control:
            target_id = event.control.idq
        else:
            return  # 如果點到空白處、沒有組件控制權，直接安全跳出
        
        # 🎯 根據點擊的標籤 id，精準切換置頂來源
        # 🎯 根據點擊的標籤 id，精準切換置頂來源
        if target_id == "lbl-pacman": self.current_priority_manager = "pacman"
        elif target_id == "lbl-yay": self.current_priority_manager = "yay"
        elif target_id == "lbl-paru": self.current_priority_manager = "paru"
        elif target_id == "lbl-apt": self.current_priority_manager = "apt"
        elif target_id == "lbl-dnf": self.current_priority_manager = "dnf"
        elif target_id == "lbl-zypper": self.current_priority_manager = "zypper"
        elif target_id == "lbl-apk": self.current_priority_manager = "apk"
        elif target_id == "lbl-emerge": self.current_priority_manager = "emerge"
        elif target_id == "lbl-xbps": self.current_priority_manager = "xbps"
        elif target_id == "lbl-snap": self.current_priority_manager = "snap"
        elif target_id == "lbl-flatpak": self.current_priority_manager = "flatpak"
        elif target_id == "lbl-brew": self.current_priority_manager = "brew"
        else: return
        
        self.notify(f"🎯 已將優先套件庫切換至：{self.current_priority_manager}")
            
        # 🚀 帶著搜尋框關鍵字，滿血洗牌刷新 5 欄位表格！
        current_keyword = self.query_one("#pkg-input").value if hasattr(self, 'query_one') else ""
        self.refresh_table_view(highlight_keyword=current_keyword, sort_by=self.current_sort)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if event.column_index == 1:
            self.current_sort = "name"
        elif event.column_index == 2:
            self.current_sort = "group"
        elif event.column_index == 4:
            self.current_sort = "size"
        else:
            return

        self.sort_descending = not self.sort_descending
        self.refresh_table_view(sort_by=self.current_sort)

    async def load_installed_packages(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            table.clear()
        except Exception: pass
        
        self.raw_packages = []
        tasks = []
        if self.sys_status["pacman"]: tasks.append(self._scan_pacman())
        if self.sys_status["apt"]: tasks.append(self._scan_apt())
        if self.sys_status["snap"]: tasks.append(self._scan_snap())

        if tasks:
            await asyncio.gather(*tasks)

        # 🎯 這裡才是更新標籤文字的正確位置！
        for mgr, avail in self.sys_status.items():
            if avail:
                # 算出這個套件管理員的總套件數
                mgr_count = sum(1 for p in self.raw_packages if p.get("manager") == mgr)
                try:
                    lbl = self.query_one(f"#lbl-{mgr}")
                    lbl.update(f"   - {mgr} [bold #e0af68]({mgr_count})[/]")
                except Exception as e:
                    self.notify(f"⚠️ {mgr} 標籤更新失敗: {str(e)}", severity="warning")

        self.refresh_table_view()

    async def _scan_pacman(self):
        try:
            process = await asyncio.create_subprocess_exec("pacman", "-Qi", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                package_blocks = stdout.decode().strip().split("\n\n")
                for block in package_blocks:
                    name, version, size = None, None, "未知"
                    for line in block.split("\n"):
                        if "名稱" in line or "Name" in line: name = line.split(":", 1)[1].strip() if ":" in line else name
                        elif "版本" in line or "Version" in line: version = line.split(":", 1)[1].strip() if ":" in line else version
                        elif "大小" in line or "Size" in line: size = line.split(":", 1)[1].strip() if ":" in line else size
                    if name and version:
                        display_size = size.replace("KiB", "KB").replace("MiB", "MB").replace("GiB", "GB").replace("TiB", "TB")
                        self.raw_packages.append({"manager": "pacman", "name": name, "version": version, "size": display_size})
        except Exception: pass

    async def _scan_apt(self):
        try:
            process = await asyncio.create_subprocess_exec(
                "dpkg-query", "-W", "-f=${Status}\t${Package}\t${Version}\t${Installed-Size}\n",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                for line in stdout.decode().strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 4 and "install ok installed" in parts[0]:
                        name, version, raw_size = parts[1], parts[2], parts[3].strip()
                        if raw_size and raw_size.isdigit():
                            size_kb = float(raw_size)
                            display_size = f"{size_kb / 1024:.2f} MB" if size_kb > 1024 else f"{size_kb:.2f} KB"
                        else: display_size = "未知"
                        self.raw_packages.append({"manager": "apt", "name": name, "version": version, "size": display_size})
        except Exception: pass

    async def _scan_snap(self):
        try:
            process = await asyncio.create_subprocess_exec("snap", "list", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        version = parts[1]
                        self.raw_packages.append({"manager": "snap", "name": name, "version": version, "size": "沙盒管理"})
        except Exception: pass

    def refresh_table_view(self, search_text: str = "", sort_by: str = "size") -> None:
        try:
            table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
        except Exception:
            return

        # 1. 每次刷新前，先清空整張表格與舊欄位
        table.clear(columns=True)
        
        # 2. 重新建立你漂亮的標題欄位
        table.add_column("[bold #7aa2f7]來源[/]", width=8)
        table.add_column("[bold #7aa2f7]套件名稱[/]", width=22)
        table.add_column("[bold #e0af68]應用群組[/]", width=15)
        table.add_column("[bold #7aa2f7]目前版本[/]", width=22)
        table.add_column("[bold #7aa2f7]佔用容量[/]", width=12)

        # 3. 準備搜尋字串 (轉小寫方便比對)
        search_lower = search_text.lower()
        packages_source = self.raw_packages if hasattr(self, "raw_packages") and self.raw_packages else []
        packages_source = self.raw_packages if hasattr(self, "raw_packages") and self.raw_packages else []
        filtered = []
        for pkg in packages_source:
            if search_lower and search_lower not in str(pkg.get("name", "")).lower():
                continue
            filtered.append(pkg)
    
        def sort_key(x):
            is_priority = 1 if x.get("manager") == self.current_priority_manager else 0
            current_sort_target = self.current_sort if hasattr(self, 'current_sort') else sort_by
            if current_sort_target == "size":
                secondary = self.parse_size_to_bytes(x.get("size", ""))
            elif current_sort_target == "group":
                secondary = x.get("group", "system").lower()
            else:
                secondary = x.get("name", "").lower()
            return (is_priority, secondary)

        filtered.sort(key=sort_key, reverse=self.sort_descending)

        # 4. 畫出符合條件的套件
        for pkg in filtered:
            # 取出變數 (加上預設值防呆)
            pkg_manager = pkg.get("manager", "unknown")
            pkg_name = pkg.get("name", "unknown")
            pkg_version = pkg.get("version", "unknown")
            pkg_size = pkg.get("size", "N/A")
            
            # 🧠 應用群組智能分類 (保留你超棒的分類邏輯)
            app_group = pkg.get("group", "System")
            if "gnome" in pkg_name.lower() or "gtk" in pkg_name.lower():
                app_group = "GNOME"
            elif "kde" in pkg_name.lower() or "qt" in pkg_name.lower():
                app_group = "KDE"
            elif pkg_name in ["python3", "gcc", "git", "make"]:
                app_group = "Development"

            # 🎨 把資料畫上去，並套用專屬的橘色與綠色標籤！
            table.add_row(
                f"[bold #e0af68]{pkg_manager}[/]",   # 🟠 來源：橘黃色
                pkg_name,                            # ⚪ 名稱：預設顏色
                f"[bold #9ece6a]{app_group}[/]",     # 🟢 群組：薄荷綠色
                pkg_version,                         # ⚪ 版本：預設顏色
                f"[bold #e0af68]{pkg_size}[/]"       # 🟠 容量：橘黃色
            )

        for p in filtered:
            pkg_manager = p.get("manager", "unknown")
            pkg_name = p.get("name", "unknown")
            pkg_version = p.get("version", "unknown")
            pkg_size = p.get("size", "N/A")
            
            app_group = p.get("group", "System")
            if "gnome" in pkg_name.lower() or "gtk" in pkg_name.lower():
                app_group = "GNOME"
            elif "kde" in pkg_name.lower() or "qt" in pkg_name.lower():
                app_group = "KDE"
            elif pkg_name in ["python3", "gcc", "git", "make"]:
                app_group = "Development"

            table.add_row(
                f"[bold #e0af68]{pkg_manager}[/]",
                pkg_name,
                f"[bold #9ece6a]{app_group}[/]",
                pkg_version,
                f"[bold #e0af68]{pkg_size}[/]"
            )

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            row_data = table.get_row(event.row_key)
            import re
            def clean_markup(text_str: str) -> str:
                return re.sub(r'\[\/?[a-zA-Z0-9#\s_@-]+\]', '', text_str).strip()
            
            package_name = clean_markup(str(row_data[1]))
            markdown_widget = self.query_one("#ai-output", Markdown)
            markdown_widget.update(f"⏳ 等待游標停駐以分析 `{package_name}`...")

            # 🛡️ 防抖機制 (Debounce)：如果前一個計時器還在跑，直接取消上一次的 API 呼叫！
            if self.ai_task:
                self.ai_task.cancel()

            # 建立一個新的延遲執行任務
            async def delayed_ai_request(pkg_name, widget):
                try:
                    await asyncio.sleep(0.6)  # ⏱️ 給予 0.6 秒的冷卻判定時間
                    widget.update(f"⏳ 正在為您通靈已安裝的 `{pkg_name}`...")
                    await self.update_ai_pane(pkg_name, widget)
                except asyncio.CancelledError:
                    pass # 任務被取消（因為游標又移走了），安靜退出不噴錯

            # 把這個新任務派發下去，並記錄在 self.ai_task
            self.ai_task = asyncio.create_task(delayed_ai_request(package_name, markdown_widget))

        except Exception: 
            pass
    
    async def update_ai_pane(self, package_name, widget):
        ai_response = await self.ai.ask_gemini(package_name)
        widget.update(ai_response)

    async def on_input_changed(self, event: __import__("textual").widgets.Input.Changed) -> None:
        
        # 確保觸發的是我們右上角的搜尋框
        if event.input.id != "pkg-input":
            return

        search_text = event.value.strip()

        # 🛑 防抖核心 1：如果之前有正在「倒數」的查詢任務，立刻取消它！
        # (代表使用者在 1 秒內又多打了字，所以舊的查詢作廢)
        if self.ai_task is not None:
            self.ai_task.cancel()

        # 如果使用者把輸入框清空了，就把右邊的 AI 面板恢復成預設狀態，然後跳出
        if not search_text:
            try:
                self.query_one("#ai-output").update("等待輸入中...")
                self.refresh_table_view("") # 🎯 傳入空字串，恢復顯示所有套件
            except Exception: pass
            return

        # ⏳ 防抖核心 2：定義一個新的延遲查詢任務
        async def delayed_search():
            try:
                # 讓程式先「睡」1 秒鐘 (1.0 秒)
                await asyncio.sleep(1.0)
                self.notify(f"🔍 自動觸發查詢：{search_text}")
                
                # 1️⃣ 更新右邊的 AI 面板狀態
                try:
                    ai_panel = self.query_one("#ai-output")
                    ai_panel.update(f"⏳ 正在幫您通靈 `{search_text}` 的資訊...")
                except Exception: pass
                self.refresh_table_view(search_text)

                # 2️⃣ 在左下角表格中自動尋找並「高亮定位」
                try:
                    table = self.query_one("#installed-packages-table")
                    # 取得目前表格中所有的 row key
                    for row_key in table.rows:
                        row_data = table.get_row(row_key)
                        # 假設套件名稱在第二個欄位 (index 1)
                        if search_text.lower() in str(row_data[1]).lower():
                            # 算出這個 row 的 index 並移動游標過去 (帶有滑動動畫！)
                            row_index = table.get_row_index(row_key)
                            table.move_cursor(row=row_index, animate=True)
                            break # 找到第一個就停止尋找
                except Exception as e: pass

                # 3️⃣ 呼叫你原本寫好的 Gemini API 函式！
                # ⚠️ 這裡非常重要：請把 `your_gemini_function` 換成你程式裡真正用來呼叫 AI 的那個函式名稱！
                # 例如： await self.get_gemini_explanation(search_text)
                
                # ⬆️ --------------------------------------------- ⬆️

            except asyncio.CancelledError:
                pass

        # 🚀 防抖核心 3：發射這個新的倒數任務，並把它存進 self.ai_task 變數裡
        import asyncio
        self.ai_task = asyncio.create_task(delayed_search())

    def action_resize_left_pane(self, delta: int) -> None:
        self.left_pane_width = max(20, min(70, self.left_pane_width + delta))
        self.query_one("#left-pane").styles.width = f"{self.left_pane_width}%"

    def action_resize_bottom_pane(self, delta: int) -> None:
        self.bottom_pane_height = max(20, min(80, self.bottom_pane_height + delta))
        self.query_one("#bottom-pane").styles.height = f"{self.bottom_pane_height}%"
        self.query_one("#top-box").styles.height = f"{100 - self.bottom_pane_height}%"

    def action_focus_search(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row_data = table.get_row(row_key)
            package_name = row_data[1].replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip()
            search_input = self.query_one("#pkg-input", Input)
            search_input.value = package_name
            search_input.focus()
            self.refresh_table_view(highlight_keyword=package_name)
            self.notify(f"🔍 已自動鎖定並搜尋：{package_name}")
        except Exception:
            self.query_one("#pkg-input", Input).focus()

    def action_open_esc_menu(self) -> None:
        def handle_esc_callback(action: str) -> None:
            if action == "change_theme":
                def apply_theme_callback(theme_name: str) -> None:
                    if theme_name:
                        try:
                            self.theme_mgr.change_theme(theme_name)
                            self.app.css = self.theme_mgr.get_css()
                            self.refresh()
                            self.notify(f"🎨 佈景主題已成功切換至：{theme_name.upper()}")
                        except Exception as e:
                            self.notify(f"⚠️ 主題套用失敗：{str(e)}", severity="error")
                try:
                    self.push_screen(ThemeMenuScreen(), apply_theme_callback)
                except Exception as e:
                    self.notify(f"⚠️ 無法加載主題選單：{str(e)}", severity="error")
                    
            elif action == "open_settings":
                # 🚀 效率核心：精準引入步驟，確保 SettingsScreen 類別絕對被正確呼叫
                from morefunction import SettingsScreen
                
                def apply_settings_callback(saved_token: str) -> None:
                    if saved_token is not None:  # 使用者按了儲存
                        self.current_gemini_token = saved_token
                        self.ai.refresh_client(saved_token)  # 重新初始化 AI 大腦
                        if saved_token:
                            self.notify("⚙️ Gemini API 金鑰儲存成功，AI 功能已全面上線！")
                        else:
                            self.notify("⚠️ 金鑰已清空，AI 解說功能將暫時關閉", severity="warning")

                # 物理彈出輸入框視窗
                self.push_screen(SettingsScreen(self.current_gemini_token), apply_settings_callback)

            elif action == "quit":
                self.exit()
                
        self.push_screen(EscMenuScreen(), handle_esc_callback)

    def action_uninstall(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            
            # 🛡️ 最終防線：確認表格真的有獲得焦點才執行，保護其他輸入框
            if not table.has_focus:
                return

            if table.cursor_coordinate:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                row_data = table.get_row(row_key)
                
                import re
                def clean_markup(text_str: str) -> str:
                    return re.sub(r'\[.*?\]', '', str(text_str)).strip()
                
                raw_mgr = clean_markup(row_data[0])
                package_name = clean_markup(row_data[1])
                
                self.notify(f"🗑️ 準備解除安裝 {raw_mgr.upper()} 套件：{package_name}...")
                
                if raw_mgr == "pacman": uninstall_cmd = f"sudo pacman -Rns {package_name}"
                elif raw_mgr == "apt": uninstall_cmd = f"sudo apt purge -y {package_name}"
                elif raw_mgr == "snap": uninstall_cmd = f"sudo snap remove {package_name}"
                else: return

                import shutil, subprocess, asyncio
                terminal_cmd = None
                for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                    if shutil.which(term) is not None:
                        terminal_cmd = term
                        break

                if terminal_cmd == "gnome-terminal":
                    subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"{uninstall_cmd}; read -p '執行完畢，按 [Enter] 關閉視窗... '"])
                elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                    subprocess.Popen([terminal_cmd, "-e", f"bash -c '{uninstall_cmd}; read -p \"執行完畢，按 [Enter] 關閉視窗... \"'"])
                else:
                    subprocess.Popen(["bash", "-c", uninstall_cmd])

                async def delayed_refresh():
                    await asyncio.sleep(5)
                    try:
                        await self.load_installed_packages()
                        self.notify("🔄 已自動為您更新全通路套件清單！")
                    except Exception: pass
                asyncio.create_task(delayed_refresh())

        except Exception:
            pass # 找不到表格時（例如正在子視窗）安全靜默跳出，不拋出紅字   

if __name__ == "__main__":
    app = LinuxPackageManagerApp()
    app.run()