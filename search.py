import asyncio

# 🔍 獨立模組：負責處理搜尋列的防抖 (Debounce) 與過濾觸發
async def process_search_input(app, event):
    """
    接收主程式傳來的 app 實例與事件，處理完再把結果丟回給主程式
    """
    # 1. 抓取使用者輸入的關鍵字
    search_str = event.value.strip()
    
    # 2. 防抖機制：如果使用者還在連續打字，就取消上一次的倒數計時
    if hasattr(app, "search_timer") and app.search_timer:
        app.search_timer.cancel()
        
    # 3. 定義延遲執行的實際搜尋任務
    async def execute_search():
        # 等待 300 毫秒 (0.3秒)，確認使用者手指離開鍵盤了才動作
        await asyncio.sleep(0.3) 
        
        # 將過濾的關鍵字存回主程式的變數中
        app.search_text = search_str
        
        # 呼叫主程式的 refresh_table_view 來重畫表格
        app.refresh_table_view()

    # 4. 啟動新的計時器
    app.search_timer = asyncio.create_task(execute_search())