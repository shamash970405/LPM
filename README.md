# 📦 Linux 套件管理助理 (LinuxPackageManagerApp)

一個基於 `Textual` 終端機 UI (TUI) 框架打造的開源跨平台 Linux 套件管理工具。
完美整合 **Arch Linux (`pacman`)**、**Ubuntu / Debian (`apt`)** 與**新世代沙盒 (`snap`)** 三大通路並行多工掃描，並內建Gemini詢問套件工具。

---
<img width="1923" height="1080" alt="image" src="https://github.com/user-attachments/assets/b352491f-3266-4f17-8c7b-4744f4d6d766" />

<video src="demo/LPM%20demo.mp4" controls="controls" width="100%" autoplay loop muted>
</video>

## 🚀 核心特色

- ⚡ **並行多工全通路掃描**：啟動時自動、並行偵測系統環境。不論是原生 `pacman`、`apt` 還是 `snap` 沙盒套件，一鍵全自動跨發行版交叉撈取，並以霓虹專屬色彩標籤完美渲染。
- 🎯 **一擊必殺卸載流**：回歸極客最直覺的操作本能！在下方表格中用滑鼠「輕點一下」或鍵盤按下 `Enter`，程式將毫無廢話、瞬間自動判斷套件來源，並應聲彈出系統預設終端機（如 Konsole 或 Gnome-terminal）直接帶入 `sudo` 卸載程序。
- 📊 **雙維度自適應排序**：
  - 點擊 **「套件名稱」** 標頭：套件依字母 `A ~ Z` / `Z ~ A` 字典順序極速重排。
  - 點擊 **「佔用容量」** 標頭：自動解析不同單位的記憶體大小，依容量大到小 / 小到大精準排序。
- 🤖 **Gemini AI 智慧通靈**：點擊套件的同時，右側區塊自動調用 Gemini-2.5-Flash 模型，用台灣習慣的白話繁體中文為你即時解說套件核心用途。
- 🛡️ **開機金鑰防呆提示**：啟動時若系統未偵測到環境變數，會主動跳出互動式問答，可手動貼上金鑰或輸入 `z` 略過 AI 功能，確保單機卸載功能依然流暢運作。

---

## 🛠️ 安裝與依賴環境

本專案採用 **Python 3.10+** 開發，且已完整測試過最新環境相容性。請在專案目錄下依序執行以下指令來初始化環境：

```bash
# 1. 建立並啟用 Python 虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 2. 一鍵安裝官方標準相容依賴套件（包含 Textual 與 Google GenAI）
pip install -r requirements.txt
