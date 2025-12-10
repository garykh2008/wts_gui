# WTS GUI (Wireless Test System Graphical Interface)

**Version**: 3.0  
**Copyright**: Copyright © 2025 Realtek Semiconductor Corp. All rights reserved.

## Introduction

WTS GUI is a graphical user interface (GUI) application designed for the **Wireless Test System (WTS)** tool. It integrates configuration file editing, test execution, log viewing, and results analysis, aiming to streamline the testing process and improve efficiency.

This tool supports cross-platform execution, including **Windows (Native / WSL)** and **Linux** environments.

---

## Key Features

*   **Configuration File Management (AllInitConfig Editor)**:
    *   Graphical editing of Key-Value configuration pairs.
    *   Dedicated pop-up editor for IP/Port parameters.
    *   Quickly enable/disable test devices (AP/STA) by commenting/uncommenting lines in the config file.
    *   Automatically loads `MasterTestInfo.xml` from the same directory as the `AllInitConfig` file.
*   **Test Execution**:
    *   Browse and filter test cases (by Role or keyword search).
    *   **Advanced Options**:
        *   **Not Pass (FAIL/NT) Cases Only**: Filters to show only failed (FAIL) or not tested (NT) items.
        *   **Show Cases include testbeds**: Filters to include test cases that utilize specific testbeds.
        *   **Ignore Cases with selected testbeds**: Excludes test cases that utilize specific testbeds (automatically linked to disabled devices in the Config Editor).
    *   Supports single or batch selection of tests for execution.
    *   Real-time Terminal Output with color-coded Pass/Fail indicators.
*   **Results Analysis (Test Result)**:
    *   Scans log directories and analyzes test results (PASS/FAIL/NT status).
    *   Supports filtering by Role and Date.
    *   **Export Results**: Export current analysis results to a professionally styled Excel (.xlsx) file, featuring:
        *   Conditional coloring (Green for PASS, Red for FAIL/ERROR).
        *   Auto-adjusted column widths for optimal readability.
        *   Frozen header row for easy scrolling through large datasets.
        *   Automatic data filters on header rows.
        *   Summary statistics (PASS/FAIL/NT/Not Support counts) prominently displayed.
    *   **History View**: Right-click on a test result to view its detailed past execution history and log folder.
    *   Live statistics dashboard (PASS/FAIL/NT/Total counts).
*   **Log Viewer**:
    *   Browse log folders by date (filterable).
    *   **Bulk Zip & Save**: Select multiple log folders and right-click to zip and save them to a specific directory in one go.
    *   View log files (`.log`, `.pcapng.gz`).
    *   Open files in the system's default text editor or Wireshark.
*   **Other Tools**:
    *   **MasterTestInfo Viewer**: Displays the detailed XML structure of test cases.
    *   **TmsClient.conf Editor**: Edits TMS upload settings.

---

## User Guide

### 1. AllInitConfig Editor (Configuration Editing)
1.  Click **Browse** to load an `AllInitConfig` file.
2.  The application will automatically load `MasterTestInfo.xml` from the same directory.
3.  **Modify Values**: Double-click on a "Value" field to edit it. IP/Port settings will open a dedicated pop-up window.
4.  **Device Control**: Use the checkboxes in the top-right to quickly enable/disable AP or STA devices.
    *   *Note: Devices disabled here will automatically affect the filtering rules in the Test Execution tab, excluding related test cases.*
5.  After making changes, click **Save AllInitConfig** to save the file.

### 2. Test Execution (Running Tests)
1.  **Filter Test Cases**: Use the Role (All/AP/STA) or Search fields to find specific test cases.
2.  **Advanced Options**:
    *   Check **Not Pass (FAIL/NT) Cases Only** to quickly filter for items that need retesting.
    *   Configure **Include/Ignore Testbeds** to precisely control the scope of tests.
3.  **Select Test Cases**: Check the desired test cases in the list (supports Select All / Deselect All).
4.  **Run**: Click **Run Selected Tests**. The right-hand Terminal will display real-time execution status.
5.  **Stop**: To abort running tests, click **Stop Tests**.

### 3. Test Result (Analyzing Results)
1.  Select a **Role** and **Date** (to analyze logs from or after that date).
2.  Click **Analyze Result** to start the analysis.
3.  The list will display the latest status (PASS/FAIL/NT) for each test case.
4.  **Export Results**: Click the **Export Result** button to save the current analysis data, including statistics and formatting, to an Excel (.xlsx) file.
5.  **View History**: Right-click on a test case result to view its detailed past execution records and associated log folders.

### 4. Log Viewer (Viewing Logs)
1.  Select a log folder from the left-hand side (can be filtered by date).
2.  **Zip Logs**: Right-click on one or more folders to zip and save them.
    *   **Single Selection**: "Zip and Save As..." allows you to choose the filename and location.
    *   **Multiple Selection**: "Zip and Save [N] Folders..." allows you to choose a destination directory. Each folder will be zipped individually into that directory.
3.  Double-click a file on the right to open it.
    *   `.log` files: Opened with the system's default text editor.
    *   `.pcapng` files: Attempted to open with Wireshark.

---

## FAQ (Frequently Asked Questions)

*   **Q: Why does the Test Execution list reduce after modifying AllInitConfig?**
    *   A: This is intended behavior. If you disable certain Testbed devices in the Config Editor, the system automatically filters out test cases that require those Testbeds, preventing execution failures.
*   **Q: Logs cannot be opened on Linux?**
    *   A: The application attempts to find editors like `gedit`, `kate`, `mousepad`, or `xdg-open`. Please ensure a common text editor is installed on your system or that the `$EDITOR` environment variable is correctly set.

---