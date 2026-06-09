import os
import shutil
import asyncio
import subprocess
from google import genai
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Markdown, Label, DataTable, OptionList
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from morefunction import ThemeMenuScreen

# ================= 1. Gemini AI 模組 =================
class GeminiExplainer:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

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
                Option("結束並退出程式", id="quit")
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

# ================= 3. 主介面模組 =================
class LinuxPackageManagerApp(App):
    BINDINGS = [
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
    .left-pane { width: 40%; border-right: solid #3b4261; padding: 1; }
    .right-pane { width: 1fr; padding: 1; background: #1f2335; }
    .bottom-pane { height: 60%; padding: 1; background: #16161e; }
    .status-label { color: #7aa2f7; }
    .disk-label { color: #e0af68; margin-top: 1; }
    .section-title { color: #bb9af3; text-style: bold; margin-bottom: 1; }
    #pkg-input { margin-bottom: 1; }
    DataTable { height: 1fr; border: solid #292e42; }
    """

    def __init__(self):
        super().__init__()
        self.ENABLE_COMMAND_PALETTE = False
        
        # 💡 ✨ 就是漏了這行！請把它補上去，把 AI 通靈模組綁定回主程式
        self.ai = GeminiExplainer()

        # 全自動硬體環境偵測
        self.sys_status = {
            "pacman": shutil.which("pacman") is not None,
            "apt": shutil.which("apt") is not None,
            "snap": shutil.which("snap") is not None
        }
        self.left_pane_width = 40
        self.left_pane_width = 40
        self.bottom_pane_height = 60
        self.sort_descending = True  # 保留你原本的變數
        self.current_sort_by = "size" # 預設依大小排序
        self.raw_packages = []
        
        # 🔄 就在這裡加！新增當前優先置頂的套件來源管理員（None 代表預設不置頂）
        self.current_priority_manager = None

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
                f"💾 系統容量狀態 (根目錄 /)：\n"
                f"  {bar}  {used_percent:.1f}%\n"
                f"  - 總大小: {total_gb:.1f} GB\n"
                f"  - 已使用: {used_gb:.1f} GB\n"
                f"  - 剩餘可用: [bold green]{free_gb:.1f} GB[/bold green]"
            )
        except Exception: return "💾 系統容量狀態: 無法讀取"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(classes="top-box", id="top-box"):
            with Vertical(classes="left-pane", id="left-pane"):
                yield Label("🔍 系統環境偵測：", classes="section-title")
                status_text = "\n".join(f"  - {mgr}: {'✅ 可用' if avail else '❌ 未安裝'}" for mgr, avail in self.sys_status.items())
                yield Label(status_text, classes="status-label")
                yield Label(self.get_disk_info(), classes="disk-label")
            with Vertical(classes="right-pane"):
                yield Label("🤖 Gemini AI 智慧解說與查詢：", classes="section-title")
                yield Input(placeholder="在此輸入套件名稱，下方將自動高亮定位...", id="pkg-input")
                yield Markdown("等待輸入中...", id="ai-output")
        with Vertical(classes="bottom-pane", id="bottom-pane"):
            yield Label("📦 全通路已安裝套件 (點擊欄位切換排序)：", classes="section-title")
            yield DataTable(id="installed-packages-table")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.cursor_type = "row"
        
        # 🔒 ✨ 終極防誤觸黑魔法：
        # 將 DataTable 的點擊切換成「必須雙擊（Double Click）或按 Enter」才觸發 Selected 事件
        table.click_to_select = False 
        
        table.add_column("來源", width=12)
        table.add_column("套件名稱", width=40)
        table.add_column("目前版本", width=25)
        table.add_column("佔用容量", width=18)
        asyncio.create_task(self.load_installed_packages())

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        header_text = str(event.label).lower().strip()
        
        if header_text in ["來源", "manager"]:
            # 🔄 來源按鈕點擊：在目前系統可用的包管理員 (True) 之間輪播洗牌！
            available_managers = [mgr for mgr, avail in self.sys_status.items() if avail]
            
            if not available_managers:
                return
                
            if self.current_priority_manager not in available_managers:
                self.current_priority_manager = available_managers[0]
            else:
                curr_idx = available_managers.index(self.current_priority_manager)
                next_idx = curr_idx + 1
                if next_idx >= len(available_managers):
                    # 如果已經輪播完一圈，可以選擇設回 None (取消置頂) 或是回到第一個
                    # 這裡設定回到第一個，讓你能源源不絕切換
                    self.current_priority_manager = available_managers[0]
                else:
                    self.current_priority_manager = available_managers[next_idx]
            
            self.notify(f"🔄 LPM 排序洗牌：目前優先置頂 [bold #e0af68]{self.current_priority_manager}[/] 套件")
            
        elif header_text in ["套件名稱", "name"]:
            self.current_sort_by = "name"
            self.sort_descending = not self.sort_descending
        elif header_text in ["佔用容量", "size", "目前版本", "version"]:
            self.current_sort_by = "size"
            self.sort_descending = not self.sort_descending
            
        self.refresh_table_view(sort_by=self.current_sort_by)

    async def load_installed_packages(self) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.clear()
        self.raw_packages = []

        tasks = []
        if self.sys_status["pacman"]: tasks.append(self._scan_pacman())
        if self.sys_status["apt"]: tasks.append(self._scan_apt())
        if self.sys_status["snap"]: tasks.append(self._scan_snap())

        if tasks:
            await asyncio.gather(*tasks)

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

    def refresh_table_view(self, highlight_keyword: str = "", sort_by: str = "size") -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.clear()
        
        filtered = []
        kw = highlight_keyword.lower().strip()
        for p in self.raw_packages:
            if not kw or kw in p.get("name", "").lower():
                filtered.append(p)
                
        # 🛠️ 核心洗牌邏輯：定義排序的 Key
        def sort_key(x):
            # 1. 來源置頂權重：如果套件來源符合當前指定的優先來源，權重為 1，否則為 0
            is_priority = 1 if x.get("manager") == self.current_priority_manager else 0
            
            # 2. 次要排序依據（大小或名稱）
            if sort_by == "size":
                secondary = self.parse_size_to_bytes(x.get("size", ""))
            else:
                secondary = x.get("name", "").lower()
                
            # 回傳 tuple：(是否置頂, 次要排序值)
            return (is_priority, secondary if sort_by == "size" else 0)

        # 進行排序 (配合你原本的 self.sort_descending)
        if sort_by == "size":
            filtered.sort(key=sort_key, reverse=self.sort_descending)
        elif sort_by == "name":
            if not self.current_priority_manager:
                filtered.sort(key=lambda x: x.get("name", "").lower(), reverse=self.sort_descending)
            else:
                filtered.sort(key=lambda x: (1 if x.get("manager") == self.current_priority_manager else 0, x.get("name", "").lower()), reverse=self.sort_descending)
            
        for p in filtered:
            pkg_manager = p.get("manager", "unknown")
            pkg_name = p.get("name", "unknown")
            pkg_version = p.get("version", "unknown")
            pkg_size = p.get("size", "N/A")
            
            table.add_row(
                f"[bold #e0af68]{pkg_manager}[/]",
                pkg_name,
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
            
            # 單純更新右側 AI 區塊，絕對不驚動終端機
            markdown_widget = self.query_one("#ai-output", Markdown)
            markdown_widget.update(f"⏳ 正在幫您通靈已安裝的 `{package_name}`...")
            asyncio.create_task(self.update_ai_pane(package_name, markdown_widget))
        except Exception:
            pass

    # 🎯 行為二：只有按下 Enter 鍵（Selected） -> 「才真正跳出終端機解除安裝」
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        row_data = table.get_row(event.row_key)
        
        # 🧼 用正規表達式完美剥離所有 Rich 標籤
        import re
        def clean_markup(text_str: str) -> str:
            return re.sub(r'\[\/?[a-zA-Z0-9#\s_@-]+\]', '', text_str).strip()
        
        raw_mgr = clean_markup(str(row_data[0]))
        package_name = clean_markup(str(row_data[1]))
        
        # 🤖 同步在右側加載 AI 通靈解說（一邊卸載一邊看用途）
        markdown_widget = self.query_one("#ai-output", Markdown)
        markdown_widget.update(f"⏳ 正在幫您通靈已安裝的 `{package_name}`...")
        asyncio.create_task(self.update_ai_pane(package_name, markdown_widget))

        # 🚪 核心功能：直接發動系統原生終端機卸載
        self.notify(f"🛠️ 正在準備為您卸載 {raw_mgr} 套件：{package_name}")
        
        if raw_mgr == "pacman":
            uninstall_cmd = f"sudo pacman -Rns {package_name}"
        elif raw_mgr == "apt":
            uninstall_cmd = f"sudo apt purge -y {package_name}"
        elif raw_mgr == "snap":
            uninstall_cmd = f"sudo snap remove {package_name}"
        else:
            uninstall_cmd = f"echo '未知的套件來源，無法自動刪除'"

        # ⚡ 全自動系統預設終端機自適應探測
        terminal_cmd = None
        common_terminals = ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]
        for term in common_terminals:
            if shutil.which(term) is not None:
                terminal_cmd = term
                break

        try:
            if terminal_cmd == "gnome-terminal":
                subprocess.Popen([
                    "gnome-terminal", "--", "bash", "-c",
                    f"{uninstall_cmd}; echo; echo \"=============================\"; read -p \"卸載程序執行完畢，按 [Enter] 鍵關閉視窗...\""
                ])
            elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                subprocess.Popen([
                    terminal_cmd, "-e", 
                    f"bash -c '{uninstall_cmd}; echo; echo \"=============================\"; read -p \"卸載程序執行完畢，按 [Enter] 鍵關閉視窗...\"'"
                ])
            else:
                subprocess.Popen(["bash", "-c", uninstall_cmd])

            # 刪除完後，自動在 3 秒後重新整理表格，讓套件從畫面上消失
            async def delayed_refresh():
                await asyncio.sleep(3)
                await self.load_installed_packages()
                self.notify("🔄 已自動為您刷新全通路套件清單！")

            asyncio.create_task(delayed_refresh())

        except Exception as e:
            self.notify(f"❌ 無法開啟外部終端機: {str(e)}", severity="error")


    async def update_ai_pane(self, package_name, widget):
        ai_response = await self.ai.ask_gemini(package_name)
        widget.update(ai_response)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        pkg_name = event.value.strip()
        if not pkg_name:
            self.refresh_table_view()
            return
        markdown_widget = self.query_one("#ai-output", Markdown)
        markdown_widget.update(f"⏳ 正在分析 `{pkg_name}`...")
        self.refresh_table_view(highlight_keyword=pkg_name)
        ai_response = await self.ai.ask_gemini(pkg_name)
        markdown_widget.update(ai_response)

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
                def apply_theme_callback(new_css: str) -> None:
                    if new_css:
                        self.app.css = new_css
                        self.refresh()
                        self.notify("🎨 佈景主題切換成功！")
                self.push_screen(ThemeMenuScreen(), apply_theme_callback)
            elif action == "quit":
                self.action_quit()
        self.push_screen(EscMenuScreen(), handle_esc_callback)

if __name__ == "__main__":
    app = LinuxPackageManagerApp()
    app.run()