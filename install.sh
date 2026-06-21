#!/bin/bash
# 遇到任何錯誤就立即停止執行，確保安裝安全
set -e

echo "🚀 [LPM 安裝引導] 開始全自動佈署環境..."

# 1. 建立標準安裝目錄 (將 /user/ 修正為 Linux 標準的 /usr/local/lpm)
INSTALL_DIR="/usr/local/lpm"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "📂 正在建立系統級安裝資料夾: $INSTALL_DIR ..."
    sudo mkdir -p "$INSTALL_DIR"
fi

# 2. 從你的 GitHub Releases 下載最新封裝好的 AppImage
# 💡 注意：請確保你已經把 LPM-x86_64.AppImage 上傳到 GitHub 的 Release 頁面
DOWNLOAD_URL="https://github.com/shamash970405/LPM/releases/latest/download/LPM-x86_64.AppImage"

echo "📥 正在從雲端獲取最新版 LPM 核心膠囊..."
sudo curl -L "$DOWNLOAD_URL" -o "$INSTALL_DIR/LPM-x86_64.AppImage"

# 3. 在系統資料夾內直接配置好執行權限
echo "🔑 正在自動配置安全執行權限..."
sudo chmod +x "$INSTALL_DIR/LPM-x86_64.AppImage"

# 4. 建立軟連結 (Symlink) 到全域環境變數路徑，這步就是「打 lpm 就能啟動」的魔法關鍵！
echo "🔗 正在將指令註冊進全域系統環境 (btop 模式)..."
sudo ln -sf "$INSTALL_DIR/LPM-x86_64.AppImage" /usr/local/bin/lpm

echo "--------------------------------------------------"
echo "🎉 [大成功] LPM 已經成功安裝到你的系統中！"
echo "👉 現在不論在任何路徑，只需輸入 'lpm' 即可直接開啟程式！"
echo "--------------------------------------------------"