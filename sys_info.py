import shutil

class SysInfo:
    """專門負責底層作業系統偵測、硬體環境、以及各發行版核心指令範本的獨立大腦"""
    
    def __init__(self):
        # 🌍 全自動硬體環境與套件管理員偵測
        self.status = {
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
            "brew": shutil.which("brew") is not None       # Homebrew
        }

        # 🎯 核心指令字典：將所有 Debian 與 Arch（及其他發行版）的底層指令集中收攏在此
        self._commands_template = {
            "apt": {
                "install": "sudo apt install -y {pkgs}",
                "uninstall": "sudo apt purge -y {pkgs}",
                "upgrade_single": "sudo apt --only-upgrade install -y {pkgs}",
                "system_upgrade": "sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y"
            },
            "pacman": {
                "install": "sudo pacman -S --noconfirm {pkgs}",
                "uninstall": "sudo pacman -Rns --noconfirm {pkgs}",
                "upgrade_single": "sudo pacman -S --needed --noconfirm {pkgs}",
                "system_upgrade": "sudo pacman -Syu --noconfirm && (pacman -Qdtq | sudo pacman -Rns - || true)"
            },
            "yay": {
                "install": "yay -S --noconfirm {pkgs}",
                "uninstall": "yay -Rns --noconfirm {pkgs}",
                "upgrade_single": "yay -S --needed --noconfirm {pkgs}",
                "system_upgrade": "yay -Syu --noconfirm && yay -Yc --noconfirm"
            },
            "paru": {
                "install": "paru -S --noconfirm {pkgs}",
                "uninstall": "paru -Rns --noconfirm {pkgs}",
                "upgrade_single": "paru -S --needed --noconfirm {pkgs}",
                "system_upgrade": "paru -Syu --noconfirm && paru -c --noconfirm"
            },
            "snap": {
                "install": "sudo snap install {pkgs}",
                "uninstall": "sudo snap remove {pkgs}",
                "upgrade_single": "sudo snap refresh {pkgs}",
                "system_upgrade": "sudo snap refresh"
            },
            "flatpak": {
                "install": "flatpak install -y {pkgs}",
                "uninstall": "flatpak uninstall -y {pkgs}",
                "upgrade_single": "flatpak update -y {pkgs}",
                "system_upgrade": "flatpak update -y"
            },
            "dnf": {
                "install": "sudo dnf install -y {pkgs}",
                "uninstall": "sudo dnf remove -y {pkgs}",
                "upgrade_single": "sudo dnf upgrade -y {pkgs}",
                "system_upgrade": "sudo dnf upgrade -y"
            },
            "zypper": {
                "install": "sudo zypper install -y {pkgs}",
                "uninstall": "sudo zypper remove -y {pkgs}",
                "upgrade_single": "sudo zypper update -y {pkgs}",
                "system_upgrade": "sudo zypper update -y"
            },
            "apk": {
                "install": "sudo apk add {pkgs}",
                "uninstall": "sudo apk del {pkgs}",
                "upgrade_single": "sudo apk add --upgrade {pkgs}",
                "system_upgrade": "sudo apk update && sudo apk upgrade"
            }
        }

    def get_os_name(self) -> str:
        """🐧 偵測目前的 Linux 發行版名稱"""
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=")[1].strip().strip('"')
            return "Unknown Linux"
        except Exception:
            return "Unknown OS"

    def get_disk_info(self) -> str:
        """💾 取得根目錄的硬碟容量狀態，並繪製文字進度條"""
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
        except Exception: 
            return "💾 系統容量狀態: 無法讀取"

    # ✨ 核心重構：讓主程式秒讀對應指令的智慧分流器
    def build_command(self, mgr: str, action: str, pkgs: list = None) -> str:
        """
        根據套件管理員、動作類型、套件列表，自動生成完美的 Linux 終端機指令。
        :param mgr: 套件管理員名稱 (例如 'apt', 'yay', 'flatpak')
        :param action: 動作類型 ('install', 'uninstall', 'upgrade_single', 'system_upgrade')
        :param pkgs: 套件名稱列表 (如 ['neofetch', 'git'])，全系統更新時可留空
        :return: 組合完畢的指令字串
        """
        mgr_lower = mgr.lower()
        if mgr_lower not in self._commands_template:
            return f"echo 'LPM 尚未支援 {mgr} 管理員'"
            
        templates = self._commands_template[mgr_lower]
        if action not in templates:
            return f"echo '未知的動作類型 {action}'"
            
        template = templates[action]
        
        # 如果是全系統更新，不需要套件參數，直接回傳範本
        if action == "system_upgrade":
            return template
            
        # 如果有傳入套件列表，自動用空白串聯並填入進去
        if pkgs:
            pkgs_str = " ".join(pkgs)
            return template.format(pkgs=pkgs_str)
            
        return "echo '指令建構失敗：缺漏套件名稱'"