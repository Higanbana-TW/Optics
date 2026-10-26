# Optic 即時雙語字幕

在 Windows 上開一支浮動字幕列。Microsoft Teams 會議進行時，它聽取電腦正在播放的聲音，辨識英文，並在同一條永遠置頂的半透明列上同時顯示英文與台灣繁體中文。

這個程式在你自己的電腦上執行。它不是 Teams 機器人，不需要 Azure Bot、Teams 應用套件，也不需要租戶管理員安裝。字幕只出現在你的螢幕上，不會送進會議。

Optic Player（這個存放庫原本的網頁播放器）維持不變。字幕程式是獨立的 `live-captions/` 目錄，有自己的相依套件。

## 不用安裝 Python

下載 Windows 預覽壓縮檔（GitHub Actions `windows-latest` 上的 PyInstaller onedir，不是在 Linux 上做出來的 exe）：

https://github.com/Higanbana-TW/Optics/releases/download/live-captions-windows-0.1.0/LiveCaptions-windows.zip

1. 解壓縮
2. 打開 `LiveCaptions` 資料夾
3. 雙擊 `LiveCaptions.exe`

字幕列會先出現。第一次需要網路，字幕列會顯示正在下載語音模型（約 139 MB）和翻譯模型（約 68 MB）。這兩個模型沒有包在壓縮檔裡。不需要安裝 Python，也不用留著命令視窗。

結束請用系統匣的「字」圖示，或按 `Ctrl+Alt+Q`。拖曳可移動。`Ctrl+Alt+C` 點擊穿透，`Ctrl+Alt+H` 隱藏，`Ctrl+Alt+A` 切換系統播放與麥克風。

## 環境

- Windows 10 或 Windows 11，64 位元
- 直接雙擊 `LiveCaptions.exe` 時不需要 Python
- 若要從原始碼執行：Python 3.11 或 3.12，64 位元（這次在 Linux 上用 Python 3.12.3 跑測試）
- 會議聲音要從喇叭或耳機播出。系統靜音時沒有字幕

## 安裝與執行

在 PowerShell 開啟 `live-captions` 目錄：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m live_captions --setup
python -m live_captions
```

若執行原則擋住 `Activate.ps1`，可以不啟動虛擬環境，改為：

```powershell
.\.venv\Scripts\python.exe -m live_captions
```

已安裝 Python 時，也可以雙擊 `run.bat`。它會建立虛擬環境、安裝套件，然後開啟字幕。請留著那個命令視窗；關掉視窗就會結束字幕。

第一次執行前請先跑 `--setup`，讓模型在會議開始前下載完。`--setup` 需要網路。模型下載後，預設路徑不再把音訊或英文字幕送到雲端。

## 安裝大小與模型下載

相依套件沒有放進 git。在這台 Linux x86_64、Python 3.12 上執行 `pip install --target` 安裝 `requirements.txt` 後，目錄合計 **726,566,008 bytes（約 693 MB）**。大項大約是：

| 項目 | 這台 Linux 上的大小 |
| --- | ---: |
| PySide6-Essentials（字幕視窗） | 238 MB |
| av（faster-whisper 的音訊解碼） | 126 MB |
| CTranslate2（語音與翻譯推理） | 145 MB |
| onnxruntime | 66 MB |
| numpy | 65 MB |

需求檔指定的是 `PySide6-Essentials`，不是會再拉進 WebEngine 的 `PySide6` 套件。Windows 的 `win_amd64` 輪檔壓縮後較小（PySide6-Essentials 約 78 MB、ctranslate2 約 19 MB、av 約 27 MB、onnxruntime 約 14 MB）。沒有在 Windows 上重測解壓後的資料夾，所以 693 MB 是這台 Linux 的實測，不是 Windows 安裝收據。

模型在第一次 `--setup` 或第一次開啟時下載，不會提交進存放庫：

| 模型 | 大小 |
| --- | --- |
| 語音：Hugging Face `Systran/faster-whisper-base.en` | 公開 `usedStorage` 與這台機器下載到的 `model.bin` 都是 **145,216,508 bytes（約 139 MB）** |
| 翻譯：Argos `translate-en_zh-1_9.argosmodel` | 下載 **70,743,021 bytes**；解壓後 **85,640,765 bytes（約 82 MB）** |

SHA-256：`433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab`

想換較大的語音模型時設定 `CAPTIONS_WHISPER_MODEL=small.en`。`Systran/faster-whisper-small.en` 的公開 `usedStorage` 是 483,545,366 bytes（約 461 MB）。

語音模型快取在 Hugging Face 的快取目錄。翻譯模型在 Windows 放在 `%LOCALAPPDATA%\OpticsLiveCaptions\models`，視窗位置放在 `%APPDATA%\OpticsLiveCaptions\settings.json`。

## 怎麼操作

字幕列沒有邊框，預設在畫面下方中央，可拖曳。背景半透明，文字維持不透明，避免疊在會議畫面上時看不清。它盡量不搶走 Teams 的鍵盤焦點。

- 拖曳：移動字幕列
- 按右鍵或系統匣圖示：選音訊、字級、點擊穿透、結束
- `Ctrl+Alt+C`：點擊穿透開或關。穿透時滑鼠點擊會落到下面的會議視窗，可用這個熱鍵或系統匣圖示關回來
- `Ctrl+Alt+H`：隱藏或顯示
- `Ctrl+Alt+A`：系統播放與麥克風切換
- `Ctrl+Alt+Q`：結束

點擊穿透與全域熱鍵只在 Windows 上有效。

示範字幕、不聽音訊：

```powershell
python -m live_captions --demo
```

## 音訊

預設來源是 **WASAPI 迴路**（pyaudiowpatch）。它聽的是 Windows 目前的預設播放裝置，也就是 Teams 從喇叭或耳機放出來的聲音。不需要開啟「立體聲混音」。耳機也可以，只要那個裝置是預設播放裝置。

迴路聽得到對方的聲音，聽不到你自己的麥克風，除非 Windows 把麥克風也送到播放裝置。麥克風模式則只聽你自己的聲音，聽不到對方。

迴路打不開時會自動改用麥克風，字幕列會寫「無法開啟系統音訊，已改用麥克風。」若要指定播放裝置，設定名稱裡的一段文字：

```powershell
$env:CAPTIONS_LOOPBACK_NAME = "Headphones"
```

指定了名稱卻找不到時，不會偷偷改聽麥克風。

音量很小、一直沒有字幕時，可把靈敏度調高（門檻調低）：

```powershell
$env:CAPTIONS_VAD_THRESHOLD = "0.005"
```

環境雜音一直觸發時，把數字調高，例如 `0.02`。

## 語音與翻譯

預設全程在本機，不需要 API 金鑰。

- **語音**：faster-whisper 的 `base.en`，CPU、`int8`。直接吃迴路送來的 PCM，所以不使用 Windows 語音 API，也不使用 Azure Speech。語言固定為英文。
- **翻譯**：Argos Translate 封裝的 OPUS-MT 英文→中文模型（Tiedemann 與 Thottingal，2020，CC-BY 4.0），用 CTranslate2 與 SentencePiece 載入。沒有安裝 `argostranslate` 這個套件，因此不會再下載 spaCy 或 Stanza。
- **繁體**：顯示前一律經過 OpenCC `s2twp`。簡體，以及「信息、程序、打印」這種簡繁同形詞，會轉成台灣用語，例如軟體、網路、影片、資訊、程式、列印。已經是台灣繁體的句子多半不變。字典還會把部分詞再本地化，例如「文件」可能變成「檔案」、「連接」可能變成「連線」。

本機模型足以跟上簡單句子，會議慣用語不一定準。這次實測：

```text
Please install the software, connect to the network, and play the video.
請安裝軟體，連線網路，播放影片。

Hello everyone, thanks for joining the meeting.
大家好，謝謝大家參加這個會議。

I will send the meeting notes after this call.
我將在這一呼籲之後發出會議說明。
```

最後一句把 call 翻成「呼籲」，這是小模型的限制。要更穩的會議用語，可改用 DeepL 或 OpenAI。這兩個只在你明確選定時才會把英文句子送出，環境裡碰巧有金鑰不會自動啟用。音訊仍留在本機，送出的是辨識後的英文。

```powershell
$env:CAPTIONS_TRANSLATOR = "deepl"
$env:DEEPL_API_KEY = "你的金鑰"
```

DeepL 的目標語言是 `ZH-HANT`（免費金鑰通常以 `:fx` 結尾）。OpenAI 預設模型是 `gpt-4.1-mini`，可用 `OPENAI_MODEL` 更換。LibreTranslate 設 `CAPTIONS_TRANSLATOR=libre` 與 `LIBRETRANSLATE_URL`。這三種回傳的中文仍會再經過 OpenCC `s2twp`。

金鑰放在環境變數，或放在 `live-captions/.env`（已列入 git 忽略）。範例見 `.env.example`。不要把金鑰提交進存放庫。

有 NVIDIA GPU 時可設 `CAPTIONS_WHISPER_DEVICE=cuda`。翻譯模型預設用 CPU；要改 GPU 才設 `CAPTIONS_MT_DEVICE=cuda`。

## 環境變數

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `CAPTIONS_AUDIO` | `loopback` | `loopback` 或 `mic` |
| `CAPTIONS_TRANSLATOR` | `local` | `local`、`deepl`、`openai`、`libre` |
| `CAPTIONS_WHISPER_MODEL` | `base.en` | 例如 `small.en` |
| `CAPTIONS_WHISPER_DEVICE` | `cpu` | `cpu`、`cuda`、`auto` |
| `CAPTIONS_WHISPER_COMPUTE` | 依裝置 | 例如 `int8` |
| `CAPTIONS_CPU_THREADS` | `4` | 1 到 32 |
| `CAPTIONS_VAD_THRESHOLD` | `0.01` | 愈大愈不容易觸發 |
| `CAPTIONS_LOOPBACK_NAME` | 預設播放裝置 | 裝置名稱需包含這段文字 |
| `CAPTIONS_BAR_ALPHA` | `214` | 背景透明度 0–255；程式會把結果限制在 80–242。文字不跟著變透明 |
| `DEEPL_API_KEY` |  | 只有 `translator=deepl` 才使用 |
| `OPENAI_API_KEY` |  | 只有 `translator=openai` 才使用 |
| `OPENAI_MODEL` | `gpt-4.1-mini` |  |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` |  |
| `LIBRETRANSLATE_URL` |  | 只有 `translator=libre` 才使用 |
| `LIBRETRANSLATE_API_KEY` |  | 選用 |

`--verbose` 才會把辨識出的句子寫進記錄。預設的 `captions.log` 不保存字幕內容。

## 開發者測試

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

可單獨檢查繁體轉換，不必下載模型：

```powershell
python -m live_captions --convert "请安装软件，连接网络并播放视频。"
```

預期輸出：`請安裝軟體，連線網路並播放影片。`

## 這次驗證與尚未在 Windows 上確認的部分

在 Linux 上執行過：

- `python -m pytest`：51 項通過。涵蓋雙語排版、OpenCC `s2twp`、假翻譯器與 DeepL／OpenAI／Libre 的請求組裝、迴路失敗時改用麥克風、音訊重採樣與斷句、點擊穿透的視窗樣式位元。
- `python -m live_captions --convert` 與 `--translate`、`--demo --headless`：本機 OPUS-MT 模型實際翻譯上面的英文句子，再轉成繁體。
- 載入 faster-whisper `base.en`（`model.bin` 145,216,508 bytes），對一秒靜音做辨識，沒有吐出句子。這只確認模型載入，不是會議語音品質。
- 安裝 `libegl1` 後以 `QT_QPA_PLATFORM=offscreen` 建立字幕視窗。英文與繁體同時寫進兩個標籤，視窗帶有永遠置頂旗標。
- `python -m live_captions --list-audio`：正確報告迴路只在 Windows 可用。這台機器沒有 PortAudio，所以列不出麥克風。

還沒有、也無法在這台 Linux 機器上證明的部分：

- 真正的 WASAPI 迴路裝置，以及 Teams 播放裝置的名稱比對
- 麥克風在 Windows 上的開啟與隱私權提示
- 無邊框、半透明、可拖曳、永遠置頂的視窗是否蓋在 Teams 上面
- 點擊穿透、全域熱鍵、系統匣
- Windows 上的實際安裝資料夾大小，以及 Visual C++ 執行庫是否已存在

若啟動時出現 DLL 錯誤，請安裝 Microsoft Visual C++ 2015–2022 Redistributable（x64）。只有改用麥克風時，才需要在 Windows 隱私設定允許麥克風。
