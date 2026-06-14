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
            action_word = "安裝" if is_install else "解除安裝"
            
            self.main_app.notify(f"⚡ 正在建構 {len(raw_packages)} 個套件的批次{action_word}指令...")

            mgr = "apt"
            for test_mgr in ["pacman", "yay", "dnf", "zypper", "apk"]:
                if shutil.which(test_mgr) is not None:
                    mgr = test_mgr
                    break

            pkgs_str = " ".join(raw_packages)
            uninstall_cmd = ""
            
            if is_install:
                if mgr in ["pacman", "yay"]: uninstall_cmd = f"sudo {mgr} -S --noconfirm {pkgs_str}"
                elif mgr == "apt": uninstall_cmd = f"sudo apt install -y {pkgs_str}"
                elif mgr == "dnf": uninstall_cmd = f"sudo dnf install -y {pkgs_str}"
                elif mgr == "zypper": uninstall_cmd = f"sudo zypper install -y {pkgs_str}"
                elif mgr == "apk": uninstall_cmd = f"sudo apk add {pkgs_str}"
            else:
                if mgr in ["pacman", "yay"]: uninstall_cmd = f"sudo {mgr} -Rns --noconfirm {pkgs_str}"
                elif mgr == "apt": uninstall_cmd = f"sudo apt purge -y {pkgs_str}"
                elif mgr == "dnf": uninstall_cmd = f"sudo dnf remove -y {pkgs_str}"
                elif mgr == "zypper": uninstall_cmd = f"sudo zypper remove -y {pkgs_str}"
                elif mgr == "apk": uninstall_cmd = f"sudo apk del {pkgs_str}"

            # 💣 信號彈同步法
            signal_file = "/tmp/lpm_refresh.tmp"
            if os.path.exists(signal_file):
                try: os.remove(signal_file)
                except Exception: pass

            terminal_cmd = None
            for term in ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                if shutil.which(term) is not None:
                    terminal_cmd = term
                    break
            
            bash_cmd = f"{uninstall_cmd}; touch {signal_file}; read -p '執行完畢，按 [Enter] 關閉視窗...'"
            
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
                            self.main_app.notify("📦 偵測到批次任務完成，套件清單已即時同步！")
                        except Exception: pass
                        break
                    await asyncio.sleep(1)
            
            asyncio.create_task(exact_refresh())