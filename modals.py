import os
import shutil
import asyncio
import subprocess
import random

from textual import on
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, RadioSet, RadioButton, Button, Static, Tree
from textual.reactive import reactive
from rich.text import Text

# ================= 🏳️‍⚧️ MTF 像素旗幟載入動畫元件 =================
class TransFlagLoader(Static):
    """使用 ANSI 區塊動態渲染的 MTF 旗幟像素淡入動畫"""
    progress = reactive(0.0)
    
    def on_mount(self):
        self.cols = 20
        self.rows = 5
        self.total_blocks = self.cols * self.rows
        self.indices = list(range(self.total_blocks))
        random.shuffle(self.indices) # 隨機打亂順序，創造「像素淡入」的科技感
        
        # MTF 旗幟標準色 (避開系統保留字)
        self.flag_colors = [
            "#5BCEFA", # 淺藍色
            "#F5A9B8", # 粉紅色
            "#FFFFFF", # 白色
            "#F5A9B8", # 粉紅色
            "#5BCEFA"  # 淺藍色
        ]
        self.bg_color = "#1a1b26"

    def render(self):
        text = Text()
        show_count = int((self.progress / 100) * self.total_blocks)
        visible_indices = set(self.indices[:show_count])
        
        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                color = self.flag_colors[r] if idx in visible_indices else self.bg_color
                text.append("██", style=color)
            if r < self.rows - 1:
                text.append("\n")
        return text

# ================= 🔍 獨立的搜尋等待與樹狀選擇視窗 =================
class SearchLoadingModal(ModalScreen):
    """跨通路搜尋並提供樹狀選擇列表的載入畫面"""
    
    CSS = """
    SearchLoadingModal { align: center middle; background: rgba(0, 0, 0, 0.85); }
    #loader-container { width: 65; height: auto; max-height: 90%; background: #1f2335; border: thick #7aa2f7; padding: 2 4; align: center middle; }
    #flag-loader { content-align: center middle; margin-bottom: 1; }
    #loader-status { text-align: center; color: #e0af68; text-style: bold; margin-bottom: 1; }
    
    /* 樹狀列表區域預設隱藏，搜尋完畢後顯示 */
    #tree-section { display: none; width: 100%; height: auto; margin-top: 1; }
    #result-tree { height: 15; border: solid #565f89; background: #1a1b26; margin-bottom: 1; }
    #tree-btn-box { height: auto; align: right middle; }
    #tree-cancel { margin-right: 2; }
    """

    def __init__(self, main_app, raw_packages, preferred_mgr, is_install):
        super().__init__()
        self.main_app = main_app
        self.raw_packages = raw_packages
        self.preferred_mgr = preferred_mgr
        self.is_install = is_install
        self.all_leaf_nodes = [] # 儲存所有可勾選的節點

    def compose(self):
        with Vertical(id="loader-container"):
            # 上半部：MTF 旗幟與狀態字
            yield TransFlagLoader(id="flag-loader")
            yield Label("尋找中.....wait a minute\n準備啟動引擎...", id="loader-status")
            
            # 下半部：隱藏的樹狀列表區域
            with Vertical(id="tree-section"):
                yield Label("🔍 [bold #7aa2f7]搜尋完畢！[/]請從下方樹狀列表勾選 (點擊) 您要安裝的精確套件：", classes="section-title")
                yield Tree("📦 跨通路搜尋結果", id="result-tree")
                with Horizontal(id="tree-btn-box"):
                    yield Button("取消", id="tree-cancel", variant="error")
                    yield Button("確認執行 🚀", id="tree-confirm", variant="success")

    async def on_mount(self):
        self.loader = self.query_one("#flag-loader")
        self.status_label = self.query_one("#loader-status")
        self.mgrs = ["apt", "snap", "flatpak"]
        self.mgr_idx = 0
        
        self.anim_timer = self.set_interval(0.1, self.update_progress)
        self.search_task = asyncio.create_task(self.perform_search())

    def update_progress(self):
        if self.loader.progress < 90:
            self.loader.progress += random.uniform(1, 3)
            
        self.mgr_idx += 1
        current_mgr = self.mgrs[self.mgr_idx % len(self.mgrs)]
        self.status_label.update(f"尋找中.....wait a minute\n正在尋找 {current_mgr}")

    async def perform_search(self):
        sys_status = self.main_app.sys_status

        if self.is_install:
            # 🚀 抓取多個候選名單 (Head -n 8 代表最多抓 8 個，避免列表太長)
            async def fetch_candidates(mgr_name, kw):
                try:
                    if mgr_name == "apt":
                        proc = await asyncio.create_subprocess_shell(
                            f"apt-cache search --names-only '{kw}' | awk '{{print $1}}' | head -n 8", stdout=asyncio.subprocess.PIPE)
                        out, _ = await proc.communicate()
                        return ("apt", [n for n in out.decode().strip().split('\n') if n])
                    
                    elif mgr_name == "snap":
                        proc = await asyncio.create_subprocess_shell(
                            f"snap find '{kw}' 2>/dev/null | awk 'NR>1 {{print $1}}' | head -n 8", stdout=asyncio.subprocess.PIPE)
                        out, _ = await proc.communicate()
                        return ("snap", [n for n in out.decode().strip().split('\n') if n and "No" not in n])
                    
                    elif mgr_name == "flatpak":
                        proc = await asyncio.create_subprocess_shell(
                            f"flatpak search --columns=application '{kw}' 2>/dev/null | head -n 8", stdout=asyncio.subprocess.PIPE)
                        out, _ = await proc.communicate()
                        names = [n for n in out.decode().strip().split('\n') if n]
                        names = [n for n in names if "Application" not in n and "---" not in n] # 過濾表頭
                        return ("flatpak", names)
                except Exception: pass
                return (mgr_name, [])

            # 平行搜尋所有關鍵字
            self.search_results = {}
            for keyword in self.raw_packages:
                tasks = []
                if sys_status.get("apt"): tasks.append(fetch_candidates("apt", keyword))
                if sys_status.get("snap"): tasks.append(fetch_candidates("snap", keyword))
                if sys_status.get("flatpak"): tasks.append(fetch_candidates("flatpak", keyword))

                fetched_results = await asyncio.gather(*tasks)
                self.search_results[keyword] = {mgr: names for mgr, names in fetched_results if names}

            # 搜尋完畢：停止動畫，填滿旗幟
            self.anim_timer.stop()
            self.loader.progress = 100
            self.status_label.update("✅ 解析完畢！正在建立清單...")
            await asyncio.sleep(0.6) 

            # 💡 魔法時刻：隱藏狀態列，顯示樹狀圖！
            self.query_one("#loader-status").styles.display = "none"
            self.query_one("#tree-section").styles.display = "block"
            
            tree = self.query_one("#result-tree")
            tree.root.expand()
            
            # 建立樹狀結構
            for kw, mgrs in self.search_results.items():
                kw_node = tree.root.add(f"🔑 關鍵字: [bold #e0af68]{kw}[/]", expand=True)
                
                if not mgrs:
                    kw_node.add_leaf("❌ 找不到相關套件")
                    continue
                    
                for mgr, pkgs in mgrs.items():
                    if pkgs:
                        mgr_node = kw_node.add(f"📂 {mgr.upper()} 來源", expand=True)
                        for pkg in pkgs:
                            # 建立一個帶有資料的子節點
                            leaf = mgr_node.add_leaf(f"[ ] {pkg}", data={"mgr": mgr, "pkg": pkg, "selected": False})
                            self.all_leaf_nodes.append(leaf)

            # ✨ 貼心功能：如果發現有與關鍵字「完全相符」的套件，自動幫使用者打勾！
            for kw in self.raw_packages:
                exact_match = next((l for l in self.all_leaf_nodes if l.data["pkg"] == kw), None)
                if exact_match:
                    exact_match.data["selected"] = True
                    exact_match.set_label(f"[bold #9ece6a][X] {exact_match.data['pkg']}[/]")

        else:
            # 🗑️ 移除模式：因為移除通常有明確目標，直接使用偏好管理員，跳過樹狀圖
            await asyncio.sleep(0.5)
            fallback_mgr = "apt"
            for test_mgr in ["pacman", "yay", "dnf", "zypper", "apk"]:
                if sys_status.get(test_mgr): fallback_mgr = test_mgr; break
            mgr = self.preferred_mgr if sys_status.get(self.preferred_mgr) else fallback_mgr
            
            cmd_list = []
            pkgs_str = " ".join(self.raw_packages)
            if mgr == "apt": cmd_list.append(f"sudo apt purge -y {pkgs_str}")
            elif mgr == "snap": cmd_list.append(f"sudo snap remove {pkgs_str}")
            elif mgr == "flatpak": cmd_list.append(f"flatpak uninstall -y {pkgs_str}")
            elif mgr in ["pacman", "yay"]: cmd_list.append(f"sudo {mgr} -Rns --noconfirm {pkgs_str}")
            elif mgr == "dnf": cmd_list.append(f"sudo dnf remove -y {pkgs_str}")
            elif mgr == "zypper": cmd_list.append(f"sudo zypper remove -y {pkgs_str}")
            elif mgr == "apk": cmd_list.append(f"sudo apk del {pkgs_str}")

            self.anim_timer.stop()
            self.loader.progress = 100
            self.status_label.update("✅ 指令建構完畢！")
            await asyncio.sleep(0.6)
            self.dismiss(" && ".join(cmd_list))

    # ================= 樹狀圖與按鈕的互動事件 =================
    @on(Tree.NodeSelected, "#result-tree")
    def toggle_node(self, event: Tree.NodeSelected):
        """當使用者點擊樹狀圖的子節點時，切換勾選狀態"""
        node = event.node
        
        # ✨ 移除掉不存在的 is_leaf，直接嚴謹檢查 data 裡面有沒有我們設定的字典！
        if node.data is not None and isinstance(node.data, dict) and "selected" in node.data:
            data = node.data
            data["selected"] = not data["selected"]
            
            # 更新視覺標籤
            if data["selected"]:
                node.set_label(f"[bold #9ece6a][X] {data['pkg']}[/]")
            else:
                node.set_label(f"[ ] {data['pkg']}")

    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed):
        if event.button.id == "tree-cancel":
            self.dismiss(None)
            
        elif event.button.id == "tree-confirm":
            selected_tasks = {}
            for leaf in getattr(self, "all_leaf_nodes", []):
                if leaf.data["selected"]:
                    selected_tasks.setdefault(leaf.data["mgr"], []).append(leaf.data["pkg"])
            
            if not selected_tasks:
                self.main_app.notify("⚠️ 請至少勾選一個套件！", severity="warning")
                return
            
            cmd_list = []
            for mgr, pkgs in selected_tasks.items():
                pkgs_str = " ".join(pkgs)
                if mgr == "apt": cmd_list.append(f"sudo apt install -y {pkgs_str}")
                elif mgr == "snap": cmd_list.append(f"sudo snap install {pkgs_str}")
                elif mgr == "flatpak": cmd_list.append(f"flatpak install -y {pkgs_str}")
                elif mgr in ["pacman", "yay"]: cmd_list.append(f"sudo {mgr} -S --noconfirm {pkgs_str}")
                elif mgr == "dnf": cmd_list.append(f"sudo dnf install -y {pkgs_str}")
                elif mgr == "zypper": cmd_list.append(f"sudo zypper install -y {pkgs_str}")
                elif mgr == "apk": cmd_list.append(f"sudo apk add {pkgs_str}")

            final_cmd = " && ".join(cmd_list)
            self.dismiss(final_cmd)

# ================= 🚀 批次大量安裝/刪除的彈出式魔法視窗 =================
class BatchActionModal(ModalScreen):
    
    CSS = """
    BatchActionModal { align: center middle; }
    #batch-modal-container { padding: 1 2; background: #1a1b26; border: thick #7aa2f7; width: 60; height: auto; }
    .spacing-bottom { margin-bottom: 1; }
    #batch-action-set { border: none; margin-bottom: 1; }
    #button-container { height: auto; align: right middle; }
    #batch-cancel { margin-right: 2; }
    """

    def __init__(self, main_app, **kwargs):
        super().__init__(**kwargs)
        self.main_app = main_app

    def compose(self):
        with Vertical(id="batch-modal-container"):
            yield Label("[bold #7aa2f7]🔮 終極多通路批次處理中心[/]", classes="spacing-bottom")
            yield Label("請輸入套件名稱 (支援多個，請以[bold #e0af68]英文逗號[/]分隔)：")
            yield Input(placeholder="範例: hyfetch, kde, linux", id="batch-pkg-input", classes="spacing-bottom")
            
            yield Label("請選擇執行動作：")
            with RadioSet(id="batch-action-set"):
                yield RadioButton("📥 一次吃飯", value=True, id="radio-install")
                yield RadioButton("🗑️ 一次催吐", id="radio-uninstall")
            
            with Horizontal(id="button-container"):
                yield Button("取消", variant="error", id="batch-cancel")
                yield Button("確認發射 🚀", variant="success", id="batch-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "batch-cancel":
            self.dismiss()
            return

        if event.button.id == "batch-confirm":
            input_value = self.query_one("#batch-pkg-input").value.strip()
            
            if not input_value:
                self.main_app.notify("❌ 請至少輸入一個套件名稱！", severity="error")
                return

            raw_packages = [p.strip() for p in input_value.split(",") if p.strip()]
            is_install = self.query_one("#radio-install").value
            
            self.query_one("#batch-confirm").disabled = True
            self.query_one("#batch-cancel").disabled = True

            def after_search(final_cmd: str | None):
                if not final_cmd:
                    self.query_one("#batch-confirm").disabled = False
                    self.query_one("#batch-cancel").disabled = False
                    return

                from morefunction import CommandTerminalScreen

                if getattr(self.main_app, "ssh_mode", False):
                    def after_terminal_closed(_=None):
                        self.main_app.notify("🔄 批次操作完畢，正在重新掃描系統套件...")
                        import asyncio
                        asyncio.create_task(self.main_app.load_installed_packages())

                    self.main_app.push_screen(CommandTerminalScreen(final_cmd), after_terminal_closed)
                    self.dismiss()
                    
                else:
                    import os, shutil, subprocess
                    signal_file = "/tmp/lpm_refresh.tmp"
                    if os.path.exists(signal_file):
                        try: os.remove(signal_file)
                        except Exception: pass

                    terminal_cmd = None
                    for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                        if shutil.which(term) is not None:
                            terminal_cmd = term
                            break
                    
                    bash_cmd = f"{final_cmd}; touch {signal_file}; read -p '執行完畢，按 [Enter] 關閉視窗...'"
                    
                    try:
                        if terminal_cmd == "gnome-terminal":
                            subprocess.Popen(["gnome-terminal", "--", "bash", "-c", bash_cmd])
                        elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                            subprocess.Popen([terminal_cmd, "-e", f"bash -c \"{bash_cmd}\""])
                        else:
                            subprocess.Popen(["bash", "-c", bash_cmd])
                    except Exception as e:
                        self.main_app.notify(f"❌ 啟動批次程序失敗: {str(e)}", severity="error")

                    self.dismiss()
                    
                    async def exact_refresh():
                        for _ in range(600):
                            if os.path.exists(signal_file):
                                try: os.remove(signal_file)
                                except Exception: pass
                                
                                try:
                                    await self.main_app.load_installed_packages()
                                    self.main_app.notify("📦 偵測到任務完成，套件清單已即時同步！")
                                except Exception: pass
                                break
                            import asyncio
                            await asyncio.sleep(1)
                    
                    import asyncio
                    asyncio.create_task(exact_refresh())

            preferred = getattr(self.main_app, "preferred_mgr", "apt")
            self.main_app.push_screen(SearchLoadingModal(self.main_app, raw_packages, preferred, is_install), after_search)