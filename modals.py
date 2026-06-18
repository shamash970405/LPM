import os
import shutil
import asyncio
import subprocess
import random

from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, RadioSet, RadioButton, Button, Static
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
        
        # MTF 旗幟標準色
        self.flag_colors = [
            "#5BCEFA", # 淺藍色
            "#F5A9B8", # 粉紅色
            "#FFFFFF", # 白色
            "#F5A9B8", # 粉紅色
            "#5BCEFA"  # 淺藍色
        ]
        self.bg_color = "#1a1b26" # 隱藏時的底色，與你的背景融為一體

    def render(self):
        text = Text()
        show_count = int((self.progress / 100) * self.total_blocks)
        visible_indices = set(self.indices[:show_count])
        
        for r in range(self.rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                # ✨ 這裡也要記得改成 self.flag_colors 喔！
                color = self.flag_colors[r] if idx in visible_indices else self.bg_color
                text.append("██", style=color)
            if r < self.rows - 1:
                text.append("\n")
        return text

# ================= 🔍 獨立的搜尋等待動畫視窗 =================
class SearchLoadingModal(ModalScreen):
    """跨通路搜尋時彈出的專屬載入畫面"""
    
    CSS = """
    SearchLoadingModal { align: center middle; background: rgba(0, 0, 0, 0.85); }
    #loader-container { width: 50; height: auto; background: #1f2335; border: thick #7aa2f7; padding: 2 4; align: center middle; }
    #flag-loader { content-align: center middle; margin-bottom: 2; }
    #loader-status { text-align: center; color: #e0af68; text-style: bold; }
    """

    def __init__(self, main_app, raw_packages, preferred_mgr, is_install):
        super().__init__()
        self.main_app = main_app
        self.raw_packages = raw_packages
        self.preferred_mgr = preferred_mgr
        self.is_install = is_install

    def compose(self):
        with Vertical(id="loader-container"):
            yield TransFlagLoader(id="flag-loader")
            yield Label("尋找中.....wait a minute\n準備啟動引擎...", id="loader-status")

    async def on_mount(self):
        self.loader = self.query_one("#flag-loader")
        self.status_label = self.query_one("#loader-status")
        
        # 準備輪播顯示的管理員名稱
        self.mgrs = ["apt", "snap", "flatpak"]
        self.mgr_idx = 0
        
        # 啟動文字與旗幟的假動畫循環 (每 0.1 秒刷新一次)
        self.anim_timer = self.set_interval(0.1, self.update_progress)
        
        # 啟動真實的背景平行搜尋任務
        self.search_task = asyncio.create_task(self.perform_search())

    def update_progress(self):
        # 讓旗幟進度條卡在 90%，直到真實搜尋完成才填滿
        if self.loader.progress < 90:
            self.loader.progress += random.uniform(1, 3)
            
        # 輪播顯示正在尋找的管理員
        self.mgr_idx += 1
        current_mgr = self.mgrs[self.mgr_idx % len(self.mgrs)]
        self.status_label.update(f"尋找中.....wait a minute\n正在尋找 {current_mgr}")

    async def perform_search(self):
        resolved_tasks = {}
        sys_status = self.main_app.sys_status

        if self.is_install:
            async def fetch_pkg(mgr_name, kw):
                try:
                    if mgr_name == "apt":
                        proc = await asyncio.create_subprocess_shell(
                            f"apt-cache search --names-only '^{kw}' | awk 'NR==1 {{print $1}}'", stdout=asyncio.subprocess.PIPE)
                        out, _ = await proc.communicate()
                        name = out.decode().strip()
                        if not name:
                            proc = await asyncio.create_subprocess_shell(
                                f"apt-cache search --names-only '{kw}' | awk 'NR==1 {{print $1}}'", stdout=asyncio.subprocess.PIPE)
                            out, _ = await proc.communicate()
                            name = out.decode().strip()
                        return ("apt", name)
                    elif mgr_name == "snap":
                        proc = await asyncio.create_subprocess_shell(
                            f"snap find '{kw}' 2>/dev/null | awk 'NR==2 {{print $1}}'", stdout=asyncio.subprocess.PIPE)
                        out, _ = await proc.communicate()
                        name = out.decode().strip()
                        return ("snap", name if name and "No" not in name else "")
                    elif mgr_name == "flatpak":
                        proc = await asyncio.create_subprocess_shell(
                            f"flatpak search --columns=application '{kw}' 2>/dev/null | awk 'NR==1 {{print $1}}'", stdout=asyncio.subprocess.PIPE)
                        out, _ = await proc.communicate()
                        name = out.decode().strip()
                        return ("flatpak", name)
                except Exception: pass
                return (mgr_name, "")

            for keyword in self.raw_packages:
                tasks = []
                if sys_status.get("apt"): tasks.append(fetch_pkg("apt", keyword))
                if sys_status.get("snap"): tasks.append(fetch_pkg("snap", keyword))
                if sys_status.get("flatpak"): tasks.append(fetch_pkg("flatpak", keyword))

                fetched_results = await asyncio.gather(*tasks)
                results = {mgr: name for mgr, name in fetched_results if name}

                # 偏好裁決
                if self.preferred_mgr in results:
                    found_mgr, found_name = self.preferred_mgr, results[self.preferred_mgr]
                elif "apt" in results: found_mgr, found_name = "apt", results["apt"]
                elif "snap" in results: found_mgr, found_name = "snap", results["snap"]
                elif "flatpak" in results: found_mgr, found_name = "flatpak", results["flatpak"]
                else: found_mgr, found_name = self.preferred_mgr if sys_status.get(self.preferred_mgr) else "apt", keyword
                
                resolved_tasks.setdefault(found_mgr, []).append(found_name)
        else:
            # 移除模式不需要久候，稍微等一下讓動畫閃過即可
            await asyncio.sleep(0.5) 
            fallback_mgr = "apt"
            for test_mgr in ["pacman", "yay", "dnf", "zypper", "apk"]:
                if sys_status.get(test_mgr): fallback_mgr = test_mgr; break
            mgr = self.preferred_mgr if sys_status.get(self.preferred_mgr) else fallback_mgr
            resolved_tasks[mgr] = self.raw_packages

        # 組合指令
        cmd_list = []
        for mgr, pkgs in resolved_tasks.items():
            pkgs_str = " ".join(pkgs)
            if self.is_install:
                if mgr == "apt": cmd_list.append(f"sudo apt install -y {pkgs_str}")
                elif mgr == "snap": cmd_list.append(f"sudo snap install {pkgs_str}")
                elif mgr == "flatpak": cmd_list.append(f"flatpak install -y {pkgs_str}")
                elif mgr in ["pacman", "yay"]: cmd_list.append(f"sudo {mgr} -S --noconfirm {pkgs_str}")
                elif mgr == "dnf": cmd_list.append(f"sudo dnf install -y {pkgs_str}")
                elif mgr == "zypper": cmd_list.append(f"sudo zypper install -y {pkgs_str}")
                elif mgr == "apk": cmd_list.append(f"sudo apk add {pkgs_str}")
            else:
                if mgr == "apt": cmd_list.append(f"sudo apt purge -y {pkgs_str}")
                elif mgr == "snap": cmd_list.append(f"sudo snap remove {pkgs_str}")
                elif mgr == "flatpak": cmd_list.append(f"flatpak uninstall -y {pkgs_str}")
                elif mgr in ["pacman", "yay"]: cmd_list.append(f"sudo {mgr} -Rns --noconfirm {pkgs_str}")
                elif mgr == "dnf": cmd_list.append(f"sudo dnf remove -y {pkgs_str}")
                elif mgr == "zypper": cmd_list.append(f"sudo zypper remove -y {pkgs_str}")
                elif mgr == "apk": cmd_list.append(f"sudo apk del {pkgs_str}")

        final_cmd = " && ".join(cmd_list)

        # 🚀 搜尋結束！停止動畫，填滿旗幟並顯示成功
        self.anim_timer.stop()
        self.loader.progress = 100
        self.status_label.update(f"尋找中.....wait a minute\n✅ 解析完畢！")
        
        await asyncio.sleep(0.6) # 停留 0.6 秒讓使用者看清楚完整的旗幟
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
                yield RadioButton("📥 大量批次安裝", value=True, id="radio-install")
                yield RadioButton("🗑️ 大量批次移除", id="radio-uninstall")
            
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
            
            # 鎖定按鈕，防止重複點擊
            self.query_one("#batch-confirm").disabled = True
            self.query_one("#batch-cancel").disabled = True

            # ================= 接收動畫視窗回傳指令的處理回呼 =================
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

            # 🚀 推出專屬的旗幟載入視窗，代替原本的卡頓感！
            preferred = getattr(self.main_app, "preferred_mgr", "apt")
            self.main_app.push_screen(SearchLoadingModal(self.main_app, raw_packages, preferred, is_install), after_search)