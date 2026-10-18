# PC Atlas 電腦規格總覽

以繁體中文瀏覽多台電腦的硬體、作業系統與已安裝軟體。`pc_china` 已從這台 Windows 電腦擷取實際規格；`pc_sdl`、`pc_data`、`pc_rtx`、`pc_5090` 尚待匯入。

## 用 VS Code Live Server 開啟

已設定 Live Server（`ritwickdey.LiveServer`）。以 VS Code 開啟 `D:\ai\pc` 或 `pc-inventory` 專案資料夾，按右下角 **Go Live**，即可瀏覽 <http://127.0.0.1:5500>，修改並儲存檔案後自動重新整理。兩層資料夾均已設定正確的 `dist` 網站根目錄。

## 用 Node.js 開啟網站

需 Node.js，不需安裝執行階段依賴。在專案資料夾執行：

```powershell
node serve.mjs
```

瀏覽 <http://127.0.0.1:4173>。請透過伺服器開啟，直接以 `file://` 開啟會受瀏覽器模組與 JSON 存取限制。

網站包含電腦切換、硬體與軟體搜尋、軟體名稱排序、設備規格比較、JSON 匯入與匯出，以及手機版介面。按 `/` 可跳至設備搜尋。

## 加入或更新電腦

將 `collect-pc.ps1` 複製至目標 Windows 電腦，在該資料夾的 PowerShell 執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\collect-pc.ps1 -Name pc_sdl
```

名稱可改為 `pc_data`、`pc_rtx`、`pc_5090` 或其他英數字與底線名稱。產生的 `pc_sdl.json` 有兩種使用方式：

- 網頁按「匯入電腦規格」或右上角 `?` 匯入 JSON。資料保存在該瀏覽器的 localStorage；不會同步至其他裝置。匯入相同名稱會替換原有資料。
- 要永久納入網站內建資料，回到本專案執行 `node manage-inventory.mjs pc_sdl.json`。它會驗證資料、更新 `dist/data/` 與資料目錄。重新整理本機網站即可；線上網站需要重新部署。

匯出的 `pc-atlas-inventory.json` 包含所有已擷取設備，也可透過相同方式匯入。預留設備不包含虛構規格，因此不會出現在匯出資料內。清除瀏覽器資料前請先匯出備份。

更新本機 `pc_china`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\collect-pc.ps1 -Name pc_china -OutputPath .\dist\data\pc_china.json
```

每次修改擷取腳本後，請同步 `collect-pc.ps1` 到 `dist/collect-pc.ps1`（網頁下載版本）。Windows PowerShell 5.1 需要腳本使用 UTF-8 BOM 編碼。

## 資料說明

- 硬體與 OS：Windows CIM。NVIDIA 顯示記憶體和驅動優先使用 `nvidia-smi`；沒有可靠數值時顯示「未取得」。
- 軟體：Windows 系統及目前使用者的 Uninstall 登錄檔，排除系統元件、依名稱與版本去重。並非所有可攜式程式、Store App 或 Python/npm 套件。
- 開發工具：PATH 中可執行的 Node.js、Python、Git、Docker、CUDA compiler 版本。
- 規格為擷取當下快照，無自動連線至各台電腦。日期統一顯示 Asia/Taipei。
- 記憶體與容量使用二進位 GiB/TiB，介面簡記 GB/TB。虛擬磁碟區不計入實體磁碟總容量。
- 不蒐集裝置序號、IP、MAC、使用者帳號、授權金鑰或環境變數。
- 網站為靜態 HTML/CSS/JavaScript，Sites 初始存取權限為私人。字型由 Google Fonts 載入，離線時使用系統字型。

## 驗證

```powershell
npm.cmd run check
```

`tests/inventory.test.mjs` 驗證真實快照、預留設備、匯入與取代、錯誤資料處理、搜尋及 HTML 跳脫。
