# WTS GUI (Wireless Test System Graphical Interface)

**版本**: 3.0  
**版權**: Copyright © 2025 Realtek Semiconductor Corp. All rights reserved.

## 簡介

WTS GUI 是一個專為 **無線測試系統 (WTS)** 工具設計的圖形使用者介面 (GUI) 應用程式。它整合了設定檔編輯、測試執行、日誌查看和結果分析，旨在簡化測試流程並提高效率。

此工具支援跨平台執行，包括 **Windows (原生 / WSL)** 和 **Linux** 環境。

---

## 主要功能

*   **設定檔管理 (AllInitConfig 編輯器)**:
    *   圖形化編輯 Key-Value 設定對。
    *   專用的彈出式編輯器，用於 IP/Port 參數。
    *   透過註解/取消註解設定檔中的行，快速啟用/禁用測試裝置 (AP/STA)。
    *   自動從 `AllInitConfig` 檔案所在的相同目錄載入 `MasterTestInfo.xml`。
*   **Test Execution**:
    *   瀏覽並篩選測試案例 (依 **Role** 或關鍵字搜尋)。
    *   **Advanced Options**:
        *   **Not Pass (FAIL/NT) Cases Only**: 篩選以僅顯示失敗 (FAIL) 或未測試 (NT) 的項目。
        *   **Show Cases include testbeds**: 篩選以包含使用特定測試平台的測試案例。
        *   **Ignore Cases with selected testbeds**: 排除使用特定測試平台的測試案例 (自動連結到設定編輯器中禁用的裝置)。
    *   支援單選或批次選擇測試進行執行。
        即時 **Terminal Output**，並帶有顏色編碼的 **Pass/Fail** 指示。
*   **結果分析 (Test Result)**:
    *   掃描日誌目錄並分析測試結果 (PASS/FAIL/NT 狀態)。
    *   支援依 **Role** 和 **Date** 篩選。
    *   **匯出結果 (Export Results)**: 將當前的分析結果匯出為專業格式的 Excel (.xlsx) 檔案，功能包含：
        *   條件式格式化上色 (PASS 為綠色，FAIL/ERROR 為紅色)。
        *   自動調整欄寬以達到最佳閱讀效果。
        *   凍結首列標題，方便瀏覽大量資料。
        *   標題列自動開啟資料篩選功能。
        *   顯著展示統計摘要 (PASS/FAIL/NT/Not Support 計數)。
    *   **History View**: 右鍵點擊測試結果可查看其詳細的歷史執行記錄和相關日誌資料夾。
    即時統計儀表板 (**PASS/FAIL/NT/Total counts**)。
*   **Log Viewer**:
    *   按 **Date** 瀏覽日誌資料夾 (可篩選)。
    *   **大量壓縮並儲存 (Bulk Zip & Save)**: 選取多個日誌資料夾並按右鍵，即可一次將它們壓縮並儲存到指定目錄。
    *   查看日誌檔案 (`.log`, `.pcapng.gz`)。
    *   使用系統預設文字編輯器或 Wireshark 開啟檔案。
*   **其他工具**:
    *   **MasterTestInfo Viewer**: 顯示測試案例的詳細 XML 結構。
    *   **TmsClient.conf Editor**: 編輯 TMS 上傳設定。

---

## 使用者指南

### 1. **AllInitConfig Editor** (設定檔編輯)
1.  點擊 **Browse** 以載入 **AllInitConfig** 檔案。
2.  應用程式將自動從相同目錄載入 **MasterTestInfo.xml**。
3.  **Modify Values**: 雙擊 "**Value**" 欄位以進行編輯。**IP/Port** 設定將會開啟專用的彈出式視窗。
4.  **Device Control**: 使用右上角的核取方塊快速啟用/禁用 **AP** 或 **STA** 裝置。
    *   *注意：在此禁用的裝置將自動影響「**Test Execution**」分頁中的篩選規則，排除相關的測試案例。*
5.  修改完成後，點擊 **Save AllInitConfig** 以儲存檔案。

### 2. **Test Execution** (執行測試)
1.  **Filter Test Cases**: 使用 **Role** (全部/**AP**/**STA**) 或 **Search** 欄位來尋找特定的測試案例。
2.  **Advanced Options**:
    *   勾選 **Not Pass (FAIL/NT) Cases Only** 以快速篩選需要重新測試的項目。
    *   配置 **Include/Ignore Testbeds** 以精確控制測試範圍。
3.  **Select Test Cases**: 在列表中勾選所需的測試案例 (支援 **Select All** / **Deselect All**)。
4.  **Run**: 點擊 **Run Selected Tests**。右側的 **Terminal** 將顯示即時執行狀態。
5.  **Stop**: 要中止正在執行的測試，點擊 **Stop Tests**。

### 3. **Test Result** (分析結果)
1.  選擇 **Role** 和 **Date** (以分析從該日期或之後的日誌)。
2.  點擊 **Analyze Result** 開始分析。
3.  列表將顯示每個測試案例的最新狀態 (**PASS/FAIL/NT**)。
4.  **匯出結果**: 點擊 **Export Result** 按鈕，將目前的分析資料（包含統計數據與格式設定）儲存為 Excel (.xlsx) 檔案。
5.  **History View**: 右鍵點擊測試案例結果可查看其詳細的歷史執行記錄和相關日誌資料夾。

### 4. **Log Viewer** (查看日誌)
1.  從左側選擇一個日誌資料夾 (可按日期篩選)。
2.  **壓縮日誌 (Zip Logs)**: 右鍵點擊一個或多個資料夾進行壓縮儲存。
    *   **單一選擇 (Single Selection)**: 選擇 "**Zip and Save As...**" 可自訂檔名與儲存位置。
    *   **多重選擇 (Multiple Selection)**: 選擇 "**Zip and Save [N] Folders...**" 可選擇目標目錄。每個資料夾將會被單獨壓縮到該目錄中。
3.  雙擊右側的檔案以開啟它。
    *   `.log` 檔案：使用系統預設文字編輯器開啟。
    *   `.pcapng` 檔案：嘗試使用 Wireshark 開啟。

---

## 常見問題 (FAQ)

*   **Q: 為什麼修改 AllInitConfig 後，「**Test Execution**」列表會減少？**
    *   A: 這是預期的行為。如果您在設定編輯器中禁用了某些測試平台裝置，系統會自動篩選掉需要這些測試平台的測試案例，以防止執行失敗。
*   **Q: 在 Linux 上無法開啟日誌？**
    *   A: 應用程式會嘗試尋找 `gedit`、`kate`、`mousepad` 或 `xdg-open` 等編輯器。請確保您的系統上安裝了常用的文字編輯器，或者 `$EDITOR` 環境變數已正確設定。

---