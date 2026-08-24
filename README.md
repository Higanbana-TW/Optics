# Optic Player

一個受 VLC 啟發的輕量網頁播放器，支援：

- 本機 MP4、WebM、Ogg 與瀏覽器可解碼的影音格式
- HTTP(S) 影音網址與 HLS (`.m3u8`) 網路串流
- 播放、暫停、快轉、倒退、音量、倍速與全螢幕控制
- 將目前影格以原始解析度擷取為 PNG

另外內建 **RAW10 Studio**：把 10-bit MIPI RAW 感測器輸出轉成 BMP / JPG / PNG。

## 開發

```bash
npm install
npm run dev     # http://localhost:5173/        播放器
                # http://localhost:5173/raw10.html  RAW10 轉換器
npm test        # 執行單元測試與 CLI 測試
```

建立正式版本：

```bash
npm run build
```

> 網路串流需允許瀏覽器跨來源存取（CORS）。RTSP、DRM 內容與瀏覽器不支援的編碼無法直接播放。

## RAW10 Studio — 10-bit MIPI RAW 轉圖檔

感測器輸出的 RAW 檔沒有檔頭，只有一連串像素資料，因此必須自行指定尺寸與格式。本工具同時提供
網頁介面與命令列工具，兩者共用 `src/raw10/` 底下的同一套解碼流程。

### 支援的輸入

| 項目 | 內容 |
| --- | --- |
| 資料封裝 | MIPI CSI-2 RAW10 packed（5 bytes / 4 px）、低位元反序的變體、未打包 16-bit（大／小端、靠左／靠右對齊） |
| Bayer 排列 | RGGB、BGGR、GRBG、GBRG、MONO |
| 版面 | 自訂每列位元組數（處理硬體 padding）、檔頭偏移、多影格連拍檔 |
| 輸出 | BMP（24-bit）、JPG（可調品質）、PNG |

處理流程：解包 10-bit 取樣 → 扣黑階並依白階正規化 → 白平衡增益與曝光補償 →
去馬賽克（雙線性 / 2×2 合併 / 不處理）→ sRGB 或 Gamma 曲線 → 8-bit RGB。

### 網頁介面

開啟 `/raw10.html`，把 `.raw`、`.raw10`、`.bin` 拖進預覽區即可：

- 由檔案大小與檔名（例如 `capture_1920x1080_bggr.raw`）自動猜測解析度與 Bayer 排列
- 「自動最佳化」用畫面本身估算黑白階與灰界（grey-world）白平衡
- 即時預覽、1:1 檢視、多影格切換，並可直接存成 BMP / JPG / PNG
- 全部在瀏覽器本機運算，檔案不會上傳

沒有 RAW 檔也可以按「載入示範 RAW」產生合成畫面試用。

### 命令列工具

```bash
# 單檔轉換
node tools/raw10-convert.mjs capture.raw -w 1920 -h 1080 -p bggr -o capture.png

# 批次轉換整個資料夾，並自動估算黑白階與白平衡
node tools/raw10-convert.mjs frames/*.raw -w 1280 -h 720 --auto -f jpg -d out/

# 匯出連拍檔中的每一張影格
node tools/raw10-convert.mjs burst.raw10 -w 640 -h 480 --frame all -d out/

# 只檢查檔案並列出可能的解析度
node tools/raw10-convert.mjs unknown.raw --info
```

常用選項（完整說明請執行 `node tools/raw10-convert.mjs --help`）：

| 選項 | 說明 |
| --- | --- |
| `-w, --width` / `-h, --height` | 影像寬高；檔名含 `1920x1080` 時可省略 |
| `-p, --pattern` | `rggb`、`bggr`、`grbg`、`gbrg`、`mono` |
| `--packing` | `mipi10`、`mipi10lsbrev`、`raw16le`、`raw16be` |
| `--stride` / `--offset` | 每列位元組數（處理 padding）與檔頭偏移 |
| `--frame <n\|all>` | 多影格檔案要輸出第幾張 |
| `--black` / `--white` / `--gains` / `--ev` | 黑階、白階、白平衡增益、曝光補償 |
| `--tone` / `--gamma` / `--demosaic` | 轉換曲線與去馬賽克方式 |
| `-a, --auto` | 由畫面自動估算黑白階與白平衡 |
| `-f, --format` / `-q, --quality` | 輸出格式與 JPEG 品質 |

### 產生測試檔

```bash
node tools/make-sample-raw10.mjs -w 1920 -h 1080 -p rggb --frames 3
```

會在 `samples/` 產生合成的 MIPI RAW10 檔（色彩條、灰階階梯與漸層），方便驗證流程。
