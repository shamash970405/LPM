import os
import shutil
import asyncio
import subprocess
import socket
from google import genai
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from theme import ThemeManager
from textual.widgets import Header, Footer, Input, Markdown, Label, DataTable, OptionList, Button 
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from morefunction import ThemeMenuScreen
from morefunction import SettingsScreen
from modals import BatchActionModal
from morefunction import ExportModal
from textual.binding import Binding
from sys_info import SysInfo

# ================= 1. Gemini AI 模組 =================
class GeminiExplainer:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None
        # 啟動獨立的系統資訊引擎
        self.sys_info = SysInfo()
        
        # 把引擎測出來的狀態重新綁回 self.sys_status，維持原本表格的運作
        self.sys_status = self.sys_info.status

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
            yield Label("系統控制選單(歐批踢唉歐嗯)", id="esc-title")
            yield OptionList(

                Option("⚙️ 系統設定", id="open_settings"), 
                Option("📤 匯出套件", id="export_list"),
                Option("📥 匯入套件", id="import_list"),
                Option("🔄 更新", id="update_system"),
                Option("🚪 退出程式", id="quit")
            
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

class PackageTable(DataTable):
    """專屬綁定 Enter 鍵的表格，徹底解決與其他輸入框的按鍵衝突"""
    BINDINGS = [
        # ✨ 將無敵星星縮小範圍，只綁定在這個表格上！
        Binding("enter", "app.enter_action", "確認刪除", priority=True)
    ]
    pass
# ================= 3. 主介面模組 =================
class LinuxPackageManagerApp(App):
    BINDINGS = [
        ("Q", "quit", "系統離開"),
        ("f1", "focus_search", "搜尋選中套件"),
        ("escape", "open_esc_menu", "系統選單"),
        ("space", "space_action", "多選標記"),      
        
        # ✨ 終極殺招：用 Binding 物件並加上 priority=True，強勢覆蓋 DataTable 的隱藏設定！
        ("enter", "do_nothing", "確認刪除"),

        ("z", "z_action", "批量安裝/卸載"),      
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

        # ✨ 啟動獨立的系統資訊引擎
        self.sys_info = SysInfo()
        self.sys_status = self.sys_info.status

        # 📦 核心資料庫暫存區與排序狀態
        self.raw_packages = []
        self.installed_packages = []
        self.current_sort = "name"
        self.sort_descending = False
        self.current_priority_manager = "apt"  # 🎯 預設優先置頂 Ubuntu APT
        
        self.left_pane_width = 40
        self.bottom_pane_height = 60
        self.ai_task = None

   # 🎯 物理分流：完全不使用 RowSelected 事件，改用精準的鍵盤事件
    # 🎯 物理分流：升級版鍵盤事件核心（支援 S 鍵多選與 Enter 批次刪除）
    def on_key(self, event: __import__("textual").events.Key) -> None:
        
        # 🔓 釋放 Esc 鍵！讓事件交給 BINDINGS 的 open_esc_menu 處理
        if event.key == 'escape':
            # 🛡️ 攔截：如果正在多選模式，就清空選取，絕對不開選單！
            if hasattr(self, "selected_packages") and self.selected_packages:
                self.selected_packages.clear()
                self.clear_notifications()
                self.notify("🚫 已清空所有待刪除項目", severity="warning", timeout=2)
                # 強制阻止事件傳遞給預設的選單 BINDINGS
                event.prevent_default()
                event.stop()
                return
            return

        # 🚪 經典 Linux 快捷鍵：按 Q 退出程式
        if event.key.lower() == "q":
            if not (self.focused and getattr(self.focused, "id", None) == "pkg-input"):
                self.exit()
                return
        
        if event.key.lower() == "z":
            # 🛡️ 焦點檢查：如果游標「在」搜尋輸入框裡，不要攔截，放行讓使用者可以正常打出 "z" 鍵！
            if self.focused and getattr(self.focused, "id", None) == "pkg-input":
                return
            # 🚀 游標在外面時，直接將批次視窗推進渲染層！
            self.push_screen(BatchActionModal(main_app=self))
            return

        # 🧰 初始化動態選擇清單 (防護罩：避免動到 __init__)
        if not hasattr(self, "selected_packages"):
            self.selected_packages = {}

        # 🧪 共通文字清洗工具 (提到最上層供 S 鍵與 Enter 鍵共享)
        import re
        def clean_markup(text_str: str) -> str:
            return re.sub(r'\[.*?\]', '', str(text_str)).strip()

        # 📌 【Space 鍵：多選 / 取消選取 模式 (TUI 界的多選標準)】
        if event.key == "space":
            # 🛡️ 焦點檢查：如果游標在搜尋輸入框裡，放行讓使用者打半形空白！
            if self.focused and getattr(self.focused, "id", None) == "pkg-input":
                return

            try:
                table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
            except Exception:
                return

            if table.cursor_coordinate:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                row_data = table.get_row(row_key)
                
                raw_mgr = clean_markup(row_data[0])
                package_name = clean_markup(row_data[1])
                pkg_unique_id = f"{raw_mgr}:{package_name}"
                
                # 🔄 切換選取狀態
                if pkg_unique_id in self.selected_packages:
                    del self.selected_packages[pkg_unique_id]
                else:
                    self.selected_packages[pkg_unique_id] = {"manager": raw_mgr, "name": package_name}
                
                # 🧹 先清除畫面上所有的舊通知 (避免重複按導致通知疊成一座山)
                self.clear_notifications()

                # 📢 顯示常駐的待刪除「詳細名單」面板
                if self.selected_packages:
                    # 📝 整理出所有選取的套件名稱
                    selected_names = [pkg["name"] for pkg in self.selected_packages.values()]
                    
                    # 🛡️ 版面防爆機制：如果選太多，做個縮寫避免通知遮住整個螢幕
                    if len(selected_names) > 5:
                        display_text = ", ".join(selected_names[:5]) + f" ...等共 {len(selected_names)} 項"
                    else:
                        display_text = ", ".join(selected_names)

                    self.notify(
                        f"即將刪除：\n[bold white]{display_text}[/]\n\n👉 按 [Enter] 執行批次刪除\n👉 按 [Esc] 取消所有選取",
                        title=f"📋 批次刪除待命中 ({len(self.selected_packages)} 項)",
                        severity="warning",
                        timeout=99999999  # 🌟 永遠顯示
                    )
                return

        # 🔑 【Enter 鍵：執行刪除（單一或批次自動分流）】
        if event.key == "enter":
            # 🛡️ 焦點防呆攔截：如果游標停在搜尋框，立刻中斷
            if self.focused and getattr(self.focused, "id", None) == "pkg-input":
                return

            try:
                table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
            except Exception:
                return 

            uninstall_cmd = ""
            
            # 🚨 分流 A：如果選取清單裡有東西，啟動「批次大規模刪除指令建構引擎」！
            if self.selected_packages:
                # 🧠 智能分組：把相同管理員的套件聚在一起
                grouped_tasks = {}
                for pkg_info in self.selected_packages.values():
                    grouped_tasks.setdefault(pkg_info["manager"], []).append(pkg_info["name"])
                
                # 🛠️ 根據不同管理員串聯多個套件 (例如：apt purge -y pkg1 pkg2)
                # ✅ 升級後無腦優雅的寫法：
                cmd_list = []
                for mgr, pkgs in grouped_tasks.items():
            # 讓 sys_info 自動依據管理員和動作，噴出對應的 Arch 或 Debian 指令！
                    cmd_list.append(self.sys_info.build_command(mgr=mgr, action="uninstall", pkgs=pkgs))

                uninstall_cmd = " && ".join(cmd_list)
                self.notify(f"🚀 批次觸發: 準備解除安裝 {len(self.selected_packages)} 個套件...")
                
                # 🧹 任務升空後，立刻清空緩存，回復乾淨狀態
                self.selected_packages.clear()
                self.clear_notifications()
                
            # 🎯 分流 B：清單是空的，退回原本高精準度的「單一套件移除」邏輯
            elif table.cursor_coordinate:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                row_data = table.get_row(row_key)
                
                raw_mgr = clean_markup(row_data[0])
                package_name = clean_markup(row_data[1])
                
                self.notify(f"🚀 鍵盤觸發: 準備解除安裝 {raw_mgr.upper()} 套件: {package_name}...")
                
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
            
            else:
                return

           # 🚀 執行卸載程序 (支援批次、單一指令與 SSH 內建終端機)
            import shutil, subprocess, asyncio
            from morefunction import CommandTerminalScreen # 引入我們剛寫好的內建終端機

            # ✨ 判斷是否開啟了 SSH 模式
            if getattr(self, "ssh_mode", False):
                
                # 🌟 核心升級：定義一個當內部終端機「關閉時」才觸發的專屬動作
                def after_terminal_closed(_=None):
                    self.notify("🔄 偵測到操作完畢，正在重新掃描系統套件...")
                    import asyncio
                    asyncio.create_task(self.load_installed_packages())

                # 💻 SSH 模式：彈出終端機，並且把這個「關閉後的動作」綁定在它身上！
                self.push_screen(CommandTerminalScreen(uninstall_cmd), after_terminal_closed)
                proc = None # 內部終端機由畫面處理，主程式不需要綁定外部 proc

            else:
                # 🖥️ 維持原本的邏輯：呼叫外部圖形終端機
                terminal_cmd = None
                for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                    if shutil.which(term) is not None:
                        terminal_cmd = term
                        break
                
                proc = None  # 💡 用來綁定行程的變數
                try:
                    if terminal_cmd == "gnome-terminal":
                        proc = subprocess.Popen(["gnome-terminal", "--wait", "--", "bash", "-c", f"{uninstall_cmd}; read -p '執行完畢，按 [Enter] 關閉視窗...'"])
                    elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                        proc = subprocess.Popen([terminal_cmd, "-e", f"bash -c '{uninstall_cmd}; read -p \"執行完畢，按 [Enter] 關閉視窗...\"'"])
                    else:
                        proc = subprocess.Popen(["bash", "-c", uninstall_cmd])
                except Exception as e:
                    self.notify(f"❌ 啟動卸載程序失敗: {str(e)}", severity="error")

            # 🎯 【主程式專屬：主動防禦型精準監聽管線】
            if proc is not None:
                async def exact_refresh():
                    # ⏳ 在背景線程死守等待終端機行程結束，絕對不卡死 LPM 畫面
                    await asyncio.to_thread(proc.wait)
                    
                    # 當使用者在終端機按下 Enter 讓視窗消失的瞬間，精準觸發刷新！
                    try:
                        await self.load_installed_packages()
                        self.notify("📦 偵測到刪除程序完成，套件清單已即時同步！")
                    except Exception: 
                        pass
                
                # 扣下背景監聽任務的扳機
                asyncio.create_task(exact_refresh())

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        # 📦 上半部：左右兩欄並排的水平容器
        with Horizontal(classes="top-box", id="top-box"):
            
            # ⬅️ 左欄：系統狀態與硬碟資訊
            with Vertical(classes="left-pane", id="left-pane"):
                yield Label(f"  發行版：[bold #9ece6a]{self.sys_info.get_os_name()}[/]", classes="status-label")
                for mgr, avail in self.sys_status.items():
                    if avail:
                        yield Label(f"   - {mgr} (計算中...)", id=f"lbl-{mgr}", classes="status-label")
                yield Label(self.sys_info.get_disk_info(), classes="disk-label")            
            
            # ➡️ 右欄：Gemini AI 查詢面板
            with Vertical(classes="right-pane"):
                yield Label("線上Gemini查詢：", classes="section-title")
                yield Input(placeholder="在此輸入套件名稱", id="pkg-input")
                yield Markdown("等待輸入中...", id="ai-output")
                
        # 📦 下半部：套件表格 (⚠️ 請確保這個區塊只有一個！)
        with Vertical(classes="bottom-pane", id="bottom-pane"):
            yield Label("套件列表", classes="section-title")
            
            # ✨ 這是我們剛剛換上的客製化表格
            yield PackageTable(id="installed-packages-table")
            
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
            target_id = event.control.id
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
        self.refresh_table_view(search_text=current_keyword, sort_by=self.current_sort)

    # 🎯 點擊表頭排序的核心觸發區 (Textual 原生極速渲染版)
    def on_data_table_header_selected(self, event: __import__("textual").widgets.DataTable.HeaderSelected) -> None:
        try:
            table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
        except Exception:
            return

        # 1. 切換正反向 (預設為 False)
        self.sort_descending = not getattr(self, "sort_descending", False)
        
        # 2. 專屬容量轉換器 (把字串換算成純數字)
        def parse_size(size_str):
            import re
            # 清除可能殘留的顏色標籤，並轉大寫
            clean_str = re.sub(r'\[.*?\]', '', str(size_str)).upper().strip()
            try:
                if "GB" in clean_str: return float(clean_str.replace("GB", "").strip()) * 1024 * 1024 * 1024
                if "MB" in clean_str: return float(clean_str.replace("MB", "").strip()) * 1024 * 1024
                if "KB" in clean_str: return float(clean_str.replace("KB", "").strip()) * 1024
                if "B" in clean_str: return float(clean_str.replace("B", "").strip())
                return 0.0 # 遇到沙盒管理等文字直接墊底
            except:
                return 0.0

        # 3. 呼叫 Textual 底層原生排序 (完全不經過 refresh_table_view，零延遲！)
        try:
            if event.column_index == 4:
                # 佔用容量：套用專屬的數字轉換器
                table.sort(event.column_key, reverse=self.sort_descending, key=parse_size)
            else:
                # 其他純文字欄位：清除標籤後直接按字母排序
                def clean_text(text):
                    import re
                    return re.sub(r'\[.*?\]', '', str(text)).lower().strip()
                table.sort(event.column_key, reverse=self.sort_descending, key=clean_text)
                
            # 給一個非常低調且 1 秒就會消失的提示，證明它有在做事
            self.notify("✨ 列表已重新排序", timeout=1)
            
        except Exception as e:
            # 如果真的有錯，強制把錯誤印在畫面上讓我們抓兇手
            self.notify(f"❌ 排序失敗: {str(e)}", severity="error", timeout=5)

    async def load_installed_packages(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            table.clear()
        except Exception: pass
        
        self.raw_packages = []
        tasks = []
        if self.sys_status.get("pacman"): tasks.append(self._scan_pacman())
        if self.sys_status.get("apt"): tasks.append(self._scan_apt())
        if self.sys_status.get("snap"): tasks.append(self._scan_snap())
        # ✨ 新增這行：如果系統有 Flatpak，就把它加入平行掃描任務中！
        if self.sys_status.get("flatpak"): tasks.append(self._scan_flatpak())

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

        try:
            current_keyword = self.query_one("#pkg-input").value
            self.refresh_table_view(search_text=current_keyword, sort_by=getattr(self, "current_sort", "name"))
        except Exception:
            # 防呆機制：如果找不到搜尋框，就正常刷新
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

    async def _scan_flatpak(self):
        try:
            # 🚀 呼叫 flatpak list，並指定只輸出 Application ID 和 Version (以 tab 分隔)
            process = await asyncio.create_subprocess_exec(
                "flatpak", "list", "--columns=application,version", 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                for line in lines:
                    if not line.strip(): 
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 1:
                        name = parts[0].strip()
                        version = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "未知"
                        # Flatpak 同樣是沙盒機制，容量計算較複雜，我們統一標示為沙盒管理
                        self.raw_packages.append({
                            "manager": "flatpak", 
                            "name": name, 
                            "version": version, 
                            "size": "沙盒管理"
                        })
        except Exception: 
            pass

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
            # 1. 管理員優先權
            priority_mgr = getattr(self, "current_priority_manager", None)
            is_priority = 1 if x.get("manager") == priority_mgr else 0
            
            # 2. 確定目前的排序目標
            target = getattr(self, "current_sort", sort_by)
            
            # ⚖️ 容量排序邏輯
            if target == "size":
                size_str = str(x.get("size", "0")).upper()
                try:
                    # 內建無敵轉型，把 MB, GB 換算成最基礎的 Bytes 數字來比大小！
                    if "GB" in size_str: val = float(size_str.replace("GB", "").strip()) * 1024 * 1024 * 1024
                    elif "MB" in size_str: val = float(size_str.replace("MB", "").strip()) * 1024 * 1024
                    elif "KB" in size_str: val = float(size_str.replace("KB", "").strip()) * 1024
                    elif "B" in size_str: val = float(size_str.replace("B", "").strip())
                    else: val = 0.0 # 遇到 "沙盒管理" 這類純文字，乖乖變成 0 墊底
                except Exception:
                    val = 0.0
                return (is_priority, val)
                
            # 📁 群組排序邏輯
            elif target == "group":
                return (is_priority, str(x.get("group", "System")).lower())
                
            # 📦 來源排序邏輯
            elif target == "manager":
                return (is_priority, str(x.get("manager", "")).lower())
                
            # 🔤 預設名稱排序邏輯
            else:
                return (is_priority, str(x.get("name", "")).lower())

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

    # 🎯 捕捉輸入框改變事件 (內建防抖引擎)
    async def on_input_changed(self, event: __import__("textual").widgets.Input.Changed) -> None:
        # 確保是套件搜尋框觸發的
        if getattr(event.input, "id", None) != "pkg-input":
            return
            
        search_text = event.value.strip()
        
        # 🛑 防抖核心 1：取消上一次還沒執行的搜尋任務
        if hasattr(self, "ai_task") and self.ai_task:
            self.ai_task.cancel()
            
        # 如果使用者把輸入框清空了，就直接恢復預設狀態並跳出
        if not search_text:
            try:
                self.query_one("#ai-output").update("等待輸入中...")
                self.refresh_table_view("")
            except Exception: pass
            return

        # ⏳ 防抖核心 2：定義一個新的延遲查詢任務
        async def delayed_search():
            import asyncio
            await asyncio.sleep(0.3) # 停頓 0.3 秒，確認手指離開鍵盤了才動作
            
            self.notify(f"🔍 自動觸發搜尋: {search_text}")
            
            # 更新右邊的 AI 面板狀態
            try:
                ai_panel = self.query_one("#ai-output")
                ai_panel.update(f"⏳ 正在幫您過濾 '{search_text}' 的資訊...")
            except Exception: 
                pass
                
            self.refresh_table_view(search_text)

        # 🚀 防抖核心 3：發射剛剛寫好的延遲任務
        import asyncio
        self.ai_task = asyncio.create_task(delayed_search())

    def action_resize_left_pane(self, delta: int) -> None:
        self.left_pane_width = max(20, min(70, self.left_pane_width + delta))
        self.query_one("#left-pane").styles.width = f"{self.left_pane_width}%"

    def action_resize_bottom_pane(self, delta: int) -> None:
        self.bottom_pane_height = max(20, min(80, self.bottom_pane_height + delta))
        self.query_one("#bottom-pane").styles.height = f"{self.bottom_pane_height}%"
        self.query_one("#top-box").styles.height = f"{100 - self.bottom_pane_height}%"

    def action_space_action(self) -> None:
        """Space 的專屬空殼，真實邏輯在 on_key"""
        pass

    def action_do_nothing(self) -> None:
        """純顯示用的空殼"""
        pass

    def action_enter_action(self) -> None:
        """✅ 真實的 Enter 執行邏輯已經搬來專屬 Action 這裡了！"""
        # 🛡️ 焦點防呆攔截：如果游標停在搜尋框，立刻中斷，讓輸入框能正常運作
        if self.focused and getattr(self.focused, "id", None) == "pkg-input":
            return

        try:
            table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
        except Exception:
            return 

        # 🧰 防呆初始化
        if not hasattr(self, "selected_packages"):
            self.selected_packages = {}

        uninstall_cmd = ""
        
        import re
        def clean_markup(text_str: str) -> str:
            return re.sub(r'\[.*?\]', '', str(text_str)).strip()
        
        # 🚨 分流 A：如果選取清單裡有東西，啟動「批次大規模刪除指令建構引擎」！
        if self.selected_packages:
            grouped_tasks = {}
            for pkg_info in self.selected_packages.values():
                grouped_tasks.setdefault(pkg_info["manager"], []).append(pkg_info["name"])
            
            cmd_list = []
            for mgr, pkgs in grouped_tasks.items():
                pkgs_str = " ".join(pkgs)
                if mgr == "pacman": cmd_list.append(f"sudo pacman -Rns {pkgs_str}")
                elif mgr == "yay": cmd_list.append(f"yay -Rns {pkgs_str}")
                elif mgr == "paru": cmd_list.append(f"paru -Rns {pkgs_str}")
                elif mgr == "apt": cmd_list.append(f"sudo apt purge -y {pkgs_str}")
                elif mgr == "dnf": cmd_list.append(f"sudo dnf remove -y {pkgs_str}")
                elif mgr == "zypper": cmd_list.append(f"sudo zypper remove -y {pkgs_str}")
                elif mgr == "apk": cmd_list.append(f"sudo apk del {pkgs_str}")
                elif mgr == "emerge": cmd_list.append(f"sudo emerge --deselect {pkgs_str}")
                elif mgr == "xbps": cmd_list.append(f"sudo xbps-remove -R {pkgs_str}")
                elif mgr == "snap": cmd_list.append(f"sudo snap remove {pkgs_str}")
                elif mgr == "flatpak": cmd_list.append(f"flatpak uninstall -y {pkgs_str}")
                elif mgr == "brew": cmd_list.append(f"brew uninstall {pkgs_str}")
            
            uninstall_cmd = " && ".join(cmd_list)
            self.notify(f"🚀 批次觸發: 準備解除安裝 {len(self.selected_packages)} 個套件...")
            
            self.selected_packages.clear()
            self.clear_notifications()
            
        # 🎯 分流 B：清單是空的，退回原本高精準度的「單一套件移除」邏輯
        elif table.cursor_coordinate:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row_data = table.get_row(row_key)
            
            raw_mgr = clean_markup(row_data[0])
            package_name = clean_markup(row_data[1])
            
            self.notify(f"🚀 鍵盤觸發: 準備解除安裝 {raw_mgr.upper()} 套件: {package_name}...")
            
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
        
        else:
            return

        # 🚀 執行卸載程序
        import shutil, subprocess, asyncio
        from morefunction import CommandTerminalScreen

        if getattr(self, "ssh_mode", False):
            def after_terminal_closed(_=None):
                self.notify("🔄 偵測到操作完畢，正在重新掃描系統套件...")
                import asyncio
                asyncio.create_task(self.load_installed_packages())

            self.push_screen(CommandTerminalScreen(uninstall_cmd), after_terminal_closed)
            proc = None 
        else:
            terminal_cmd = None
            for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                if shutil.which(term) is not None:
                    terminal_cmd = term
                    break
            
            proc = None 
            try:
                if terminal_cmd == "gnome-terminal":
                    proc = subprocess.Popen(["gnome-terminal", "--wait", "--", "bash", "-c", f"{uninstall_cmd}; read -p '執行完畢，按 [Enter] 關閉視窗...'"])
                elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                    proc = subprocess.Popen([terminal_cmd, "-e", f"bash -c '{uninstall_cmd}; read -p \"執行完畢，按 [Enter] 關閉視窗...\"'"])
                else:
                    proc = subprocess.Popen(["bash", "-c", uninstall_cmd])
            except Exception as e:
                self.notify(f"❌ 啟動卸載程序失敗: {str(e)}", severity="error")

        if proc is not None:
            async def exact_refresh():
                await asyncio.to_thread(proc.wait)
                try:
                    await self.load_installed_packages()
                    self.notify("📦 偵測到刪除程序完成，套件清單已即時同步！")
                except Exception: 
                    pass
            
            asyncio.create_task(exact_refresh())

    def action_z_action(self) -> None:
        """Z 鍵的專屬空殼，真實邏輯在 on_key"""
        pass

    def action_focus_search(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", __import__("textual").widgets.DataTable)
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row_data = table.get_row(row_key)
            package_name = row_data[1].replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip()
            search_input = self.query_one("#pkg-input", __import__("textual").widgets.Input)
            search_input.value = package_name
            search_input.focus()
            self.refresh_table_view(search_text=package_name)
            self.notify(f"🔍 已自動鎖定並搜尋：{package_name}")
        except Exception:
            self.query_one("#pkg-input", __import__("textual").widgets.Input).focus()

    def action_open_esc_menu(self) -> None:
        def handle_esc_callback(action: str | None) -> None:
            if not action:
                return

            if action == "open_settings":
                def apply_settings_callback(settings_data: dict | None) -> None:
                    if settings_data is not None:
                        selected_engine = settings_data.get("ai_engine", "gemini")
                        new_token = settings_data.get("api_token", "").strip()
                        ssh_mode = settings_data.get("ssh_mode", False)
                        pref_mgr = settings_data.get("preferred_mgr", "apt")
                        
                        self.current_ai_engine = selected_engine
                        self.current_gemini_token = new_token
                        self.ssh_mode = ssh_mode
                        self.preferred_mgr = pref_mgr
                        
                        try:
                            self.ai.refresh_client(new_token)
                        except Exception as e:
                            self.notify(f"❌ AI 初始化失敗: {str(e)}", severity="error")
                            return

                        if new_token:
                            self.notify(f"⚙️ {selected_engine.upper()} 引擎已切換，金鑰儲存成功！")
                        else:
                            self.notify(f"⚠️ 已切換至 {selected_engine.upper()}，但您尚未輸入 API 金鑰哦！", severity="warning")

                current_ssh_mode = getattr(self, "ssh_mode", False)
                current_pref_mgr = getattr(self, "preferred_mgr", "apt")
                from morefunction import SettingsScreen
                self.push_screen(SettingsScreen(getattr(self, "current_gemini_token", ""), current_ssh_mode, current_pref_mgr), apply_settings_callback)

            # 🔄 處理系統與套件更新
            elif action == "update_system":
                from morefunction import UpdateChoiceModal, PackageUpdateModal

                # ✨ 建立一個共用的執行引擎：負責判斷 SSH 模式，並處理背景刷新
                def execute_update_cmd(final_cmd: str):
                    if not final_cmd or final_cmd == "echo '無更新指令'" or final_cmd == "echo '找不到支援的更新指令'":
                        self.notify("⚠️ 沒有產生有效的更新指令！", severity="warning")
                        return

                    if getattr(self, "ssh_mode", False):
                        # 💻 SSH 模式：使用內建終端機
                        from morefunction import CommandTerminalScreen
                        def after_term(_=None):
                            self.notify("🔄 更新完畢，正在重新掃描系統套件...")
                            import asyncio
                            asyncio.create_task(self.load_installed_packages())
                        self.push_screen(CommandTerminalScreen(final_cmd), after_term)
                    else:
                        # 🖥️ 桌面模式：呼叫外部系統終端機
                        import shutil, subprocess, os
                        signal_file = "/tmp/lpm_refresh.tmp"
                        if os.path.exists(signal_file):
                            try: os.remove(signal_file)
                            except Exception: pass

                        terminal_cmd = None
                        for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                            if shutil.which(term) is not None:
                                terminal_cmd = term; break
                        
                        bash_cmd = f"{final_cmd}; touch {signal_file}; read -p '執行完畢，按 [Enter] 關閉視窗...'"
                        
                        try:
                            if terminal_cmd == "gnome-terminal":
                                subprocess.Popen(["gnome-terminal", "--", "bash", "-c", bash_cmd])
                            elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                                subprocess.Popen([terminal_cmd, "-e", f"bash -c \"{bash_cmd}\""])
                            else:
                                subprocess.Popen(["bash", "-c", bash_cmd])
                        except Exception as e:
                            self.notify(f"❌ 啟動外部終端機失敗: {str(e)}", severity="error")
                            return
                        
                        # 背景監聽外部終端機是否關閉
                        async def exact_refresh():
                            for _ in range(600):
                                if os.path.exists(signal_file):
                                    try: os.remove(signal_file)
                                    except Exception: pass
                                    try:
                                        await self.load_installed_packages()
                                        self.notify("📦 更新任務完成，套件清單已即時同步！")
                                    except Exception: pass
                                    break
                                import asyncio
                                await asyncio.sleep(1)
                        import asyncio
                        asyncio.create_task(exact_refresh())

                # ========================================================

                def handle_update_choice(choice: str | None) -> None:
                    if not choice: return
                    
                    # 💻 模式一：全系統大升級與垃圾回收
                    if choice == "system_update":
                        cmd = []
                        if self.sys_status.get("apt"): cmd.append("sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y")
                        if self.sys_status.get("snap"): cmd.append("sudo snap refresh")
                        if self.sys_status.get("flatpak"): cmd.append("flatpak update -y")
                        if self.sys_status.get("pacman"): cmd.append("sudo pacman -Syu --noconfirm")
                        
                        final_cmd = " && ".join(cmd) if cmd else "echo '找不到支援的更新指令'"
                        # ✨ 透過共用引擎發射
                        execute_update_cmd(final_cmd)

                    # 📦 模式二：選擇個別套件更新
                    elif choice == "package_update":
                        table = self.query_one("#installed-packages-table")
                        package_data = []
                        import re
                        for row_key in table.rows:
                            row = table.get_row(row_key)
                            mgr = re.sub(r'\[.*?\]', '', str(row[0])).strip()
                            name = re.sub(r'\[.*?\]', '', str(row[1])).strip()
                            package_data.append({"mgr": mgr, "name": name})
                        
                        def handle_package_update(selected_pkgs: dict | None) -> None:
                            if not selected_pkgs: return
                            
                            cmd = []
                            for mgr, pkgs in selected_pkgs.items():
                                pkgs_str = " ".join(pkgs)
                                if mgr == "apt": cmd.append(f"sudo apt --only-upgrade install -y {pkgs_str}")
                                elif mgr == "snap": cmd.append(f"sudo snap refresh {pkgs_str}")
                                elif mgr == "flatpak": cmd.append(f"flatpak update -y {pkgs_str}")
                                elif mgr == "pacman": cmd.append(f"sudo pacman -S --needed --noconfirm {pkgs_str}")
                                elif mgr == "yay": cmd.append(f"yay -S --needed --noconfirm {pkgs_str}")
                            
                            final_cmd = " && ".join(cmd) if cmd else "echo '無更新指令'"
                            # ✨ 透過共用引擎發射
                            execute_update_cmd(final_cmd)

                        self.push_screen(PackageUpdateModal(package_data), handle_package_update)

                self.push_screen(UpdateChoiceModal(), handle_update_choice)
            
            elif action == "export_list":
                from morefunction import ExportModal
                def clean_text(raw_data):
                    if hasattr(raw_data, "plain"): return raw_data.plain.strip()
                    import re
                    return re.sub(r'\[.*?\]', '', str(raw_data)).strip()
                    
                table = self.query_one("#installed-packages-table")
                package_data = []
                for row_key in table.rows:
                    row = table.get_row(row_key)
                    package_data.append({"mgr": clean_text(row[0]), "name": clean_text(row[1]), "version": clean_text(row[3])})

                def apply_export_callback(export_data: dict | None) -> None:
                    if export_data is not None:
                        import socket, os
                        from datetime import datetime
                        file_path = export_data["path"]
                        filter_text = export_data.get("filter_text", "").lower()
                        
                        if not file_path: file_path = os.path.expanduser("~/lpm_packages.txt")
                        elif os.path.isdir(file_path): file_path = os.path.join(file_path, "lpm_packages.txt")
                        
                        try:
                            with open(file_path, "w", encoding="utf-8") as f:
                                hostname = socket.gethostname()
                                now = datetime.now().strftime("%Y/%m/%d  %H:%M")
                                f.write(f"hostname:{hostname}\n匯出時間:{now}\n\n＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝\n")
                                
                                all_packages = [pkg for pkg in package_data if not filter_text or filter_text in pkg["name"].lower()]
                                
                                from collections import defaultdict
                                groups = defaultdict(list)
                                for pkg in all_packages: groups[pkg["name"].split("-", 1)[0]].append(pkg)
                                
                                for prefix in sorted(groups.keys()):
                                    items = sorted(groups[prefix], key=lambda x: x["name"])
                                    if len(items) == 1:
                                        pkg = items[0]
                                        line = pkg["name"]
                                        if export_data["inc_version"]: line += f" ({pkg['version']})"
                                        if export_data["inc_mgr"]: line = f"[{pkg['mgr']}] " + line
                                        f.write(line + "\n")
                                    else:
                                        f.write(f"📁 {prefix}\n") 
                                        for i, pkg in enumerate(items):
                                            branch = "└── " if i == len(items) - 1 else "├── "
                                            suffix = pkg["name"][len(prefix)+1:] if pkg["name"] != prefix else "(核心本體)"
                                            line = suffix
                                            if export_data["inc_version"]: line += f" ({pkg['version']})"
                                            if export_data["inc_mgr"]: line = f" [{pkg['mgr']}] " + line
                                            f.write(f"{branch}{line}\n")
                                            
                            self.notify(f"✅ 匯出成功！檔案已儲存至：{file_path}", severity="info")
                        except Exception as e:
                            self.notify(f"❌ 匯出失敗：{str(e)}", severity="error")

                self.push_screen(ExportModal(package_data), apply_export_callback)

            elif action == "import_list":
                from morefunction import ImportModal
                def apply_import_callback(import_data: dict | None) -> None:
                    if import_data is None: return
                    filepath = import_data["path"]
                    ignore_ver = import_data["ignore_version"]
                    
                    import os
                    if not os.path.exists(filepath):
                        self.notify("❌ 找不到指定的檔案！請確認路徑正確。", severity="error")
                        return
                        
                    try:
                        packages = []
                        current_prefix = ""
                        import re
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for raw_line in f:
                                line = raw_line.strip()
                                if not line or line.startswith(('hostname:', '匯出時間:', '＝＝＝')): continue
                                if line.startswith('📁'):
                                    current_prefix = line.replace('📁', '').strip()
                                    continue
                                
                                is_tree_item = '├──' in raw_line or '└──' in raw_line
                                line = line.replace('├── ', '').replace('└── ', '').strip()
                                
                                pkg_mgr = None
                                mgr_match = re.match(r'^\[(.*?)\]\s*(.*)', line)
                                if mgr_match: 
                                    pkg_mgr = mgr_match.group(1).lower()
                                    line = mgr_match.group(2)
                                
                                ver_match = re.search(r'\((.*?)\)$', line)
                                version = None
                                if ver_match:
                                    version = ver_match.group(1)
                                    line = line[:ver_match.start()].strip()
                                
                                pkg_name = line
                                if is_tree_item and current_prefix:
                                    pkg_name = current_prefix if pkg_name == "(核心本體)" else f"{current_prefix}-{pkg_name}"
                                
                                if not ignore_ver and version: pkg_name = f"{pkg_name}={version}"
                                if pkg_name: packages.append({"mgr": pkg_mgr, "name": pkg_name})
                                    
                        if not packages:
                            self.notify("⚠️ 檔案內沒有找到任何有效的套件名稱！", severity="warning")
                            return
                            
                        self.notify(f"✅ 成功解析 {len(packages)} 個套件！正在啟動智能安裝引擎...")
                            
                        from modals import SearchLoadingModal
                        preferred = getattr(self, "preferred_mgr", "apt")
                        
                        def after_search(final_cmd: str | None):
                            if not final_cmd: return
                            from morefunction import CommandTerminalScreen
                            if getattr(self, "ssh_mode", False):
                                def after_term(_=None):
                                    self.notify("🔄 批次匯入完畢，正在重新掃描系統套件...")
                                    import asyncio
                                    asyncio.create_task(self.load_installed_packages())
                                self.push_screen(CommandTerminalScreen(final_cmd), after_term)
                            else:
                                import shutil, subprocess
                                signal_file = "/tmp/lpm_refresh.tmp"
                                if os.path.exists(signal_file):
                                    try: os.remove(signal_file)
                                    except Exception: pass

                                terminal_cmd = None
                                for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                                    if shutil.which(term) is not None:
                                        terminal_cmd = term; break
                                
                                bash_cmd = f"{final_cmd}; touch {signal_file}; read -p '執行完畢，按 [Enter] 關閉視窗...'"
                                
                                try:
                                    if terminal_cmd == "gnome-terminal":
                                        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", bash_cmd])
                                    elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                                        subprocess.Popen([terminal_cmd, "-e", f"bash -c \"{bash_cmd}\""])
                                    else:
                                        subprocess.Popen(["bash", "-c", bash_cmd])
                                except Exception as e:
                                    self.notify(f"❌ 啟動匯入程序失敗: {str(e)}", severity="error")
                                
                                async def exact_refresh():
                                    for _ in range(600):
                                        if os.path.exists(signal_file):
                                            try: os.remove(signal_file)
                                            except Exception: pass
                                            try:
                                                await self.load_installed_packages()
                                                self.notify("📦 匯入任務完成，套件清單已即時同步！")
                                            except Exception: pass
                                            break
                                        import asyncio
                                        await asyncio.sleep(1)
                                import asyncio
                                asyncio.create_task(exact_refresh())

                        self.push_screen(SearchLoadingModal(self, packages, preferred, is_install=True), after_search)

                    except Exception as e:
                        self.notify(f"❌ 檔案解析發生錯誤：{str(e)}", severity="error")
                
                self.push_screen(ImportModal(), apply_import_callback)

            elif action == "quit":
                self.exit()

            else:
                self.notify(f"❌ 選單指令對不上：未知的 action '{action}'", severity="error")
                
        self.push_screen(EscMenuScreen(), handle_esc_callback)

if __name__ == "__main__":
    app = LinuxPackageManagerApp()
    app.run()