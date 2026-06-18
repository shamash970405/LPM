import shutil

class SysInfo:
    """專門負責底層作業系統與硬體環境偵測的獨立引擎"""
    
    def __init__(self):
        # 🌍 終極全自動硬體環境偵測
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
            "brew": shutil.which("brew") is not None       # Homebrew (Linuxbrew)
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