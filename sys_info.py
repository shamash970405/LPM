import shutil
import asyncio
import subprocess

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
                "install": "sudo snap install {pkgs} || (echo '\n⚠️ LPM 偵測到套件需要 Classic 沙盒權限，正在自動為您重試...' && sudo snap install {pkgs} --classic)",
                
                # ✨ 升級解除安裝：如果一般移除失敗，就用 --purge 強制暴力清道夫！
                "uninstall": "sudo snap remove {pkgs} || (echo '\n⚠️ 偵測到殘留的套件設定檔，正在啟動強制清除...' && sudo snap remove {pkgs} --purge)",
                
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
    
    # ================= 📦 底層套件掃描引擎 =================
    async def scan_all_packages(self) -> list:
        """🚀 平行發動所有可用的套件管理員進行掃描，並統整成乾淨的清單回傳"""
        packages = []
        tasks = []
        
        if self.status.get("pacman"): tasks.append(self._scan_pacman(packages))
        if self.status.get("apt"): tasks.append(self._scan_apt(packages))
        if self.status.get("snap"): tasks.append(self._scan_snap(packages))
        if self.status.get("flatpak"): tasks.append(self._scan_flatpak(packages))

        if tasks:
            await asyncio.gather(*tasks)
            
        return packages

    async def _scan_pacman(self, packages):
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
                        packages.append({"manager": "pacman", "name": name, "version": version, "size": display_size})
        except Exception: pass

    async def _scan_apt(self, packages):
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
                        packages.append({"manager": "apt", "name": name, "version": version, "size": display_size})
        except Exception: pass

    async def _scan_snap(self, packages):
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
                        # ✨ 你的幽靈防護網在這裡！
                        if version == "-" or "broken" in line.lower():
                            continue
                        packages.append({"manager": "snap", "name": name, "version": version, "size": "沙盒管理"})
        except Exception: pass

    async def _scan_flatpak(self, packages):
        try:
            process = await asyncio.create_subprocess_exec(
                "flatpak", "list", "--columns=application,version", 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                for line in lines:
                    if not line.strip(): continue
                    parts = line.split("\t")
                    if len(parts) >= 1:
                        name = parts[0].strip()
                        version = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "未知"
                        packages.append({"manager": "flatpak", "name": name, "version": version, "size": "沙盒管理"})
        except Exception: pass