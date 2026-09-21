/**
 * @file lattice_gui.cpp
 * @brief Middleout-Lattice — Premium Dark-Theme Win32 GUI
 *
 * Full-featured native Windows GUI with:
 *   - Custom dark theme (GDI owner-draw)
 *   - Drag-and-drop file/folder support
 *   - Real-time stats dashboard (ratio, speed, throughput)
 *   - Speed mode selector (Fast / Balanced / Best)
 *   - JSON progress parsing from lattice_cli.exe pipe
 *
 * @copyright 2024-2026 Middleout-Lattice Project. All rights reserved.
 */

#define WIN32_LEAN_AND_MEAN
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <commctrl.h>
#include <shobjidl.h>
#include <shlobj.h>
#include <shellapi.h>
#include <uxtheme.h>
#include <dwmapi.h>
#include <string>
#include <thread>
#include <vector>
#include <sstream>
#include <algorithm>
#include <memory>
#include <atomic>
#include <cstdio>

#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "uxtheme.lib")
#pragma comment(lib, "dwmapi.lib")

// Resource IDs
#define IDI_ICON1 101

// Control IDs
enum {
    ID_RADIO_COMPRESS   = 201,
    ID_RADIO_DECOMPRESS = 202,
    ID_EDIT_INPUT       = 203,
    ID_BTN_BROWSE_IN    = 204,
    ID_EDIT_OUTPUT      = 205,
    ID_BTN_BROWSE_OUT   = 206,
    ID_CHK_SOLID        = 207,
    ID_CHK_LOSSLESS     = 208,
    ID_RADIO_FAST       = 209,
    ID_RADIO_BALANCED   = 210,
    ID_RADIO_BEST       = 211,
    ID_PROGRESS         = 212,
    ID_EDIT_LOG         = 213,
    ID_BTN_START        = 214,
    ID_BTN_CANCEL       = 215,
    ID_STAT_RATIO       = 216,
    ID_STAT_SPEED       = 217,
    ID_STAT_TIME        = 218,
    ID_TIMER_ANIM       = 219,
    ID_LBL_STATUS       = 220,
    ID_LBL_DROP         = 221,
};

// ─── Color Palette ────────────────────────────────────────────────────────────
static const COLORREF CLR_BG         = RGB(10,  10,  26);   // Deep navy
static const COLORREF CLR_CARD       = RGB(18,  18,  40);   // Card bg
static const COLORREF CLR_BORDER     = RGB(40,  40,  80);   // Subtle border
static const COLORREF CLR_ACCENT     = RGB(0,   229, 255);  // Teal accent
static const COLORREF CLR_PURPLE     = RGB(124, 77,  255);  // Purple accent
static const COLORREF CLR_SUCCESS    = RGB(0,   230, 118);  // Green
static const COLORREF CLR_ERROR      = RGB(255, 82,  82);   // Red
static const COLORREF CLR_TEXT       = RGB(230, 230, 255);  // Primary text
static const COLORREF CLR_MUTED      = RGB(120, 120, 160);  // Muted text
static const COLORREF CLR_BTN_COMP   = RGB(0,   180, 200);  // Compress button
static const COLORREF CLR_BTN_DECOMP = RGB(100, 60,  200);  // Decompress button

// ─── Globals ──────────────────────────────────────────────────────────────────
HWND hMainWnd      = NULL;
HWND hRadioCompress= NULL, hRadioDecompress = NULL;
HWND hEditInput    = NULL, hEditOutput = NULL;
HWND hBtnBrowseIn  = NULL, hBtnBrowseOut = NULL;
HWND hChkSolid     = NULL, hChkLossless = NULL;
HWND hRadioFast    = NULL, hRadioBalanced = NULL, hRadioBest = NULL;
HWND hProgress     = NULL;
HWND hEditLog      = NULL;
HWND hBtnStart     = NULL, hBtnCancel = NULL;
HWND hLblStatus    = NULL;
HWND hStatRatio    = NULL, hStatSpeed = NULL, hStatTime = NULL;
HWND hLblDrop      = NULL;

HANDLE hChildProcess = NULL;
HANDLE hReadPipe     = NULL;
std::thread workerThread;
std::atomic<bool> bIsRunning(false);

HBRUSH hBrushBg    = NULL;
HBRUSH hBrushCard  = NULL;
HFONT  hFontMain   = NULL;
HFONT  hFontMono   = NULL;
HFONT  hFontTitle  = NULL;
HFONT  hFontStat   = NULL;

// ─── Helpers ─────────────────────────────────────────────────────────────────
static std::string ExtractJson(const std::string& json, const std::string& key) {
    size_t p = json.find("\"" + key + "\"");
    if (p == std::string::npos) return "";
    p = json.find(":", p);
    if (p == std::string::npos) return "";
    p++;
    while (p < json.size() && (json[p] == ' ' || json[p] == '\t')) p++;
    if (p >= json.size()) return "";
    if (json[p] == '"') {
        p++;
        size_t e = json.find('"', p);
        return e == std::string::npos ? "" : json.substr(p, e - p);
    } else {
        size_t e = p;
        while (e < json.size() && json[e] != ',' && json[e] != '}' && json[e] != '\r' && json[e] != '\n') e++;
        return json.substr(p, e - p);
    }
}

static std::wstring ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, NULL, 0);
    std::vector<wchar_t> buf(n);
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, buf.data(), n);
    return std::wstring(buf.data());
}

static std::wstring GetWndText(HWND h) {
    int n = GetWindowTextLengthW(h);
    if (n <= 0) return L"";
    std::vector<wchar_t> buf(n + 1);
    GetWindowTextW(h, buf.data(), n + 1);
    return std::wstring(buf.data());
}

static void AppendLog(const std::wstring& msg) {
    int len = GetWindowTextLengthW(hEditLog);
    SendMessageW(hEditLog, EM_SETSEL, len, len);
    SendMessageW(hEditLog, EM_REPLACESEL, 0, (LPARAM)msg.c_str());
}

static void AppendLogA(const std::string& msg) {
    AppendLog(ToWide(msg) + L"\r\n");
}

static void SetStat(HWND h, const wchar_t* label, const std::wstring& val) {
    std::wstring full = std::wstring(label) + L"\n" + val;
    SetWindowTextW(h, full.c_str());
    InvalidateRect(h, NULL, TRUE);
}

// ─── Dialogs ──────────────────────────────────────────────────────────────────
static std::wstring BrowseDialog(bool folderMode, bool saveMode) {
    std::wstring result;
    IFileDialog* pfd = NULL;
    CLSID clsid = saveMode ? CLSID_FileSaveDialog : CLSID_FileOpenDialog;
    IID   iid   = saveMode ? IID_IFileSaveDialog  : IID_IFileOpenDialog;
    if (SUCCEEDED(CoCreateInstance(clsid, NULL, CLSCTX_INPROC_SERVER, iid, (void**)&pfd))) {
        DWORD opts = 0;
        pfd->GetOptions(&opts);
        if (folderMode) pfd->SetOptions(opts | FOS_PICKFOLDERS);
        if (!folderMode && !saveMode) {
            COMDLG_FILTERSPEC ft[] = {
                { L"Lattice Archives (*.lattice)", L"*.lattice" },
                { L"All Files (*.*)",              L"*.*"       }
            };
            pfd->SetFileTypes(2, ft);
        }
        if (saveMode) {
            COMDLG_FILTERSPEC sf[] = {{ L"Lattice Archive (*.lattice)", L"*.lattice" }};
            pfd->SetFileTypes(1, sf);
            pfd->SetDefaultExtension(L"lattice");
        }
        if (SUCCEEDED(pfd->Show(hMainWnd))) {
            IShellItem* psi = NULL;
            if (SUCCEEDED(pfd->GetResult(&psi))) {
                LPWSTR pszPath = NULL;
                if (SUCCEEDED(psi->GetDisplayName(SIGDN_FILESYSPATH, &pszPath))) {
                    result = pszPath;
                    CoTaskMemFree(pszPath);
                }
                psi->Release();
            }
        }
        pfd->Release();
    }
    return result;
}

// ─── Drag-and-Drop ────────────────────────────────────────────────────────────
static void HandleDrop(HDROP hDrop) {
    wchar_t buf[MAX_PATH * 2];
    UINT count = DragQueryFileW(hDrop, 0xFFFFFFFF, NULL, 0);
    if (count > 0) {
        DragQueryFileW(hDrop, 0, buf, MAX_PATH * 2);
        SetWindowTextW(hEditInput, buf);
        // Auto-fill output
        std::wstring out = buf;
        bool isDir = (GetFileAttributesW(buf) & FILE_ATTRIBUTE_DIRECTORY) != 0;
        if (isDir) {
            while (!out.empty() && (out.back() == L'\\' || out.back() == L'/')) out.pop_back();
        }
        // Only auto-fill if compress mode
        if (SendMessageW(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED) {
            out += L".lattice";
            SetWindowTextW(hEditOutput, out.c_str());
        }
        // Set window title to show dragged item
        SetWindowTextW(hMainWnd, (std::wstring(L"Lattice \u2014 ") + buf).c_str());
    }
    DragFinish(hDrop);
}

// ─── Worker Thread ────────────────────────────────────────────────────────────
static void PipeReaderThread() {
    char raw[4096];
    DWORD got;
    std::string lineBuf;

    while (ReadFile(hReadPipe, raw, sizeof(raw) - 1, &got, NULL) && got > 0) {
        raw[got] = '\0';
        lineBuf += raw;
        size_t pos;
        while ((pos = lineBuf.find('\n')) != std::string::npos) {
            std::string line = lineBuf.substr(0, pos);
            lineBuf.erase(0, pos + 1);
            // Trim
            while (!line.empty() && (line.front() == ' ' || line.front() == '\r' || line.front() == '\t')) line.erase(line.begin());
            while (!line.empty() && (line.back()  == ' ' || line.back()  == '\r' || line.back()  == '\t')) line.pop_back();
            if (line.empty()) continue;

            if (line.front() == '{' && line.back() == '}') {
                std::string type = ExtractJson(line, "type");
                if (type == "status") {
                    std::string s = ExtractJson(line, "status");
                    SetWindowTextW(hLblStatus, ToWide("[" + s + "]").c_str());
                    AppendLogA("\u25B6 " + s);
                } else if (type == "file_progress") {
                    std::string pct  = ExtractJson(line, "percent");
                    std::string file = ExtractJson(line, "file");
                    double p = pct.empty() ? 0 : std::stod(pct);
                    SendMessageW(hProgress, PBM_SETPOS, (WPARAM)(int)p, 0);
                    SetWindowTextW(hLblStatus, ToWide("\u25B6 " + file + " (" + pct + "%)").c_str());
                } else if (type == "progress") {
                    std::string pct  = ExtractJson(line, "percent");
                    std::string file = ExtractJson(line, "file");
                    double p = pct.empty() ? 0 : std::stod(pct);
                    SendMessageW(hProgress, PBM_SETPOS, (WPARAM)(int)p, 0);
                    SetWindowTextW(hLblStatus, ToWide(file + " (" + pct + "%)").c_str());
                } else if (type == "done") {
                    std::string origStr  = ExtractJson(line, "original_size");
                    std::string compStr  = ExtractJson(line, "compressed_size");
                    std::string ratioStr = ExtractJson(line, "ratio");
                    std::string elapsed  = ExtractJson(line, "elapsed");
                    std::string tput     = ExtractJson(line, "throughput_mbps");

                    SendMessageW(hProgress, PBM_SETPOS, 100, 0);
                    SetWindowTextW(hLblStatus, L"\u2705 Done!");
                    SetStat(hStatRatio, L"RATIO",  ToWide(ratioStr + "x"));
                    SetStat(hStatSpeed, L"SPEED",  ToWide(tput + " MB/s"));
                    SetStat(hStatTime,  L"TIME",   ToWide(elapsed + "s"));

                    AppendLog(L"\r\n\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\r\n");
                    AppendLogA("\u2728 COMPRESSION COMPLETE");
                    if (!origStr.empty())  AppendLogA("   Original : " + origStr + " bytes");
                    if (!compStr.empty() && compStr != "0") {
                        AppendLogA("   Output   : " + compStr + " bytes");
                        AppendLogA("   Ratio    : " + ratioStr + "x");
                        AppendLogA("   Speed    : " + tput + " MB/s");
                    }
                    AppendLogA("   Time     : " + elapsed + "s");
                    AppendLog(L"\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\r\n");
                } else if (type == "error") {
                    std::string msg = ExtractJson(line, "message");
                    AppendLogA("\u274C ERROR: " + msg);
                    SetWindowTextW(hLblStatus, L"\u274C Error");
                    MessageBoxA(hMainWnd, msg.c_str(), "Lattice Engine Error", MB_ICONERROR);
                }
            } else {
                AppendLogA(line);
            }
        }
    }

    WaitForSingleObject(hChildProcess, INFINITE);
    CloseHandle(hChildProcess); CloseHandle(hReadPipe);
    hChildProcess = NULL; hReadPipe = NULL;
    bIsRunning = false;

    // Re-enable controls on UI thread
    PostMessageW(hMainWnd, WM_USER + 1, 0, 0);
}

// ─── Start / Cancel ────────────────────────────────────────────────────────────
static void StartEngine() {
    std::wstring inp = GetWndText(hEditInput);
    std::wstring out = GetWndText(hEditOutput);
    // Trim trailing slashes
    while (inp.size() > 3 && (inp.back() == L'\\' || inp.back() == L'/')) inp.pop_back();
    while (out.size() > 3 && (out.back() == L'\\' || out.back() == L'/')) out.pop_back();

    if (inp.empty() || out.empty()) {
        MessageBoxW(hMainWnd, L"Please set both source and output paths.", L"Missing Paths", MB_ICONWARNING);
        return;
    }

    bool isCompress = SendMessageW(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isSolid    = SendMessageW(hChkSolid,      BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isVL       = SendMessageW(hChkLossless,   BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isFast     = SendMessageW(hRadioFast,     BM_GETCHECK, 0, 0) == BST_CHECKED;
    bool isBest     = SendMessageW(hRadioBest,     BM_GETCHECK, 0, 0) == BST_CHECKED;

    // Locate lattice_cli.exe
    wchar_t exeBuf[MAX_PATH];
    GetModuleFileNameW(NULL, exeBuf, MAX_PATH);
    std::wstring dir = exeBuf;
    size_t sl = dir.find_last_of(L"\\/");
    dir = (sl != std::wstring::npos) ? dir.substr(0, sl + 1) : L".\\";

    std::wstring cliPath = dir + L"lattice_cli.exe";
    if (GetFileAttributesW(cliPath.c_str()) == INVALID_FILE_ATTRIBUTES)
        cliPath = dir + L"..\\lattice_cli.exe";
    if (GetFileAttributesW(cliPath.c_str()) == INVALID_FILE_ATTRIBUTES)
        cliPath = L"lattice_cli.exe";

    std::wstringstream cmd;
    cmd << L"\"" << cliPath << L"\" ";
    if (isCompress) {
        cmd << L"compress \"" << inp << L"\" \"" << out << L"\"";
        if (isSolid)  cmd << L" --solid";
        if (isVL)     cmd << L" --virtually-lossless";
        if (isFast)   cmd << L" --fast";
        if (isBest)   cmd << L" --best";
    } else {
        cmd << L"decompress \"" << inp << L"\" \"" << out << L"\"";
    }
    std::wstring cmdLine = cmd.str();

    // Create pipe
    HANDLE hWrite;
    SECURITY_ATTRIBUTES sa = { sizeof(sa), NULL, TRUE };
    if (!CreatePipe(&hReadPipe, &hWrite, &sa, 0)) {
        MessageBoxW(hMainWnd, L"Pipe creation failed.", L"Error", MB_ICONERROR);
        return;
    }
    SetHandleInformation(hReadPipe, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW si = {};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = si.hStdError = hWrite;

    PROCESS_INFORMATION pi = {};
    std::vector<wchar_t> cmdBuf(cmdLine.begin(), cmdLine.end());
    cmdBuf.push_back(0);

    // Clear log & reset stats
    SetWindowTextW(hEditLog, L"");
    SetWindowTextW(hLblStatus, L"\u25B6 Starting...");
    SendMessageW(hProgress, PBM_SETPOS, 0, 0);
    SetStat(hStatRatio, L"RATIO", L"\u2014");
    SetStat(hStatSpeed, L"SPEED", L"\u2014");
    SetStat(hStatTime,  L"TIME",  L"\u2014");
    AppendLog(L"\u25B6 " + cmdLine + L"\r\n\r\n");

    if (!CreateProcessW(NULL, cmdBuf.data(), NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
        DWORD e = GetLastError();
        std::wstringstream es;
        es << L"Could not launch lattice_cli.exe (error " << e << L")\nPath: " << cliPath;
        MessageBoxW(hMainWnd, es.str().c_str(), L"Launch Error", MB_ICONERROR);
        CloseHandle(hReadPipe); CloseHandle(hWrite);
        return;
    }
    CloseHandle(hWrite);
    CloseHandle(pi.hThread);
    hChildProcess = pi.hProcess;

    bIsRunning = true;
    // Disable inputs
    EnableWindow(hBtnStart,       FALSE);
    EnableWindow(hEditInput,      FALSE);
    EnableWindow(hEditOutput,     FALSE);
    EnableWindow(hBtnBrowseIn,    FALSE);
    EnableWindow(hBtnBrowseOut,   FALSE);
    EnableWindow(hRadioCompress,  FALSE);
    EnableWindow(hRadioDecompress,FALSE);
    SetWindowTextW(hBtnCancel, L"Cancel");

    workerThread = std::thread(PipeReaderThread);
    workerThread.detach();
}

static void CancelEngine() {
    if (bIsRunning && hChildProcess) {
        TerminateProcess(hChildProcess, 1);
        AppendLog(L"\r\n[Cancelled]\r\n");
        SetWindowTextW(hLblStatus, L"\u26D4 Cancelled");
        SendMessageW(hProgress, PBM_SETPOS, 0, 0);
    }
}

// ─── Custom Draw helpers ──────────────────────────────────────────────────────
static void PaintStatCard(HWND hWnd) {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hWnd, &ps);
    RECT rc;
    GetClientRect(hWnd, &rc);

    // Background
    HBRUSH bgBr = CreateSolidBrush(CLR_CARD);
    FillRect(hdc, &rc, bgBr);
    DeleteObject(bgBr);

    // Border
    HPEN borderPen = CreatePen(PS_SOLID, 1, CLR_BORDER);
    HPEN oldPen = (HPEN)SelectObject(hdc, borderPen);
    HBRUSH oldBr = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
    RoundRect(hdc, rc.left, rc.top, rc.right - 1, rc.bottom - 1, 8, 8);
    SelectObject(hdc, oldPen);
    SelectObject(hdc, oldBr);
    DeleteObject(borderPen);

    // Text
    SetBkMode(hdc, TRANSPARENT);
    int wlen = GetWindowTextLengthW(hWnd);
    std::vector<wchar_t> buf(wlen + 2);
    GetWindowTextW(hWnd, buf.data(), wlen + 1);
    std::wstring full(buf.data());

    // Split at newline
    size_t nl = full.find(L'\n');
    std::wstring label = (nl != std::wstring::npos) ? full.substr(0, nl) : full;
    std::wstring value = (nl != std::wstring::npos) ? full.substr(nl + 1) : L"\u2014";

    // Label (muted small text at top)
    RECT rcLabel = { rc.left + 8, rc.top + 6, rc.right - 4, rc.top + 24 };
    HFONT fSmall = CreateFontW(12, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    HFONT old = (HFONT)SelectObject(hdc, fSmall);
    SetTextColor(hdc, CLR_MUTED);
    DrawTextW(hdc, label.c_str(), -1, &rcLabel, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    DeleteObject(SelectObject(hdc, old));

    // Value (big accent text)
    RECT rcVal = { rc.left + 8, rc.top + 22, rc.right - 4, rc.bottom - 4 };
    HFONT fBig = CreateFontW(22, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
    old = (HFONT)SelectObject(hdc, fBig);
    SetTextColor(hdc, CLR_ACCENT);
    DrawTextW(hdc, value.c_str(), -1, &rcVal, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
    DeleteObject(SelectObject(hdc, old));

    EndPaint(hWnd, &ps);
}

// Custom stat card window class
static LRESULT CALLBACK StatCardProc(HWND h, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_PAINT) { PaintStatCard(h); return 0; }
    if (msg == WM_ERASEBKGND) return 1;
    return DefWindowProcW(h, msg, wp, lp);
}

// ─── Main Window Proc ─────────────────────────────────────────────────────────
static LRESULT CALLBACK WndProc(HWND hWnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {

    case WM_CREATE: {
        DragAcceptFiles(hWnd, TRUE);

        hBrushBg   = CreateSolidBrush(CLR_BG);
        hBrushCard = CreateSolidBrush(CLR_CARD);

        hFontMain  = CreateFontW(15, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
        hFontMono  = CreateFontW(13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            FIXED_PITCH | FF_MODERN, L"Consolas");
        hFontTitle = CreateFontW(20, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
        hFontStat  = CreateFontW(24, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
            OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");

        // Enable dark title bar on Windows 11 (runtime check — graceful degradation)
        {
            typedef HRESULT(WINAPI* PFN_DwmSetWA)(HWND, DWORD, LPCVOID, DWORD);
            HMODULE hDwm = GetModuleHandleW(L"dwmapi.dll");
            if (!hDwm) hDwm = LoadLibraryW(L"dwmapi.dll");
            if (hDwm) {
                auto pfn = (PFN_DwmSetWA)GetProcAddress(hDwm, "DwmSetWindowAttribute");
                if (pfn) { BOOL d = TRUE; pfn(hWnd, 20, &d, sizeof(d)); }
            }
        }

        // ── MODE SELECTOR ──────────────────────────────────────────────
        // Two large mode buttons as radio buttons
        hRadioCompress = CreateWindowW(L"BUTTON", L"\U0001F5DC  COMPRESS",
            WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON | WS_GROUP,
            20, 60, 200, 36, hWnd, (HMENU)ID_RADIO_COMPRESS, NULL, NULL);
        hRadioDecompress = CreateWindowW(L"BUTTON", L"\U0001F4C2  DECOMPRESS",
            WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON,
            230, 60, 200, 36, hWnd, (HMENU)ID_RADIO_DECOMPRESS, NULL, NULL);
        SendMessageW(hRadioCompress, BM_SETCHECK, BST_CHECKED, 0);
        SendMessageW(hRadioCompress, WM_SETFONT, (WPARAM)hFontMain, TRUE);
        SendMessageW(hRadioDecompress, WM_SETFONT, (WPARAM)hFontMain, TRUE);

        // ── INPUT PATH ─────────────────────────────────────────────────
        HWND lbl1 = CreateWindowW(L"STATIC", L"Source:", WS_CHILD | WS_VISIBLE, 20, 115, 60, 20, hWnd, NULL, NULL, NULL);
        hEditInput = CreateWindowW(L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
            20, 135, 520, 26, hWnd, (HMENU)ID_EDIT_INPUT, NULL, NULL);
        hBtnBrowseIn = CreateWindowW(L"BUTTON", L"Browse...",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            550, 134, 100, 28, hWnd, (HMENU)ID_BTN_BROWSE_IN, NULL, NULL);

        // ── OUTPUT PATH ────────────────────────────────────────────────
        HWND lbl2 = CreateWindowW(L"STATIC", L"Output:", WS_CHILD | WS_VISIBLE, 20, 172, 60, 20, hWnd, NULL, NULL, NULL);
        hEditOutput = CreateWindowW(L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
            20, 192, 520, 26, hWnd, (HMENU)ID_EDIT_OUTPUT, NULL, NULL);
        hBtnBrowseOut = CreateWindowW(L"BUTTON", L"Browse...",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            550, 191, 100, 28, hWnd, (HMENU)ID_BTN_BROWSE_OUT, NULL, NULL);

        // ── OPTIONS ROW ────────────────────────────────────────────────
        hChkSolid = CreateWindowW(L"BUTTON", L"Solid Block",
            WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 20, 234, 120, 22, hWnd, (HMENU)ID_CHK_SOLID, NULL, NULL);
        hChkLossless = CreateWindowW(L"BUTTON", L"Virtually Lossless",
            WS_CHILD | WS_VISIBLE | BS_AUTOCHECKBOX, 150, 234, 160, 22, hWnd, (HMENU)ID_CHK_LOSSLESS, NULL, NULL);
        SendMessageW(hChkSolid, BM_SETCHECK, BST_CHECKED, 0);

        // Speed mode selector
        HWND lbl3 = CreateWindowW(L"STATIC", L"Speed:", WS_CHILD | WS_VISIBLE, 330, 234, 50, 22, hWnd, NULL, NULL, NULL);
        hRadioFast = CreateWindowW(L"BUTTON", L"Fast",
            WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON | WS_GROUP, 385, 234, 58, 22, hWnd, (HMENU)ID_RADIO_FAST, NULL, NULL);
        hRadioBalanced = CreateWindowW(L"BUTTON", L"Balanced",
            WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON, 448, 234, 78, 22, hWnd, (HMENU)ID_RADIO_BALANCED, NULL, NULL);
        hRadioBest = CreateWindowW(L"BUTTON", L"Best",
            WS_CHILD | WS_VISIBLE | BS_AUTORADIOBUTTON, 530, 234, 58, 22, hWnd, (HMENU)ID_RADIO_BEST, NULL, NULL);
        SendMessageW(hRadioBalanced, BM_SETCHECK, BST_CHECKED, 0);

        // ── STAT CARDS ─────────────────────────────────────────────────
        hStatRatio = CreateWindowW(L"STATCARD", L"RATIO\n\u2014",
            WS_CHILD | WS_VISIBLE, 20, 270, 195, 58, hWnd, (HMENU)ID_STAT_RATIO, NULL, NULL);
        hStatSpeed = CreateWindowW(L"STATCARD", L"SPEED\n\u2014",
            WS_CHILD | WS_VISIBLE, 222, 270, 195, 58, hWnd, (HMENU)ID_STAT_SPEED, NULL, NULL);
        hStatTime  = CreateWindowW(L"STATCARD", L"TIME\n\u2014",
            WS_CHILD | WS_VISIBLE, 424, 270, 222, 58, hWnd, (HMENU)ID_STAT_TIME, NULL, NULL);

        // ── PROGRESS ───────────────────────────────────────────────────
        hProgress = CreateWindowW(PROGRESS_CLASSW, L"",
            WS_CHILD | WS_VISIBLE | PBS_SMOOTH,
            20, 340, 630, 16, hWnd, (HMENU)ID_PROGRESS, NULL, NULL);
        SendMessageW(hProgress, PBM_SETRANGE, 0, MAKELPARAM(0, 100));
        SendMessageW(hProgress, PBM_SETBARCOLOR, 0, CLR_ACCENT);
        SendMessageW(hProgress, PBM_SETBKCOLOR,  0, CLR_BORDER);

        hLblStatus = CreateWindowW(L"STATIC", L"\u25CB Idle \u2014 drop files or browse to begin",
            WS_CHILD | WS_VISIBLE, 20, 360, 630, 20, hWnd, (HMENU)ID_LBL_STATUS, NULL, NULL);

        // ── LOG ────────────────────────────────────────────────────────
        hEditLog = CreateWindowW(L"EDIT", L"",
            WS_CHILD | WS_VISIBLE | WS_BORDER | WS_VSCROLL |
            ES_MULTILINE | ES_READONLY | ES_AUTOVSCROLL,
            20, 388, 630, 160, hWnd, (HMENU)ID_EDIT_LOG, NULL, NULL);

        // ── BUTTONS ────────────────────────────────────────────────────
        hBtnStart = CreateWindowW(L"BUTTON", L"\u25BA  Start",
            WS_CHILD | WS_VISIBLE | BS_DEFPUSHBUTTON,
            450, 560, 90, 32, hWnd, (HMENU)ID_BTN_START, NULL, NULL);
        hBtnCancel = CreateWindowW(L"BUTTON", L"Exit",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            550, 560, 100, 32, hWnd, (HMENU)ID_BTN_CANCEL, NULL, NULL);

        // ── FONTS on all controls ──────────────────────────────────────
        for (HWND h : { lbl1, lbl2, lbl3,
                        hChkSolid, hChkLossless,
                        hRadioFast, hRadioBalanced, hRadioBest,
                        hLblStatus }) {
            SendMessageW(h, WM_SETFONT, (WPARAM)hFontMain, TRUE);
        }
        for (HWND h : { hEditInput, hEditOutput }) {
            SendMessageW(h, WM_SETFONT, (WPARAM)hFontMain, TRUE);
        }
        SendMessageW(hEditLog,    WM_SETFONT, (WPARAM)hFontMono,  TRUE);
        SendMessageW(hBtnStart,   WM_SETFONT, (WPARAM)hFontMain,  TRUE);
        SendMessageW(hBtnCancel,  WM_SETFONT, (WPARAM)hFontMain,  TRUE);
        SendMessageW(hBtnBrowseIn, WM_SETFONT,(WPARAM)hFontMain,  TRUE);
        SendMessageW(hBtnBrowseOut,WM_SETFONT,(WPARAM)hFontMain,  TRUE);
        break;
    }

    case WM_DROPFILES:
        HandleDrop((HDROP)wp);
        break;

    case WM_CTLCOLORSTATIC: {
        HDC hdc = (HDC)wp;
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, CLR_TEXT);
        return (LRESULT)hBrushBg;
    }
    case WM_CTLCOLOREDIT: {
        HDC hdc = (HDC)wp;
        SetBkColor(hdc, CLR_CARD);
        SetTextColor(hdc, CLR_TEXT);
        return (LRESULT)hBrushCard;
    }
    case WM_CTLCOLORBTN:
        return (LRESULT)hBrushBg;

    case WM_ERASEBKGND: {
        RECT rc; GetClientRect(hWnd, &rc);
        FillRect((HDC)wp, &rc, hBrushBg);
        return 1;
    }

    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hWnd, &ps);
        // Title bar area
        RECT rcTitle = { 20, 14, 500, 50 };
        SetBkMode(hdc, TRANSPARENT);
        HFONT old = (HFONT)SelectObject(hdc, hFontTitle);
        SetTextColor(hdc, CLR_ACCENT);
        DrawTextW(hdc, L"\u22C4 Lattice Compression Engine", -1, &rcTitle, DT_LEFT | DT_SINGLELINE | DT_VCENTER);
        SelectObject(hdc, old);

        // Separator lines
        HPEN sep = CreatePen(PS_SOLID, 1, CLR_BORDER);
        HPEN oldPen = (HPEN)SelectObject(hdc, sep);
        MoveToEx(hdc, 20, 108, NULL); LineTo(hdc, 660, 108);
        MoveToEx(hdc, 20, 225, NULL); LineTo(hdc, 660, 225);
        MoveToEx(hdc, 20, 264, NULL); LineTo(hdc, 660, 264);
        MoveToEx(hdc, 20, 382, NULL); LineTo(hdc, 660, 382);
        MoveToEx(hdc, 20, 554, NULL); LineTo(hdc, 660, 554);
        SelectObject(hdc, oldPen);
        DeleteObject(sep);
        EndPaint(hWnd, &ps);
        return 0;
    }

    case WM_COMMAND: {
        int id = LOWORD(wp);
        switch (id) {
        case ID_RADIO_COMPRESS:
        case ID_RADIO_DECOMPRESS:
            break;
        case ID_BTN_BROWSE_IN: {
            bool isCompress = SendMessageW(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
            std::wstring path;
            if (isCompress) {
                int r = MessageBoxW(hWnd, L"Compress a single FILE (Yes) or a whole FOLDER (No)?",
                    L"Select Input Type", MB_YESNOCANCEL | MB_ICONQUESTION);
                if (r == IDYES)       path = BrowseDialog(false, false);
                else if (r == IDNO)   path = BrowseDialog(true,  false);
            } else {
                path = BrowseDialog(false, false);
            }
            if (!path.empty()) {
                SetWindowTextW(hEditInput, path.c_str());
                if (isCompress) {
                    std::wstring out = path;
                    while (!out.empty() && (out.back() == L'\\' || out.back() == L'/')) out.pop_back();
                    out += L".lattice";
                    SetWindowTextW(hEditOutput, out.c_str());
                } else {
                    std::wstring out = path;
                    size_t ep = out.find(L".lattice");
                    if (ep != std::wstring::npos) out = out.substr(0, ep) + L"_extracted";
                    else out += L"_extracted";
                    SetWindowTextW(hEditOutput, out.c_str());
                }
            }
            break;
        }
        case ID_BTN_BROWSE_OUT: {
            bool isCompress = SendMessageW(hRadioCompress, BM_GETCHECK, 0, 0) == BST_CHECKED;
            std::wstring path = isCompress ? BrowseDialog(false, true) : BrowseDialog(true, false);
            if (!path.empty()) SetWindowTextW(hEditOutput, path.c_str());
            break;
        }
        case ID_BTN_START:
            StartEngine();
            break;
        case ID_BTN_CANCEL:
            if (bIsRunning) CancelEngine();
            else DestroyWindow(hWnd);
            break;
        }
        break;
    }

    case WM_USER + 1: {
        // Worker thread finished — re-enable controls
        EnableWindow(hBtnStart,        TRUE);
        EnableWindow(hEditInput,       TRUE);
        EnableWindow(hEditOutput,      TRUE);
        EnableWindow(hBtnBrowseIn,     TRUE);
        EnableWindow(hBtnBrowseOut,    TRUE);
        EnableWindow(hRadioCompress,   TRUE);
        EnableWindow(hRadioDecompress, TRUE);
        SetWindowTextW(hBtnCancel, L"Exit");
        break;
    }

    case WM_DESTROY:
        DeleteObject(hBrushBg);
        DeleteObject(hBrushCard);
        DeleteObject(hFontMain);
        DeleteObject(hFontMono);
        DeleteObject(hFontTitle);
        DeleteObject(hFontStat);
        PostQuitMessage(0);
        break;

    default:
        return DefWindowProcW(hWnd, msg, wp, lp);
    }
    return 0;
}

// ─── WinMain ─────────────────────────────────────────────────────────────────
int APIENTRY WinMain(HINSTANCE hInst, HINSTANCE, LPSTR, int nShow) {
    CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);

    INITCOMMONCONTROLSEX icex = { sizeof(icex), ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES };
    InitCommonControlsEx(&icex);

    // Register stat-card window class
    WNDCLASSEXW wsc = {};
    wsc.cbSize        = sizeof(wsc);
    wsc.lpfnWndProc   = StatCardProc;
    wsc.hInstance     = hInst;
    wsc.hbrBackground = CreateSolidBrush(CLR_CARD);
    wsc.lpszClassName = L"STATCARD";
    RegisterClassExW(&wsc);

    // Register main window class
    WNDCLASSEXW wc = {};
    wc.cbSize        = sizeof(wc);
    wc.style         = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc   = WndProc;
    wc.hInstance     = hInst;
    wc.hIcon         = LoadIconW(hInst, MAKEINTRESOURCEW(IDI_ICON1));
    if (!wc.hIcon)   wc.hIcon = LoadIconW(NULL, (LPCWSTR)IDI_APPLICATION);
    wc.hCursor       = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hbrBackground = CreateSolidBrush(CLR_BG);
    wc.lpszClassName = L"LatticeMainWnd";
    wc.hIconSm       = wc.hIcon;
    RegisterClassExW(&wc);

    // Window size
    RECT rc = { 0, 0, 680, 608 };
    AdjustWindowRect(&rc, WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX, FALSE);

    hMainWnd = CreateWindowExW(
        WS_EX_ACCEPTFILES,
        L"LatticeMainWnd",
        L"\u22C4 Lattice Compression Engine",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT,
        rc.right - rc.left, rc.bottom - rc.top,
        NULL, NULL, hInst, NULL);

    if (!hMainWnd) return 1;

    ShowWindow(hMainWnd, nShow);
    UpdateWindow(hMainWnd);

    MSG m;
    while (GetMessageW(&m, NULL, 0, 0)) {
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
    CoUninitialize();
    return (int)m.wParam;
}
