#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <commctrl.h>
#include <shobjidl.h>
#include <shlobj.h>

// Embedded icon resource ID (must match lattice_gui.rc)
#define IDI_ICON1 101
#include <string>
#include <thread>
#include <vector>
#include <sstream>
#include <algorithm>
#include <memory>
#include <atomic>

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "shell32.lib")

// Control IDs
enum {
    ID_RADIO_COMPRESS = 101,
    ID_RADIO_DECOMPRESS,
    ID_EDIT_INPUT,
    ID_BTN_BROWSE_INPUT,
    ID_EDIT_OUTPUT,
    ID_BTN_BROWSE_OUTPUT,
    ID_CHK_SOLID,
    ID_CHK_LOSSLESS,
    ID_CHK_FAST,
    ID_CHK_BEST,
    ID_PROGRESS,
    ID_STATUS_LABEL,
    ID_EDIT_LOG,
    ID_BTN_START,
    ID_BTN_CANCEL
};

// Global variables
HWND hMainWnd = NULL;
HWND hRadioCompress = NULL;
HWND hRadioDecompress = NULL;
HWND hEditInput = NULL;
HWND hEditOutput = NULL;
HWND hBtnBrowseInput = NULL;
HWND hBtnBrowseOutput = NULL;
HWND hChkSolid = NULL;
HWND hChkLossless = NULL;
HWND hChkFast = NULL;
HWND hChkBest = NULL;
HWND hProgress = NULL;
HWND hStatusLabel = NULL;
HWND hEditLog = NULL;
HWND hBtnStart = NULL;
HWND hBtnCancel = NULL;

HANDLE hChildProcess = NULL;
HANDLE hReadPipe = NULL;
std::thread workerThread;
std::atomic<bool> bIsRunning(false);

// Helpers
std::string extract_json_value(const std::string& json, const std::string& key) {
    size_t pos = json.find("\"" + key + "\"");
    if (pos == std::string::npos) return "";
    pos = json.find(":", pos);
    if (pos == std::string::npos) return "";
    pos++;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t')) pos++;
    if (pos >= json.size()) return "";
    if (json[pos] == '"') {
        pos++;
        size_t end_pos = json.find("\"", pos);
        if (end_pos == std::string::npos) return "";
        return json.substr(pos, end_pos - pos);
    } else {
        size_t end_pos = pos;
        while (end_pos < json.size() && json[end_pos] != ',' && json[end_pos] != '}' && json[end_pos] != '\r' && json[end_pos] != '\n') {
            end_pos++;
        }
        return json.substr(pos, end_pos - pos);
    }
}

std::wstring GetWindowTextString(HWND hwnd) {
    int len = GetWindowTextLengthW(hwnd);
    if (len <= 0) return L"";
    std::vector<wchar_t> buf(len + 1);
    GetWindowTextW(hwnd, buf.data(), len + 1);
    return std::wstring(buf.data());
}

void LogMessage(const std::wstring& msg) {
    int len = GetWindowTextLengthW(hEditLog);
    SendMessageW(hEditLog, EM_SETSEL, len, len);
    SendMessageW(hEditLog, EM_REPLACESEL, 0, (LPARAM)msg.c_str());
}

void LogMessageA(const std::string& msg) {
    int len = MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, NULL, 0);
    std::vector<wchar_t> buf(len);
    MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1, buf.data(), len);
    LogMessage(std::wstring(buf.data()) + L"\r\n");
}

void UpdateControlsState() {
    EnableWindow(hRadioCompress, !bIsRunning);
    EnableWindow(hRadioDecompress, !bIsRunning);
    EnableWindow(hEditInput, !bIsRunning);
    EnableWindow(hBtnBrowseInput, !bIsRunning);
    EnableWindow(hEditOutput, !bIsRunning);
    EnableWindow(hBtnBrowseOutput, !bIsRunning);
    
    bool isCompress = SendMessage(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
    EnableWindow(hChkSolid, !bIsRunning && isCompress);
    EnableWindow(hChkLossless, !bIsRunning && isCompress);
    EnableWindow(hChkFast, !bIsRunning && isCompress);
    EnableWindow(hChkBest, !bIsRunning && isCompress);
    
    EnableWindow(hBtnStart, !bIsRunning);
    SetWindowTextW(hBtnCancel, bIsRunning ? L"Cancel" : L"Exit");
}

// Open Dialog helpers
std::wstring OpenFileDialog(bool folderMode, bool saveMode) {
    std::wstring path = L"";
    IFileDialog *pfd = NULL;
    CLSID clsid = saveMode ? CLSID_FileSaveDialog : CLSID_FileOpenDialog;
    IID iid = saveMode ? IID_IFileSaveDialog : IID_IFileOpenDialog;
    
    if (SUCCEEDED(CoCreateInstance(clsid, NULL, CLSCTX_INPROC_SERVER, iid, (void**)&pfd))) {
        DWORD dwOptions = 0;
        if (SUCCEEDED(pfd->GetOptions(&dwOptions))) {
            if (folderMode) {
                pfd->SetOptions(dwOptions | FOS_PICKFOLDERS);
            } else if (!saveMode) {
                pfd->SetOptions(dwOptions | FOS_FORCEFILESYSTEM);
            }
        }
        
        if (!folderMode && !saveMode) {
            COMDLG_FILTERSPEC fileTypes[] = {
                { L"Lattice Archives (*.lattice)", L"*.lattice" },
                { L"All Files (*.*)", L"*.*" }
            };
            pfd->SetFileTypes(2, fileTypes);
        }
        
        if (SUCCEEDED(pfd->Show(hMainWnd))) {
            IShellItem *psi = NULL;
            if (SUCCEEDED(pfd->GetResult(&psi))) {
                LPWSTR pszPath = NULL;
                if (SUCCEEDED(psi->GetDisplayName(SIGDN_FILESYSPATH, &pszPath))) {
                    path = pszPath;
                    CoTaskMemFree(pszPath);
                }
                psi->Release();
            }
        }
        pfd->Release();
    }
    return path;
}

// Background CLI worker
void ReadPipeThread() {
    char buf[1024];
    DWORD bytesRead;
    std::string lineBuffer = "";
    
    while (ReadFile(hReadPipe, buf, sizeof(buf) - 1, &bytesRead, NULL) && bytesRead > 0) {
        buf[bytesRead] = '\0';
        lineBuffer += buf;
        
        size_t pos;
        while ((pos = lineBuffer.find('\n')) != std::string::npos) {
            std::string line = lineBuffer.substr(0, pos);
            lineBuffer.erase(0, pos + 1);
            
            // Trim leading and trailing whitespace/newlines
            while (!line.empty() && (line.front() == ' ' || line.front() == '\t' || line.front() == '\r' || line.front() == '\n')) {
                line.erase(line.begin());
            }
            while (!line.empty() && (line.back() == ' ' || line.back() == '\t' || line.back() == '\r' || line.back() == '\n')) {
                line.pop_back();
            }
            if (line.empty()) continue;
            
            // Try to parse JSON output
            if (line.front() == '{' && line.back() == '}') {
                std::string type = extract_json_value(line, "type");
                if (type == "status") {
                    std::string status = extract_json_value(line, "status");
                    std::wstring statusW = L"Status: " + std::wstring(status.begin(), status.end());
                    SetWindowTextW(hStatusLabel, statusW.c_str());
                    LogMessageA("[Status] " + status);
                } else if (type == "progress") {
                    std::string pctStr = extract_json_value(line, "percent");
                    std::string fileStr = extract_json_value(line, "file");
                    
                    double pct = 0;
                    if (!pctStr.empty()) pct = std::stod(pctStr);
                    
                    std::wstring statusW = L"Processing: " + std::wstring(fileStr.begin(), fileStr.end()) + L" (" + std::wstring(pctStr.begin(), pctStr.end()) + L"%)";
                    SetWindowTextW(hStatusLabel, statusW.c_str());
                    SendMessage(hProgress, PBM_SETPOS, (WPARAM)(int)pct, 0);
                } else if (type == "done") {
                    std::string sizeStr = extract_json_value(line, "compressed_size");
                    std::string origStr = extract_json_value(line, "original_size");
                    std::string ratioStr = extract_json_value(line, "ratio");
                    std::string elapsedStr = extract_json_value(line, "elapsed");
                    
                    LogMessageA("==========================================");
                    LogMessageA("Execution Completed successfully!");
                    LogMessageA("Original Size: " + origStr + " bytes");
                    if (!sizeStr.empty() && sizeStr != "0") {
                        LogMessageA("Compressed Size: " + sizeStr + " bytes");
                        LogMessageA("Ratio: " + ratioStr + "x");
                    }
                    LogMessageA("Time Elapsed: " + elapsedStr + " seconds");
                    LogMessageA("==========================================");
                    
                    SetWindowTextW(hStatusLabel, L"Status: Done");
                    SendMessage(hProgress, PBM_SETPOS, 100, 0);
                } else if (type == "error") {
                    std::string msg = extract_json_value(line, "message");
                    LogMessageA("[ERROR] " + msg);
                    SetWindowTextW(hStatusLabel, L"Status: Execution Failed");
                    MessageBoxA(hMainWnd, msg.c_str(), "Lattice Engine Error", MB_ICONERROR);
                }
            } else {
                LogMessageA(line);
            }
        }
    }
    
    // Wait for process termination
    WaitForSingleObject(hChildProcess, INFINITE);
    
    CloseHandle(hChildProcess);
    CloseHandle(hReadPipe);
    hChildProcess = NULL;
    hReadPipe = NULL;
    
    bIsRunning = false;
    UpdateControlsState();
}

void StartEngineProcess() {
    std::wstring input = GetWindowTextString(hEditInput);
    std::wstring output = GetWindowTextString(hEditOutput);
    
    // Trim trailing backslash/slash to prevent argument escaping issues in CreateProcessW
    if (input.size() > 3 && (input.back() == '\\' || input.back() == '/')) {
        input.pop_back();
    }
    if (output.size() > 3 && (output.back() == '\\' || output.back() == '/')) {
        output.pop_back();
    }

    if (input.empty() || output.empty()) {
        MessageBoxW(hMainWnd, L"Please select both input and output paths.", L"Validation Error", MB_ICONWARNING);
        return;
    }
    
    bool isCompress = SendMessage(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isSolid = SendMessage(hChkSolid, BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isLossless = SendMessage(hChkLossless, BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isFast = SendMessage(hChkFast, BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isBest = SendMessage(hChkBest, BM_GETCHECK, 0, 0) == BST_CHECKED;
    
    // Find CLI executable location relative to the GUI binary directory
    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(NULL, exePath, MAX_PATH);
    std::wstring baseDir = exePath;
    size_t lastSlash = baseDir.find_last_of(L"\\/");
    if (lastSlash != std::wstring::npos) {
        baseDir = baseDir.substr(0, lastSlash + 1);
    } else {
        baseDir = L".\\";
    }

    std::wstring cliPath = baseDir + L"lattice_cli.exe";
    if (GetFileAttributesW(cliPath.c_str()) == INVALID_FILE_ATTRIBUTES) {
        // Try fallback to baseDir + engine/build/lattice_cli.exe
        cliPath = baseDir + L"engine\\build\\lattice_cli.exe";
        if (GetFileAttributesW(cliPath.c_str()) == INVALID_FILE_ATTRIBUTES) {
            // Try parent directory fallback
            cliPath = baseDir + L"..\\lattice_cli.exe";
            if (GetFileAttributesW(cliPath.c_str()) == INVALID_FILE_ATTRIBUTES) {
                cliPath = L"lattice_cli.exe"; // Try system PATH fallback
            }
        }
    }
    
    std::wstringstream cmdStream;
    cmdStream << L"\"" << cliPath << L"\" ";
    if (isCompress) {
        cmdStream << L"compress \"" << input << L"\" \"" << output << L"\"";
        if (isSolid) cmdStream << L" --solid";
        if (isLossless) cmdStream << L" --virtually-lossless";
        if (isFast) cmdStream << L" --fast";
        if (isBest) cmdStream << L" --best";
    } else {
        cmdStream << L"decompress \"" << input << L"\" \"" << output << L"\"";
    }
    
    std::wstring cmdLine = cmdStream.str();
    
    // Create Pipes
    HANDLE hWritePipe;
    SECURITY_ATTRIBUTES saAttr;
    saAttr.nLength = sizeof(SECURITY_ATTRIBUTES);
    saAttr.bInheritHandle = TRUE;
    saAttr.lpSecurityDescriptor = NULL;
    
    if (!CreatePipe(&hReadPipe, &hWritePipe, &saAttr, 0)) {
        MessageBoxW(hMainWnd, L"Failed to create pipes for execution.", L"System Error", MB_ICONERROR);
        return;
    }
    
    if (!SetHandleInformation(hReadPipe, HANDLE_FLAG_INHERIT, 0)) {
        CloseHandle(hReadPipe);
        CloseHandle(hWritePipe);
        return;
    }
    
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.hStdError = hWritePipe;
    si.hStdOutput = hWritePipe;
    si.dwFlags |= STARTF_USESTDHANDLES;
    
    ZeroMemory(&pi, sizeof(pi));
    
    SetWindowTextW(hEditLog, L"");
    LogMessage(L"Starting execution command:\r\n" + cmdLine + L"\r\n\r\n");
    SendMessage(hProgress, PBM_SETPOS, 0, 0);
    SetWindowTextW(hStatusLabel, L"Status: Starting engine...");
    
    // Copy command line to a modifiable buffer (CreateProcessW writes to the string in-place)
    std::vector<wchar_t> cmdLineBuf(cmdLine.begin(), cmdLine.end());
    cmdLineBuf.push_back(L'\0');
    
    if (!CreateProcessW(NULL, cmdLineBuf.data(), NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        DWORD err = GetLastError();
        std::wstringstream errStream;
        errStream << L"Failed to launch Lattice CLI core engine (ErrorCode: " << err << L").\nPath tried: " << cliPath;
        MessageBoxW(hMainWnd, errStream.str().c_str(), L"Process Spawning Error", MB_ICONERROR);
        CloseHandle(hReadPipe);
        CloseHandle(hWritePipe);
        SetWindowTextW(hStatusLabel, L"Status: Idle");
        return;
    }
    
    // Write pipe is owned by the child, close our reference to it
    CloseHandle(hWritePipe);
    CloseHandle(pi.hThread);
    
    hChildProcess = pi.hProcess;
    bIsRunning = true;
    UpdateControlsState();
    
    workerThread = std::thread(ReadPipeThread);
    workerThread.detach();
}

void CancelEngineProcess() {
    if (bIsRunning && hChildProcess) {
        TerminateProcess(hChildProcess, 1);
        LogMessage(L"\r\n[Process cancelled by user]\r\n");
        SetWindowTextW(hStatusLabel, L"Status: Cancelled");
        SendMessage(hProgress, PBM_SETPOS, 0, 0);
    }
}

// Window Procedure
LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_CREATE: {
        // Set fonts to modern System Font
        HFONT hFont = CreateFontW(16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
            
        // Groupboxes
        HWND hGrpMode = CreateWindowW(L"BUTTON", L"Operation Mode", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 15, 10, 675, 60, hWnd, NULL, NULL, NULL);
        HWND hGrpPaths = CreateWindowW(L"BUTTON", L"Paths Selection", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 15, 80, 675, 130, hWnd, NULL, NULL, NULL);
        HWND hGrpOptions = CreateWindowW(L"BUTTON", L"Advanced Options", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 15, 220, 675, 90, hWnd, NULL, NULL, NULL);
        HWND hGrpLog = CreateWindowW(L"BUTTON", L"Execution Output Log", WS_CHILD | WS_VISIBLE | BS_GROUPBOX, 15, 320, 675, 205, hWnd, NULL, NULL, NULL);
        
        SendMessage(hGrpMode, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hGrpPaths, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hGrpOptions, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hGrpLog, WM_SETFONT, (WPARAM)hFont, TRUE);

        // Radio buttons
        hRadioCompress = CreateWindowW(L"BUTTON", L"Compress Payload (Lossless)", WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON | WS_GROUP, 30, 30, 240, 25, hWnd, (HMENU)ID_RADIO_COMPRESS, NULL, NULL);
        hRadioDecompress = CreateWindowW(L"BUTTON", L"Decompress Archive (*.lattice)", WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON, 280, 30, 260, 25, hWnd, (HMENU)ID_RADIO_DECOMPRESS, NULL, NULL);
        SendMessage(hRadioCompress, BM_SETCHECK, BST_CHECKED, 0);
        SendMessage(hRadioCompress, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hRadioDecompress, WM_SETFONT, (WPARAM)hFont, TRUE);

        // Path labels & edits
        HWND hLblInput = CreateWindowW(L"STATIC", L"Source File/Directory:", WS_CHILD | WS_VISIBLE, 30, 105, 200, 20, hWnd, NULL, NULL, NULL);
        hEditInput = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL, 30, 125, 520, 23, hWnd, (HMENU)ID_EDIT_INPUT, NULL, NULL);
        hBtnBrowseInput = CreateWindowW(L"BUTTON", L"Browse...", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 560, 124, 115, 25, hWnd, (HMENU)ID_BTN_BROWSE_INPUT, NULL, NULL);
        
        HWND hLblOutput = CreateWindowW(L"STATIC", L"Output Path:", WS_CHILD | WS_VISIBLE, 30, 155, 200, 20, hWnd, NULL, NULL, NULL);
        hEditOutput = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL, 30, 175, 520, 23, hWnd, (HMENU)ID_EDIT_OUTPUT, NULL, NULL);
        hBtnBrowseOutput = CreateWindowW(L"BUTTON", L"Browse...", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 560, 174, 115, 25, hWnd, (HMENU)ID_BTN_BROWSE_OUTPUT, NULL, NULL);

        SendMessage(hLblInput, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hEditInput, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hBtnBrowseInput, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hLblOutput, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hEditOutput, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hBtnBrowseOutput, WM_SETFONT, (WPARAM)hFont, TRUE);

        // Checkboxes
        hChkSolid = CreateWindowW(L"BUTTON", L"Solid Block Mode (Highly recommended for folders)", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 30, 245, 380, 25, hWnd, (HMENU)ID_CHK_SOLID, NULL, NULL);
        hChkLossless = CreateWindowW(L"BUTTON", L"Virtually Lossless Masking (For WAV / BMP / Floats)", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 410, 245, 265, 25, hWnd, (HMENU)ID_CHK_LOSSLESS, NULL, NULL);
        hChkFast = CreateWindowW(L"BUTTON", L"Fast Mode (Turbo speed / low compression)", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 30, 275, 380, 25, hWnd, (HMENU)ID_CHK_FAST, NULL, NULL);
        hChkBest = CreateWindowW(L"BUTTON", L"Best Compression (Ultra slow / maximum ratio)", WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 410, 275, 265, 25, hWnd, (HMENU)ID_CHK_BEST, NULL, NULL);
        
        SendMessage(hChkSolid, BM_SETCHECK, BST_CHECKED, 0);
        SendMessage(hChkSolid, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hChkLossless, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hChkFast, WM_SETFONT, (WPARAM)hFont, TRUE); // Default to fast mode
        SendMessage(hChkFast, BM_SETCHECK, BST_CHECKED, 0);
        SendMessage(hChkFast, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hChkBest, WM_SETFONT, (WPARAM)hFont, TRUE);

        // Progress bar & Status
        hProgress = CreateWindowW(PROGRESS_CLASSW, L"", WS_CHILD | WS_VISIBLE | PBS_SMOOTH, 30, 345, 645, 17, hWnd, (HMENU)ID_PROGRESS, NULL, NULL);
        hStatusLabel = CreateWindowW(L"STATIC", L"Status: Idle", WS_CHILD | WS_VISIBLE, 30, 367, 645, 20, hWnd, (HMENU)ID_STATUS_LABEL, NULL, NULL);
        SendMessage(hProgress, PBM_SETRANGE, 0, MAKELPARAM(0, 100));
        SendMessage(hProgress, PBM_SETSTEP, 1, 0);
        SendMessage(hStatusLabel, WM_SETFONT, (WPARAM)hFont, TRUE);

        // Log edit box
        hEditLog = CreateWindowW(L"EDIT", L"", WS_CHILD | WS_VISIBLE | WS_BORDER | WS_VSCROLL | WS_HSCROLL | ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL | ES_AUTOHSCROLL, 30, 390, 645, 120, hWnd, (HMENU)ID_EDIT_LOG, NULL, NULL);
        SendMessage(hEditLog, WM_SETFONT, (WPARAM)hFont, TRUE);

        // Action buttons
        hBtnStart = CreateWindowW(L"BUTTON", L"Start Execution", WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON, 440, 535, 120, 30, hWnd, (HMENU)ID_BTN_START, NULL, NULL);
        hBtnCancel = CreateWindowW(L"BUTTON", L"Exit", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 570, 535, 120, 30, hWnd, (HMENU)ID_BTN_CANCEL, NULL, NULL);
        SendMessage(hBtnStart, WM_SETFONT, (WPARAM)hFont, TRUE);
        SendMessage(hBtnCancel, WM_SETFONT, (WPARAM)hFont, TRUE);

        UpdateControlsState();
        break;
    }
    case WM_COMMAND: {
        int wmId = LOWORD(wParam);
        int wmEvent = HIWORD(wParam);
        switch (wmId) {
        case ID_RADIO_COMPRESS:
        case ID_RADIO_DECOMPRESS:
            if (wmEvent == BN_CLICKED) {
                UpdateControlsState();
            }
            break;
        case ID_CHK_FAST:
            if (wmEvent == BN_CLICKED) {
                if (SendMessage(hChkFast, BM_GETCHECK, 0, 0) == BST_CHECKED) {
                    SendMessage(hChkBest, BM_SETCHECK, BST_UNCHECKED, 0);
                }
            }
            break;
        case ID_CHK_BEST:
            if (wmEvent == BN_CLICKED) {
                if (SendMessage(hChkBest, BM_GETCHECK, 0, 0) == BST_CHECKED) {
                    SendMessage(hChkFast, BM_SETCHECK, BST_UNCHECKED, 0);
                }
            }
            break;
        case ID_BTN_BROWSE_INPUT: {
            bool isCompress = SendMessage(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
            std::wstring path = L"";
            if (isCompress) {
                // For compress input, let the user pick EITHER files or folders
                int ret = MessageBoxW(hWnd, L"Click YES to select a FILE, or NO to select a FOLDER.", L"Select Input Type", MB_YESNOCANCEL | MB_ICONQUESTION);
                if (ret == IDYES) {
                    path = OpenFileDialog(false, false);
                } else if (ret == IDNO) {
                    path = OpenFileDialog(true, false);
                }
            } else {
                // For decompress, pick the .lattice archive file
                path = OpenFileDialog(false, false);
            }
            
            if (!path.empty()) {
                SetWindowTextW(hEditInput, path.c_str());
                
                // Auto-suggest output path
                std::wstring outPath = path;
                bool isCompressMode = SendMessage(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
                if (isCompressMode) {
                    // Append .lattice
                    if (outPath.back() == '\\' || outPath.back() == '/') {
                        outPath.pop_back();
                    }
                    outPath += L".lattice";
                    SetWindowTextW(hEditOutput, outPath.c_str());
                } else {
                    // Extract to a folder
                    size_t extPos = outPath.find(L".lattice");
                    if (extPos != std::wstring::npos) {
                        outPath = outPath.substr(0, extPos) + L"_extracted";
                    } else {
                        outPath += L"_extracted";
                    }
                    SetWindowTextW(hEditOutput, outPath.c_str());
                }
            }
            break;
        }
        case ID_BTN_BROWSE_OUTPUT: {
            bool isCompress = SendMessage(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
            std::wstring path = L"";
            if (isCompress) {
                path = OpenFileDialog(false, true); // Save file dialog
            } else {
                path = OpenFileDialog(true, false);  // Folder picker dialog
            }
            if (!path.empty()) {
                SetWindowTextW(hEditOutput, path.c_str());
            }
            break;
        }
        case ID_BTN_START:
            StartEngineProcess();
            break;
        case ID_BTN_CANCEL:
            if (bIsRunning) {
                CancelEngineProcess();
            } else {
                DestroyWindow(hWnd);
            }
            break;
        }
        break;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        break;
    default:
        return DefWindowProc(hWnd, message, wParam, lParam);
    }
    return 0;
}

int APIENTRY WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    
    INITCOMMONCONTROLSEX icex;
    icex.dwSize = sizeof(INITCOMMONCONTROLSEX);
    icex.dwICC = ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES;
    InitCommonControlsEx(&icex);
    
    WNDCLASSEXW wcex;
    wcex.cbSize = sizeof(WNDCLASSEXW);
    wcex.style = CS_HREDRAW | CS_VREDRAW;
    wcex.lpfnWndProc = WndProc;
    wcex.cbClsExtra = 0;
    wcex.cbWndExtra = 0;
    wcex.hInstance = hInstance;
    wcex.hIcon = LoadIconW(hInstance, MAKEINTRESOURCEW(IDI_ICON1));
    if (!wcex.hIcon) wcex.hIcon = LoadIconW(NULL, (LPCWSTR)IDI_APPLICATION);
    wcex.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wcex.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wcex.lpszMenuName = NULL;
    wcex.lpszClassName = L"LatticeGuiClass";
    wcex.hIconSm = LoadIconW(hInstance, MAKEINTRESOURCEW(IDI_ICON1));
    if (!wcex.hIconSm) wcex.hIconSm = LoadIconW(NULL, (LPCWSTR)IDI_APPLICATION);
    
    RegisterClassExW(&wcex);
    
    // Fixed window frame size matching our controls layout
    RECT rect = { 0, 0, 710, 580 };
    AdjustWindowRect(&rect, WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX, FALSE);
    
    hMainWnd = CreateWindowW(L"LatticeGuiClass", L"Lattice Compression Engine — Premium GUI UI",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, rect.right - rect.left, rect.bottom - rect.top,
        NULL, NULL, hInstance, NULL);
        
    if (!hMainWnd) return FALSE;
    
    ShowWindow(hMainWnd, nCmdShow);
    UpdateWindow(hMainWnd);
    
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    
    CoUninitialize();
    return (int)msg.wParam;
}
