import os
import sys
import shutil
import random
import asyncio
import platform
import subprocess
from textual import on
from rich.text import Text
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, RadioSet, RadioButton, Button, Static, Tree, RichLog, Markdown

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
    """跨通路搜尋並提供樹狀選擇列表的載入畫面 (支援超大預覽框與手動結算)"""
    
    CSS = """
    SearchLoadingModal { align: center middle; background: rgba(0, 0, 0, 0.85); }
    /* ✨ 將視窗拉高至 90%，讓預覽框有巨大的展示空間 */
    #loader-container { width: 75; height: 90%; background: #1f2335; border: thick #7aa2f7; padding: 2 4; }
    
    /* 動畫與日誌區塊 */
    #anim-section { width: 100%; height: 100%; align: center top; }
    #flag-loader { height: auto; content-align: center middle; margin-bottom: 1; }
    #loader-status { height: auto; text-align: center; color: #e0af68; text-style: bold; margin-bottom: 1; }
    
    /* ✨ 預覽框自動撐滿剩餘空間 (1fr) */
    #search-log { height: 1fr; border: solid #565f89; background: #16161e; margin-bottom: 1; padding: 0 1; }
    
    /* ✨ 將按鈕統一放置在右下角 */
    #action-box { width: 100%; height: auto; align: right middle; }
    #btn-skip { display: none; margin-right: 1; }
    #btn-view-report { display: none; }
    
    /* 樹狀列表區域 */
    #tree-section { display: none; width: 100%; height: 100%; margin-top: 0; }
    #result-tree { height: 1fr; border: solid #565f89; background: #1a1b26; margin-bottom: 1; }
    #tree-btn-box { height: auto; align: right middle; }
    #tree-cancel { margin-right: 2; }
    """

    def __init__(self, main_app, raw_packages, preferred_mgr, is_install):
        super().__init__()
        self.main_app = main_app
        self.raw_packages = raw_packages
        self.preferred_mgr = preferred_mgr
        self.is_install = is_install
        self.all_leaf_nodes = [] 
        self.resolved_dict = {}  

    def compose(self):
        with Vertical(id="loader-container"):
            # 上半部：MTF 旗幟、狀態字、巨大預覽日誌與「右下角控制按鈕」
            with Vertical(id="anim-section"):
                yield TransFlagLoader(id="flag-loader")
                yield Label("尋找中.....wait a minute\n準備啟動引擎...", id="loader-status")
                yield RichLog(id="search-log", markup=True) 
                
                with Horizontal(id="action-box"):
                    yield Button("⏳ 略過剩餘搜尋", id="btn-skip", variant="warning")
                    yield Button("🏁 結束並查看報告", id="btn-view-report", variant="success")
            
            # 下半部：隱藏的樹狀結算清單
            with Vertical(id="tree-section"):
                yield Label("🔍 [bold #7aa2f7]批次解析報告[/] (可勾選所需項目)：", classes="section-title")
                yield Tree("📦 跨通路搜尋結果", id="result-tree")
                with Horizontal(id="tree-btn-box"):
                    yield Button("取消", id="tree-cancel", variant="error")
                    yield Button("確認執行 🚀", id="tree-confirm", variant="success")

    async def on_mount(self):
        self.loader = self.query_one("#flag-loader")
        self.status_label = self.query_one("#loader-status")
        self.mgrs = ["apt", "snap", "flatpak"]
        
        if self.is_install:
            self.search_process_task = asyncio.create_task(self.run_search_process(self.raw_packages))
        else:
            self.search_process_task = asyncio.create_task(self.perform_uninstall())

    def update_progress(self):
        # 1. 處理上方旗幟進度條的動畫
        if self.loader.progress < 90:
            import random
            self.loader.progress += random.uniform(1, 3)
            
        # 2. 處理下方會呼吸的點點動畫
        # 初始化動畫狀態與點點數量
        if not hasattr(self, "dot_count"):
            self.dot_count = 1
            self.dot_growing = True

        # 根據目前狀態決定點點要變長還是變短 (範圍 1~6 個點)
        if self.dot_growing:
            self.dot_count += 1
            if self.dot_count >= 6:
                self.dot_growing = False
        else:
            self.dot_count -= 1
            if self.dot_count <= 1:
                self.dot_growing = True

        # 產生變動的點點字串
        animated_dots = "." * self.dot_count
        
        # 3. 更新標籤文字 (加入你專屬的迷因標語)
        self.status_label.update(f"正在尋找.....wait a minute who are you{animated_dots}")
        
    def show_skip_btn(self):
        self.query_one("#btn-skip").styles.display = "block"

    async def fetch_all_managers(self, kw):
        sys_status = self.main_app.sys_status
        tasks = []
        
        async def fetch_candidates(mgr_name, keyword):
            import shutil
            try:
                # 🛡️ 安全過濾與連字號轉換：將 "google chro" 轉為 "google-chro"
                keyword = keyword.replace("'", "")
                kw_lower = keyword.lower().strip()
                kw_hyphen = kw_lower.replace(" ", "-")
                
                # 🚀 放大終端機抓取量到 50 筆，避免真正的套件被截斷
                fetch_limit = 50
                out_names = []
                
                if mgr_name == "apt":
                    cmd = shutil.which("apt-cache") or "apt-cache"
                    proc = await asyncio.create_subprocess_shell(f"{cmd} search --names-only '{keyword}' 2>/dev/null | awk '{{print $1}}' | head -n {fetch_limit}", stdout=asyncio.subprocess.PIPE)
                    out, _ = await proc.communicate()
                    out_names = [n for n in out.decode('utf-8', errors='ignore').strip().split('\n') if n]
                    
                elif mgr_name == "snap":
                    cmd = shutil.which("snap") or "snap"
                    proc = await asyncio.create_subprocess_shell(f"{cmd} find '{keyword}' 2>/dev/null | awk 'NR>1 {{print $1}}' | head -n {fetch_limit}", stdout=asyncio.subprocess.PIPE)
                    out, _ = await proc.communicate()
                    out_names = [n for n in out.decode('utf-8', errors='ignore').strip().split('\n') if n and "No" not in n]
                    
                elif mgr_name == "flatpak":
                    cmd = shutil.which("flatpak") or "flatpak"
                    proc = await asyncio.create_subprocess_shell(f"{cmd} search --columns=application '{keyword}' 2>/dev/null | head -n {fetch_limit}", stdout=asyncio.subprocess.PIPE)
                    out, _ = await proc.communicate()
                    out_names = [n for n in out.decode('utf-8', errors='ignore').strip().split('\n') if n and "Application" not in n and "---" not in n]
                    
                elif mgr_name == "pacman":
                    cmd = shutil.which("pacman") or "pacman"
                    proc = await asyncio.create_subprocess_shell(f"{cmd} -Ssq '{keyword}' 2>/dev/null | head -n {fetch_limit}", stdout=asyncio.subprocess.PIPE)
                    out, _ = await proc.communicate()
                    out_names = [n for n in out.decode('utf-8', errors='ignore').strip().split('\n') if n]
                    
                elif mgr_name == "yay":
                    cmd = shutil.which("yay") or "yay"
                    proc = await asyncio.create_subprocess_shell(f"{cmd} -Ssq '{keyword}' 2>/dev/null | head -n {fetch_limit}", stdout=asyncio.subprocess.PIPE)
                    out, _ = await proc.communicate()
                    out_names = [n for n in out.decode('utf-8', errors='ignore').strip().split('\n') if n]
                    
                elif mgr_name == "paru":
                    cmd = shutil.which("paru") or "paru"
                    proc = await asyncio.create_subprocess_shell(f"{cmd} -Ssq '{keyword}' 2>/dev/null | head -n {fetch_limit}", stdout=asyncio.subprocess.PIPE)
                    out, _ = await proc.communicate()
                    out_names = [n for n in out.decode('utf-8', errors='ignore').strip().split('\n') if n]
                
                # 🧠 核心精準度演算法：幫抓出來的套件打分數 (越小越優先)
                def rank_pkg(pkg):
                    pkg_l = pkg.lower()
                    # 階級 0: 完全命中
                    if pkg_l == kw_hyphen or pkg_l == kw_lower: return 0
                    # 階級 1: 開頭完全吻合 (例如 google-chrome)
                    if pkg_l.startswith(kw_hyphen) or pkg_l.startswith(kw_lower): return 1
                    # 階級 2: 名字裡面包含連字號關鍵字
                    if kw_hyphen in pkg_l: return 2
                    # 階級 3: 包含以空白分割的所有單字 (google, chro)
                    parts = kw_lower.split()
                    if all(p in pkg_l for p in parts): return 3
                    # 階級 4: 其他靠描述混進來的雜魚
                    return 4

                # 依據精準度排序，然後只取最前面的 8 個精華！
                sorted_names = sorted(out_names, key=rank_pkg)
                return (mgr_name, sorted_names[:8])

            except Exception: 
                pass 
            return (mgr_name, [])

        # 任務派發
        if sys_status.get("apt"): tasks.append(fetch_candidates("apt", kw))
        if sys_status.get("snap"): tasks.append(fetch_candidates("snap", kw))
        if sys_status.get("flatpak"): tasks.append(fetch_candidates("flatpak", kw))
        
        # Arch 專屬防禦
        if sys_status.get("yay"): tasks.append(fetch_candidates("yay", kw))
        elif sys_status.get("paru"): tasks.append(fetch_candidates("paru", kw))
        elif sys_status.get("pacman"): tasks.append(fetch_candidates("pacman", kw))

        fetched_results = await asyncio.gather(*tasks)
        return {mgr: names for mgr, names in fetched_results if names}

        # 任務派發
        if sys_status.get("apt"): tasks.append(fetch_candidates("apt", kw))
        if sys_status.get("snap"): tasks.append(fetch_candidates("snap", kw))
        if sys_status.get("flatpak"): tasks.append(fetch_candidates("flatpak", kw))
        
        # ✨ Arch 專屬防禦
        if sys_status.get("yay"): tasks.append(fetch_candidates("yay", kw))
        elif sys_status.get("paru"): tasks.append(fetch_candidates("paru", kw))
        elif sys_status.get("pacman"): tasks.append(fetch_candidates("pacman", kw))

        fetched_results = await asyncio.gather(*tasks)
        return {mgr: names for mgr, names in fetched_results if names}

    async def run_search_process(self, input_packages):
        self.query_one("#anim-section").styles.display = "block"
        self.query_one("#tree-section").styles.display = "none"
        self.query_one("#btn-skip").styles.display = "none"
        self.query_one("#btn-view-report").styles.display = "none"
        self.loader.progress = 0
        self.mgr_idx = 0

        log_view = self.query_one("#search-log", RichLog)
        log_view.clear()

        self.anim_timer = self.set_interval(0.1, self.update_progress)
        self.skip_timer = self.set_timer(10.0, self.show_skip_btn)

        semaphore = asyncio.Semaphore(15)

        async def safe_fetch(kw):
            async with semaphore:
                res = await self.fetch_all_managers(kw)
                has_found = False
                best_mgr = None
                
                if res:
                    if self.preferred_mgr in res and res[self.preferred_mgr]:
                        best_mgr = self.preferred_mgr
                        has_found = True
                    else:
                        for m in ["apt", "snap", "flatpak", "pacman", "yay", "dnf", "zypper", "apk"]:
                            if m in res and res[m]:
                                best_mgr = m
                                has_found = True
                                break
                
                if has_found:
                    log_view.write(f"[bold #9ece6a]✅ [{best_mgr}][/] {kw}")
                else:
                    log_view.write(f"[bold #ff5555]❌ [未找到][/] {kw}")
                    
                return kw, res

        keywords_to_search = []
        for item in input_packages:
            if isinstance(item, dict):
                kw = item["name"]
                mgr = item.get("mgr")
                if mgr:
                    self.resolved_dict.setdefault(kw, {}).setdefault(mgr, []).append(kw)
                    log_view.write(f"[bold #9ece6a]✅ [VIP保送: {mgr}][/] {kw}")
                else:
                    keywords_to_search.append(kw)
            else:
                keywords_to_search.append(item)

        self.search_tasks = {}
        for kw in keywords_to_search:
            self.search_tasks[kw] = asyncio.create_task(safe_fetch(kw))

        if self.search_tasks:
            try:
                await asyncio.wait(self.search_tasks.values(), return_when=asyncio.ALL_COMPLETED)
            except asyncio.CancelledError:
                pass 

        self.skip_timer.stop()
        self.anim_timer.stop()
        self.loader.progress = 100

        unresolved = []
        for kw, task in self.search_tasks.items():
            if task.done() and not task.cancelled():
                try:
                    task_kw, res = task.result()
                    has_any = False
                    if res:
                        for found_mgr, found_pkgs in res.items():
                            if found_pkgs:
                                self.resolved_dict.setdefault(kw, {}).setdefault(found_mgr, []).extend(found_pkgs)
                                has_any = True
                    if not has_any: unresolved.append(kw)
                except Exception:
                    unresolved.append(kw)
            else:
                unresolved.append(kw)

        # ✨ 關鍵改變：不自動跳轉！將結果存起來，顯示「結束並查看報告」按鈕
        self.final_unresolved = unresolved
        self.query_one("#btn-skip").styles.display = "none"
        self.query_one("#btn-view-report").styles.display = "block"
        self.query_one("#loader-status").update("[bold #9ece6a]✅ 搜尋任務已結束！請點擊右下角查看報告。[/]")

    def build_tree_ui(self, unresolved):
        self.query_one("#anim-section").styles.display = "none"
        self.query_one("#tree-section").styles.display = "block"
        
        tree = self.query_one("#result-tree")
        tree.clear()
        self.all_leaf_nodes = []

        root_success = tree.root.add("✅ [bold #9ece6a]已解析成功[/] (勾選以直接安裝)", expand=True)
        if not self.resolved_dict: root_success.add_leaf("   (無)")
            
        for kw, mgrs in self.resolved_dict.items():
            kw_node = root_success.add(f"🔑 關鍵字: [bold #e0af68]{kw}[/]", expand=True)
            
            best_mgr = self.preferred_mgr if self.preferred_mgr in mgrs and mgrs[self.preferred_mgr] else None
            if not best_mgr:
                for m in ["apt", "snap", "flatpak", "pacman", "yay", "dnf", "zypper", "apk"]:
                    if m in mgrs and mgrs[m]:
                        best_mgr = m
                        break

            for mgr, pkgs in mgrs.items():
                if not pkgs: continue
                mgr_node = kw_node.add(f"📂 {mgr.upper()} 來源", expand=True)
                for pkg in pkgs:
                    leaf = mgr_node.add_leaf(f"[ ] {pkg}", data={"type": "install", "mgr": mgr, "display": pkg, "selected": False})
                    self.all_leaf_nodes.append(leaf)
                    
                    if pkg == kw and mgr == best_mgr:
                        leaf.data["selected"] = True
                        leaf.set_label(f"[bold #9ece6a][X] {pkg}[/]")

        root_failed = tree.root.add("⏳ [bold #ff5555]未解析 / 尋找逾時[/] (勾選以重新解析)", expand=True)
        if not unresolved: root_failed.add_leaf("   (無)")
            
        for kw in unresolved:
            leaf = root_failed.add_leaf(f"[ ] {kw}", data={"type": "reparse", "display": kw, "selected": False})
            self.all_leaf_nodes.append(leaf)

        tree.root.expand()

    async def perform_uninstall(self):
        import asyncio
        
        self.query_one("#anim-section").styles.display = "block"
        self.query_one("#tree-section").styles.display = "none"
        self.query_one("#btn-skip").styles.display = "none"
        self.query_one("#btn-view-report").styles.display = "none"
        self.anim_timer = self.set_interval(0.1, self.update_progress)

        await asyncio.sleep(0.5)
        
        # ✨ 核心修復：直接向主程式的「卸載指令大一統引擎」索取指令！
        # self.raw_packages 就是你在輸入框打的套件陣列
        final_cmd = self.main_app.generate_uninstall_cmd_from_names(self.raw_packages)
        
        if hasattr(self, "anim_timer"):
            self.anim_timer.stop()
            
        self.loader.progress = 100
        self.status_label.update("✅ 跨通路卸載指令建構完畢！")
        
        await asyncio.sleep(0.6)
        self.dismiss(final_cmd)

    @on(Tree.NodeSelected, "#result-tree")
    def toggle_node(self, event: Tree.NodeSelected):
        node = event.node
        if node.data is not None and isinstance(node.data, dict) and "selected" in node.data:
            data = node.data
            data["selected"] = not data["selected"]
            
            if data["selected"]:
                node.set_label(f"[bold #9ece6a][X] {data['display']}[/]")
            else:
                node.set_label(f"[ ] {data['display']}")

    @on(Button.Pressed)
    def handle_buttons(self, event: Button.Pressed):
        # ✨ 按鈕邏輯更新
        if event.button.id == "btn-skip":
            for task in getattr(self, "search_tasks", {}).values():
                if not task.done():
                    task.cancel()
                    
        elif event.button.id == "btn-view-report":
            # 點擊報告按鈕後，才建立並顯示樹狀圖！
            self.build_tree_ui(getattr(self, "final_unresolved", []))
            
        elif event.button.id == "tree-cancel":
            self.dismiss(None)
            
        elif event.button.id == "tree-confirm":
            selected_install = {}
            selected_reparse = []

            for leaf in getattr(self, "all_leaf_nodes", []):
                if leaf.data.get("selected"):
                    if leaf.data.get("type") == "install":
                        selected_install.setdefault(leaf.data["mgr"], []).append(leaf.data["display"])
                    elif leaf.data.get("type") == "reparse":
                        selected_reparse.append(leaf.data["display"])
            
            if selected_reparse:
                self.main_app.notify(f"🔄 收到指令！正在重新解析 {len(selected_reparse)} 個套件...")
                import asyncio
                asyncio.create_task(self.run_search_process(selected_reparse))
                return
            
            if not selected_install:
                self.main_app.notify("⚠️ 請至少勾選一個要處理的套件！", severity="warning")
                return
            
            # ✨ 這裡就是關鍵！全面呼叫 sys_info 大腦來幫我們產生完美的安裝指令！
            cmd_list = []
            for mgr, pkgs in selected_install.items():
                cmd_list.append(self.main_app.sys_info.build_command(mgr=mgr, action="install", pkgs=pkgs))

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

                # 🚀 透過主程式的大一統引擎發射！
                self.main_app.execute_and_refresh(final_cmd, "🔮 批次操作完成，系統套件已同步！")
                self.dismiss()

            preferred = getattr(self.main_app, "preferred_mgr", "apt")
            self.main_app.push_screen(SearchLoadingModal(self.main_app, raw_packages, preferred, is_install), after_search)

class SysInfoPreviewModal(ModalScreen):
    """顯示並自動複製系統資訊的彈出視窗"""
    
    # 專屬的 CSS 排版，讓視窗置中且美觀
    CSS = """
    SysInfoPreviewModal {
        align: center middle;
    }
    #sys_info_dialog {
        width: 60%;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }
    #sys_info_dialog .buttons {
        width: 100%;
        align: center middle;
        margin-top: 1;
    }
    """

    def __init__(self):
        super().__init__()
        # 初始化時就先將系統資訊收集完畢
        self.sys_info_text = self.generate_sys_info()

    def generate_sys_info(self):
        """蒐集四大核心情報"""
        # 嘗試讀取 Linux 發行版名稱 (例如 Ubuntu 26.04)
        distro_name = "Unknown Linux"
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro_name = line.split("=")[1].strip().strip('"')
                        break
        except Exception:
            pass

        # 組合 Markdown 格式的報告
        return f"""### 🐛 LPM 系統除錯資訊 (Debug Info)
- **作業系統**: {distro_name}
- **核心版本**: {platform.release()}
- **Python 版本**: {sys.version.split()[0]}
- **執行環境**: {'AppImage 獨立封裝' if 'APPIMAGE' in os.environ else '本地原始碼'}
- **終端機類型**: {os.environ.get('TERM', 'Unknown')}
"""

    def compose(self):
        """構建 UI 畫面"""
        with Vertical(id="sys_info_dialog"):
            yield Markdown(self.sys_info_text)
            with Horizontal(classes="buttons"):
                yield Button("✅ 資訊已複製，關閉視窗", variant="success", id="btn_close_info")

    def on_mount(self):
        """視窗掛載完成時，自動執行剪貼簿複製與通知"""
        try:
            # 呼叫 Textual 內建的剪貼簿 API
            self.app.copy_to_clipboard(self.sys_info_text)
            self.app.notify("系統資訊已成功複製到剪貼簿！可以直接貼給開發者囉！", title="📋 複製成功")
        except Exception as e:
            # 防呆機制：如果使用者的 Linux 缺少 xclip/wl-clipboard 等底層剪貼簿工具
            self.app.notify("自動複製失敗，請使用滑鼠手動圈選文字複製。", severity="warning")

    def on_button_pressed(self, event: Button.Pressed):
        """處理按鈕點擊事件"""
        if event.button.id == "btn_close_info":
            self.app.pop_screen()