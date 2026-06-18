import os
import shutil
import asyncio
import subprocess

from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Input, RadioSet, RadioButton, Button

# 🚀 獨立模組：批次大量安裝/刪除的彈出式魔法視窗
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

   # ✨ 加上 async 讓按鈕可以執行非同步的搜尋等待
    async def on_button_pressed(self, event: Button.Pressed) -> None:
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
            
            # 鎖定按鈕避免重複點擊
            self.query_one("#batch-confirm").disabled = True
            self.query_one("#batch-cancel").disabled = True

            import asyncio
            resolved_tasks = {} # 記錄 [管理器] -> [套件名清單]
            
            # 讀取使用者偏好與系統現有環境
            preferred = getattr(self.main_app, "preferred_mgr", "apt")
            sys_status = self.main_app.sys_status

            if is_install:
                self.main_app.notify("🔍 啟動智能搜尋引擎，正在跨通路精準比對套件名稱...", timeout=4)
                
                for keyword in raw_packages:
                    results = {}
                    
                    # 1. 🔍 APT 深度搜尋 (使用 awk 精準擷取第一欄名稱)
                    if sys_status.get("apt"):
                        proc = await asyncio.create_subprocess_shell(
                            f"apt-cache search --names-only '^{keyword}' | awk 'NR==1 {{print $1}}'",
                            stdout=asyncio.subprocess.PIPE
                        )
                        out, _ = await proc.communicate()
                        name = out.decode().strip()
                        if not name: # 如果開頭沒有，放寬搜尋
                            proc = await asyncio.create_subprocess_shell(
                                f"apt-cache search --names-only '{keyword}' | awk 'NR==1 {{print $1}}'",
                                stdout=asyncio.subprocess.PIPE
                            )
                            out, _ = await proc.communicate()
                            name = out.decode().strip()
                        if name: results["apt"] = name

                    # 2. 🔍 Snap 搜尋
                    if sys_status.get("snap"):
                        proc = await asyncio.create_subprocess_shell(
                            f"snap find '{keyword}' 2>/dev/null | awk 'NR==2 {{print $1}}'",
                            stdout=asyncio.subprocess.PIPE
                        )
                        out, _ = await proc.communicate()
                        name = out.decode().strip()
                        if name and "No" not in name: results["snap"] = name

                    # 3. 🔍 Flatpak 搜尋 (直接請求 application ID)
                    if sys_status.get("flatpak"):
                        proc = await asyncio.create_subprocess_shell(
                            f"flatpak search --columns=application '{keyword}' 2>/dev/null | awk 'NR==1 {{print $1}}'",
                            stdout=asyncio.subprocess.PIPE
                        )
                        out, _ = await proc.communicate()
                        name = out.decode().strip()
                        if name: results["flatpak"] = name

                    # 🧠 邏輯裁決中心 (父親教導的嚴謹守則)
                    # 如果使用者偏好的管理員有找到，優先用它；若無，依次 fallback 給 apt -> snap -> flatpak
                    if preferred in results:
                        found_mgr, found_name = preferred, results[preferred]
                    elif "apt" in results:
                        found_mgr, found_name = "apt", results["apt"]
                    elif "snap" in results:
                        found_mgr, found_name = "snap", results["snap"]
                    elif "flatpak" in results:
                        found_mgr, found_name = "flatpak", results["flatpak"]
                    else:
                        # 如果全世界都找不到，就維持原字串丟給預設管理員去報錯
                        found_mgr, found_name = preferred if sys_status.get(preferred) else "apt", keyword
                    
                    self.main_app.notify(f"💡 `{keyword}` 已解析為 [{found_mgr}] 的 `{found_name}`")
                    resolved_tasks.setdefault(found_mgr, []).append(found_name)

            else:
                # 🗑️ 解除安裝：直接套用原始字串並使用偏好管理員 (避免模糊搜尋誤刪)
                self.main_app.notify("⚡ 正在建構批次解除安裝指令...")
                fallback_mgr = "apt"
                for test_mgr in ["pacman", "yay", "dnf", "zypper", "apk"]:
                    if sys_status.get(test_mgr): fallback_mgr = test_mgr; break
                
                mgr = preferred if sys_status.get(preferred) else fallback_mgr
                resolved_tasks[mgr] = raw_packages

            # 🛠️ 組合終極指令 (支援多重通路串聯)
            cmd_list = []
            for mgr, pkgs in resolved_tasks.items():
                pkgs_str = " ".join(pkgs)
                if is_install:
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

            # --- 下方保留你超棒的 SSH 內建終端機判斷邏輯 ---
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
                        await asyncio.sleep(1)
                
                asyncio.create_task(exact_refresh())