#!/bin/bash

# ==============================================================================
# 🎨 ANSI 顏色定義
# ==============================================================================
GREEN='\033[0;32m'
LIGHT_BLUE='\033[1;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # 清除顏色

clear
echo -e "${LIGHT_BLUE}${BOLD}==================================================${NC}"
echo -e "${LIGHT_BLUE}${BOLD}🔍 [LPM 安裝助手] 正在初始化環境與相依設定...${NC}"
echo -e "${LIGHT_BLUE}${BOLD}==================================================${NC}"

# ==============================================================================
# 📍 核心邏輯 1：精準抓取用戶目前 git clone 下來的絕對路徑
# ==============================================================================
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
echo -e "${GREEN}✔ 成功定位專案實體路徑：${BOLD}${REPO_DIR}${NC}\n"

# ==============================================================================
# 🛠️ 核心邏輯 2：全自動偵測並安裝 Python 必備底層工具 (pip & venv)
# ==============================================================================
echo -e "${LIGHT_BLUE}⏳ 正在檢查系統 Python 底層工具 (pip 與 venv 模組)...${NC}"

# 檢查 pip 是否正常運作
if ! python3 -m pip --version &> /dev/null || ! python3 -c "import venv" &> /dev/null; then
    echo -e "${YELLOW}⚠️ 偵測到系統缺少必備的 python3-pip 或 venv 虛擬環境模組！${NC}"
    echo -e "${LIGHT_BLUE}🚀 正在自動偵測您的 Linux 發行版，並為您安裝相依套件...${NC}"
    
    if command -v apt &> /dev/null; then
        echo -e "📦 偵測為 Debian / Ubuntu 體系，正在透過 apt 安裝..."
        sudo apt update && sudo apt install -y python3-pip python3-venv
    elif command -v pacman &> /dev/null; then
        echo -e "📦 偵測為 Arch Linux 體系，正在透過 pacman 安裝..."
        sudo pacman -Sy --needed --noconfirm python-pip
    elif command -v dnf &> /dev/null; then
        echo -e "📦 偵測為 Fedora / RHEL 體系，正在透過 dnf 安裝..."
        sudo dnf install -y python3-pip
    elif command -v zypper &> /dev/null; then
        echo -e "📦 偵測為 openSUSE 體系，正在透過 zypper 安裝..."
        sudo zypper install -y python3-pip
    elif command -v apk &> /dev/null; then
        echo -e "📦 偵測為 Alpine Linux，正在透過 apk 安裝..."
        sudo apk add py3-pip
    elif command -v xbps-install &> /dev/null; then
        echo -e "📦 偵測為 Void Linux，正在透過 xbps 安裝..."
        sudo xbps-install -Sy python3-pip
    else
        echo -e "${RED}❌ 無法自動判斷發行版！請手動安裝 python3-pip 與 python3-venv 後再試。${NC}"
        exit 1
    fi
    echo -e "${GREEN}✔ 底層 Python 工具 (pip & venv) 安裝完畢！${NC}\n"
else
    echo -e "${GREEN}✔ 系統已具備完整 pip 與 venv 支援！${NC}\n"
fi

# ==============================================================================
# 🐍 核心邏輯 3：智能建立並進入 Python 虛擬環境 (Virtualenv)
# ==============================================================================
cd "$REPO_DIR" || exit 1

if [ -d ".venv" ]; then
    echo -e "${GREEN}✔ 偵測到現有虛擬環境 (.venv)，正在自動啟用...${NC}\n"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${GREEN}✔ 偵測到現有虛擬環境 (venv)，正在自動啟用...${NC}\n"
    source venv/bin/activate
else
    echo -e "${YELLOW}💡 正在為您建立獨立的 .venv 虛擬環境並安裝 requirements.txt 套件...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    
    # 升級 venv 內的 pip 並安裝相依套件
    python3 -m pip install --upgrade pip --quiet
    if [ -f "requirements.txt" ]; then
        echo -e "📦 正在下載並安裝 LPM 核心套件 (Textual, GenAI, Rich...)..."
        pip install -r requirements.txt
        echo -e "${GREEN}✔ 虛擬環境與 requirements.txt 套件建置完成！${NC}\n"
    fi
fi

# ==============================================================================
# ❓ 核心邏輯 4：互動式詢問用戶是否加入家目錄快捷鍵
# ==============================================================================
echo -e -n "${YELLOW}❓ 是否要在您的家目錄 (~/) 下建立 lpm.sh 快捷腳本？\n   下次只需在家目錄輸入 ./lpm.sh 即可直接啟動 (y/N): ${NC}"
read -r response

# 支援大寫 Y、小寫 y 或 yes
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    TARGET_SCRIPT="$HOME/lpm.sh"
    TARGET_SCRIPT_UPPER="$HOME/LPM.sh"
    
    echo -e "\n⏳ 正在產生自動啟動虛擬環境的快捷程式中..."

    # 自動生成 ~/lpm.sh (內含自動載入虛擬環境與啟動邏輯)
    cat << EOF > "$TARGET_SCRIPT"
#!/bin/bash
# ==============================================================================
# 🚀 LPM (Linux Package Manager) 快捷啟動腳本
# ==============================================================================
cd "$REPO_DIR" || exit 1

# 🧠 自動啟用 Python 虛擬環境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 執行 LPM 管理工具 (並將命令列參數完美透傳)
python3 manager.py "\$@"
EOF

    # 複製一份大寫版本並賦予執行權限
    cp "$TARGET_SCRIPT" "$TARGET_SCRIPT_UPPER"
    chmod +x "$TARGET_SCRIPT" "$TARGET_SCRIPT_UPPER"

    echo -e "${GREEN}==================================================${NC}"
    echo -e "${GREEN}🎉 恭喜！lpm.sh 快捷啟動腳本建立成功！${NC}"
    echo -e "${GREEN}📂 腳本位置: ${BOLD}${TARGET_SCRIPT}${NC} (同時支援 ~/LPM.sh)"
    echo -e "${GREEN}--------------------------------------------------${NC}"
    echo -e "${LIGHT_BLUE}💡 未來使用教學：${NC}"
    echo -e "   隨時在您的家目錄 (${BOLD}cd ~${NC}) 下，直接輸入：${BOLD}./lpm.sh${NC}"
    echo -e "   系統就會自動進入 Python 虛擬環境並為您秒開 LPM 管理工具！"
    echo -e "${GREEN}==================================================${NC}"
    
    echo -e "\n${GREEN}🚀 正在自動載入 Python 虛擬環境並開啟 LPM 管理工具...${NC}\n"
    sleep 1.5
    python3 manager.py "$@"

else
    # ==============================================================================
    # 🚀 核心邏輯 5：用戶選擇 N 時，保留提示並立刻在虛擬環境秒開 LPM！
    # ==============================================================================
    echo -e "\n${YELLOW}ℹ️ 已跳過快捷腳本建立。您日後仍可在專案目錄下透過 python3 manager.py 啟動。${NC}"
    echo -e "${GREEN}🚀 正在自動載入 Python 虛擬環境並開啟 LPM 管理工具...${NC}\n"
    
    sleep 1
    python3 manager.py "$@"
fi