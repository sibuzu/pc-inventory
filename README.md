# PC Atlas 電腦規格總覽

以繁體中文瀏覽多台電腦的硬體、作業系統與已安裝軟體。介面使用淺色主題與黑字，左側選單可獨立捲動。設備順序為 `pc_china`、`pc_sdl`、`pc_data`、`pc_rtx`、`rtx_5090`、`pc_one`、`pc_andy`、`pc_nas`；pc_one 與 pc_andy 的工作用途暫留空白。

## 透過 SSH 盤點

在管理電腦上使用 Python 3.10 以上與 SSH 金鑰登入。遠端 Linux 支援 Python 3.4 以上，並相容 Docker 1.13；不安裝遠端套件。

首次授權 Windows 主機可在管理電腦執行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/authorize-windows-ssh.ps1 -ComputerName 192.168.100.199`，密碼僅輸入於本機終端機。若 SSH 設定明確指定使用者的 `.ssh/authorized_keys` 且沒有 Match／Include 規則，腳本使用該路徑；其他情況依帳號群組選擇 Windows 預設授權檔。腳本修復授權檔的擁有者／ACL，保留既有金鑰並加入本機 `id_rsa.pub`，最後驗證 `SSH_OK`。異常編碼的檔案會保留並回報錯誤。遠端登入權限不足以修復 ACL 時，需在目標機器以系統管理員 PowerShell 處理；不修改 sshd 設定或停用密碼登入。

SSH 登入失敗時，可執行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/diagnose-windows-ssh.ps1 -ComputerName 192.168.100.199`。唯讀檢查 SSH 設定、授權檔 ACL、編碼與公鑰指紋，逐項顯示並將報告寫入 `.sites-runtime/ssh-diagnostics-192.168.100.199.txt`；不對異常格式檔案執行金鑰解析。

```powershell
# Linux（此處 pc_sdl 是本機 SSH config 別名）
python collect-ssh.py --host pc_sdl --name pc_sdl --output .sites-runtime/pc_sdl-raw.json
# Windows
python collect-ssh.py --host jack@192.168.100.186 --platform windows --name pc_data --output .sites-runtime/pc_data-raw.json
python collect-ssh.py --host jack@192.168.100.180 --platform windows --name pc_rtx --output .sites-runtime/pc_rtx-raw.json
python collect-ssh.py --host jack@192.168.100.156 --platform windows --name rtx_5090 --output .sites-runtime/rtx_5090-raw.json
python collect-ssh.py --host jack@192.168.100.190 --platform windows --name pc_one --storage-seconds 600 --output .sites-runtime/pc_one-raw.json
python collect-ssh.py --host jack@192.168.100.199 --platform windows --name pc_andy --storage-seconds 600 --expand-over-gb 5 --output .sites-runtime/pc_andy-raw.json
# QNAP（pc_nas 是本機 SSH config 別名，admin@192.168.100.185）
python collect-ssh.py --host pc_nas --platform qnap --name pc_nas --output .sites-runtime/pc_nas-raw.json
# 僅更新 CUDA、PyTorch 和環境套件（output 必須已存在）
python collect-ssh.py --host pc_sdl --name pc_sdl --output .sites-runtime/pc_sdl-raw.json --only-ai
# 更新網站內建資料，保留原有歷史快照與較新的 AI 盤點
node manage-inventory.mjs .sites-runtime/pc_sdl-raw.json
```

Linux 使用 SSH stdin 執行採集程式；Windows 先透過 SCP 傳送一次性來源資料與短指令啟動的 PowerShell 腳本，避免 Windows 命令列長度限制，完成後清除本次檔案。Windows 預設使用 PATH 中的 Python；只有 Windows Store 別名時，可傳入 `--python-archive <本機官方 Windows embeddable Python ZIP>`，暫存解壓後執行並清除，不安裝 Python，也不將暫存執行環境列入 AI／Python 清單。工具只查詢狀態，不啟停容器或子系統、不安裝或升級套件。Windows 新盤點預設採用 5 GB 展開門檻，`--expand-over-gb` 可調整。預設使用每個磁碟區 45 秒掃描預算，可用 `--storage-seconds 600` 增加時間。

Linux 的硬體來源包含 `/proc`、`/sys`；若 `sudo -n dmidecode -t 17` 已獲授權，會擷取 DIMM 容量、插槽、型號及時脈，不保存序號。無權限時使用 OS 可見的 MemTotal 並標明來源。軟體清單為已安裝 dpkg 套件。Linux Docker 透過本機 Unix socket 執行 GET 查詢，記錄 Engine OS、Image OS/架構/大小、容器可寫層與 Volume 使用量。Image 共用層總量使用 Engine 的 LayersSize，不重複加總各 Image 的大小。未提供的回收空間與快取保留未知。

## CUDA / PyTorch：所有設備的統一欄位

總覽顯示 CUDA／PyTorch 摘要，「系統環境」提供詳細盤點：

- NVIDIA 驅動版本、`nvidia-smi` 回報的 CUDA 支援上限。
- 可執行的 `nvcc` 與常見 CUDA 安裝目錄；目錄來源與 nvcc 驗證來源分開標示。
- PATH、常見 Anaconda/Miniconda、Conda 註冊環境、`~/.virtualenvs` 與執行中容器的 Python 環境。
- 每個環境的 Python、PyTorch、PyTorch 編譯 CUDA、cuDNN 原始版本碼、GPU 可用狀態與裝置數。
- Python distribution metadata 與 `conda-meta` 的套件名稱、版本、來源與 Build；按環境樹狀展開與搜尋。這些套件與 OS 軟體清單分開呈現。

本機可執行 `python scripts/ai-probe.py` 輸出 AI 盤點 JSON。SSH 採集會自動整合此資訊，`--only-ai` 可單獨更新。沒有回報的欄位保留未知，不根據驅動、Toolkit 或 PyTorch 的其中一個版本推測其他版本；CPU build 與 CUDA build 分開顯示。未註冊的專案 venv、未執行的容器、沒有 Python 的映像檔不會被啟動掃描。探測 PyTorch 會載入該環境的套件，但不執行訓練。

更新採集工具後，請同步 `collect-ssh.py` 與 `scripts/` 中的四個採集工具至 `dist/` 對應位置，讓網頁下載版本保持一致。

QNAP 使用 NAS 內建 Python 2.7，擷取型號、QTS、DIMM、硬碟、MD RAID、已掛載磁碟區及 QPKG/App Center 清單。硬碟原始容量、RAID 容量與磁碟區容量分開呈現。資料夾掃描保留原生位元組路徑，以支援中文名稱，略過符號連結、其他掛載點與快照目錄；不讀取檔案內容或安裝套件。

比較表的「已用儲存」加總最新快照中實體磁碟區的系統已用空間，排除虛擬磁碟區；RAID 鏡像硬碟不會重複加總。後方百分比為系統已用／同份快照的實體磁碟區總容量，四捨五入至整數；容量不完整時不推算比例。「工作用途」對應 JSON 的 `workPurpose`，已填入使用者指定的六台用途。後續採集未提供該欄位時保留原值；明確傳入空字串可清空。

## 用 VS Code Live Server 開啟

已設定 Live Server（`ritwickdey.LiveServer`）。以 VS Code 開啟 `D:\ai\pc` 或 `pc-inventory` 專案資料夾，按右下角 **Go Live**，即可瀏覽 <http://127.0.0.1:5500>，修改並儲存檔案後自動重新整理。兩層資料夾均已設定正確的 `dist` 網站根目錄。

## 用 Node.js 開啟網站

需 Node.js，不需安裝執行階段依賴。在專案資料夾執行：

```powershell
node serve.mjs
```

瀏覽 <http://127.0.0.1:4173>。請透過伺服器開啟，直接以 `file://` 開啟會受瀏覽器模組與 JSON 存取限制。

網站包含電腦切換、硬體與軟體搜尋、軟體名稱排序、設備規格比較、JSON 匯入與匯出，以及手機版介面。按 `/` 可跳至設備搜尋。分頁順序：總覽、硬體規格、軟體清單、儲存空間、子系統、系統環境。

## 儲存空間快照與子系統盤點

使用 Python 3.10 以上執行唯讀工具（無第三方依賴）：

```powershell
# 資料夾使用量快照
python collect-usage.py --computer dist/data/pc_china.json --kind storage
# 目前 WSL / Docker 子系統盤點
python collect-usage.py --computer dist/data/pc_china.json --kind environments
# 同時更新兩者
python collect-usage.py --computer dist/data/pc_china.json --kind all
```

儲存空間分頁提供快照時間選擇、磁碟容量、資料夾樹狀展開及收合。預設每個實體磁碟區最多掃描 45 秒，保留 4 層目錄，深層檔案會合計至父層。時間不足或有無法讀取的項目會標示「部分掃描」，不估算未讀取的大小。虛擬磁碟區預設僅記錄容量。可用 `--drives C: D:` 指定掃描範圍、`--seconds-per-volume 300` 增加掃描時間、`--depth 6` 增加保留層級。保留最近 20 份快照；匯入相同設備時合併快照，並保留最新的子系統盤點。

樹狀容量為可讀檔案的邏輯大小，可能含硬連結重複計數；它不等於系統已用空間。目錄接合點與符號連結會略過，不讀取檔案內容。子節點採按需展開，避免一次渲染大量目錄。這是掃描時段的使用量記錄，並非作業系統的原子 VSS 快照。

對大型目錄使用 `--expand-over-gb 5`：以 5 GiB（介面顯示 5 GB）為門檻，持續保留大型資料夾的子層，單一檔案達門檻也會列出名稱。較小資料夾仍可手動展開額外一層明細，依容量優先保留；每個磁碟區最多額外保留 6,000 個小型節點，每個小資料夾最多約 25 個子項目，並列出至多 8 個具代表性的較大檔案，其餘歸入合計。大型分支不受這項額外預算限制，每層最多列出約 500 個項目，所有達門檻的項目都保留。深度安全上限為 64 層，達上限或讀取逾時仍會明確標示。此模式走訪可讀檔案的中繼資料以重新計算容量，不讀取檔案內容、不啟動停止中的 WSL。

例如：`python collect-usage.py --computer dist/data/pc_china.json --kind storage --expand-over-gb 5 --seconds-per-volume 1200`。SSH 重查工具同樣支援 `--expand-over-gb 5`。

省略 `--expand-over-gb` 時，儲存重查會沿用該電腦最新快照的展開門檻；舊資料沒有此設定才使用固定深度。大於 5 MiB 的網站內建 JSON 會以緊湊格式儲存，保留所有內容及歷史快照。

只重查 SSH 主機的儲存空間，可執行 `python scripts/recheck-storage.py --name pc_rtx --host jack@192.168.100.180 --platform windows --seconds 600 --output .sites-runtime/recheck-pc_rtx.json`，再以 `manage-inventory.mjs` 匯入。Linux 使用 `--platform linux`；僅當既有非互動 sudo 已授權時才加 `--sudo`。此工具保留原有硬體、軟體、用途及 CUDA／PyTorch 盤點，只新增儲存快照並更新磁碟區容量。深層節點達顯示上限時，仍保留前兩層資料夾的容量歸屬。頁面分開顯示掃描是否逾時、無法讀取的項目、掃描耗時與系統已用／檔案邏輯合計的差額；差額並非可回收空間。

「子系統」分頁獨立盤點 WSL 與 Docker，顯示最近盤點時間：

- WSL：已註冊發行版、WSL 版本、狀態、OS、VHDX 檔案長度與主機占用量。執行中的發行版另讀取 `/etc/os-release` 與 Linux `df`；停止中的發行版不啟動，OS 僅標示登錄名稱來源。
- Docker：本機 context、Engine OS/Kernel/架構、資源摘要、容器可寫層大小、Image OS/架構/大小、Volumes 清單與可讀取的 Docker Desktop VHDX。Docker 引擎無法連線時顯示「未取得」，不將未知資源顯示為零；遠端 context 不列為本機資源。
- VHDX 檔案長度與磁碟實際占用分開顯示；Images 共用層、VHD、Linux `df` 不互相加總。

網頁不能直接查詢本機磁碟或 Docker daemon。按「擷取新快照」或「更新盤點」可下載工具與目前規格 JSON，執行工具後再匯入更新檔。瀏覽器匯入資料僅存於 localStorage；永久更新請將更新檔交給 `manage-inventory.mjs` 並重新部署。快照變大超過瀏覽器容量時可直接更新網站內建檔案。

`collect-usage.py` 的網頁下載版本位於 `dist/collect-usage.py`，修改後請同步兩份檔案。重新執行 `collect-pc.ps1` 更新規格時會保留該 JSON 既有的儲存空間快照與子系統盤點。

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

規格比較表新增「記憶體擴充」與「儲存擴充」，各台「硬體規格」提供選項、限制與原廠來源。`dist/expansion.mjs` 的評估依精確主機板／機型及 CPU 配對，不以設備名稱推定能力；不相符時顯示待查。空記憶體槽依完整 DIMM 清單推估；儲存接孔占用、機殼硬碟架及供電未確認時不宣稱可直接加裝。官方規格核對日期為 2026-10-18，較高容量仍需確認 BIOS 與 QVL。

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

`tests/usage.test.mjs` 驗證使用量資料、歷史合併與錯誤輸入。執行 `python -m unittest discover -s tests -p test_usage_collector.py` 可驗證檔案掃描統計。開啟本機 Node 預覽後，使用已安裝的 Playwright 與 Edge 執行 `node tests/browser-check.mjs`、`node tests/usage-browser-check.mjs`，可驗證完整流程、樹狀展開、手機版與矮視窗側欄。
