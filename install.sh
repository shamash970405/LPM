#!/bin/bash

# ==============================================================================
# 🎨 ANSI 顏色定義 (讓安裝畫面更具科技感)
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
echo -e "${GREEN}✔ 成功定位專案實體路徑：${BOLD}${REPO_DIR}${NC}"

# ==============================================================================
# 🐍 核心邏輯 2：智能偵測 / 建立並進入 Python 虛擬環境 (Virtualenv)
# ==============================================================================
cd "$REPO_DIR" || exit 1

if [ -d ".venv" ]; then
    echo -e "${GREEN}✔ 偵測到現有虛擬環境 (.venv)，正在自動啟用...${NC}\n"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${GREEN}✔ 偵測到現有虛擬環境 (venv)，正在自動啟用...${NC}\n"
    source venv/bin/activate
else
    echo -e "${YELLOW}💡 未偵測到虛擬環境，正在自動幫您建立 .venv 虛擬環境並安裝必備套件...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    if [ -f "requirements.txt" ]; then
        pip install -q -r requirements.txt
        echo -e "${GREEN}✔ 虛擬環境與 requirements.txt 套件建置完成！${NC}\n"
    fi
fi

# ==============================================================================
# ❓ 核心邏輯 3：互動式詢問用戶是否加入快捷鍵
# ==============================================================================
echo -e -n "${YELLOW}❓ 是否要在您的家目錄 (~/) 下建立 lpm.sh 快捷腳本？\n   下次只需在家目錄輸入 ./lpm.sh 即可直接啟動 (y/N): ${NC}"
read -r response

# 支援大寫 Y、小寫 y 或 yes
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    TARGET_SCRIPT="$HOME/lpm.sh"
    # 貼心防呆：順手建立一份大寫的 LPM.sh，用戶不管打大寫還是小寫都能通！
    TARGET_SCRIPT_UPPER="$HOME/LPM.sh"
    
    echo -e "\n⏳ 正在產生自動啟動虛擬環境的快捷程式中..."

    # ==============================================================================
    # 📝 核心邏輯 4：自動生成 ~/lpm.sh (內含自動載入虛擬環境與啟動邏輯)
    # ==============================================================================
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
    
    # 暫停 1.5 秒，讓用戶看清楚上方的提示與使用教學
    echo -e "\n${GREEN}🚀 正在自動載入 Python 虛擬環境並開啟 LPM 管理工具...${NC}\n"
    sleep 1.5
    
    # 啟動主程式 (此時已經在 Python 虛擬環境中)
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