# Optic Player

一個受 VLC 啟發的輕量網頁播放器，支援：

- 本機 MP4、WebM、Ogg 與瀏覽器可解碼的影音格式
- HTTP(S) 影音網址與 HLS (`.m3u8`) 網路串流
- 播放、暫停、快轉、倒退、音量、倍速與全螢幕控制
- 將目前影格以原始解析度擷取為 PNG
- [10-bit MIPI RAW 轉 BMP / JPG / PNG](#10-bit-mipi-raw-轉換器)

## 開發

```bash
npm install
npm run dev
```

建立正式版本：

```bash
npm run build
```

> 網路串流需允許瀏覽器跨來源存取（CORS）。RTSP、DRM 內容與瀏覽器不支援的編碼無法直接播放。

## 10-bit MIPI RAW 轉換器

把 camera sensor 的 10-bit MIPI CSI-2 RAW dump 轉成 `.bmp`、`.jpg` 或 `.png`。

### 機構電腦不能裝軟體時

不要執行 `.exe`、`.js`，也不必安裝 Python。用**已經有的瀏覽器**開這個網址：

https://raw.githack.com/Higanbana-TW/Optics/cursor%2Fmipi-raw10-converter-4045/mipi-raw.html

這是開網頁，不是執行程式。把 `.raw` 拖進去，再下載 PNG / JPG / BMP。詳細步驟見 `使用說明.txt`。

實驗室若已安裝 MATLAB，可用文字腳本 `mipi_raw_convert.m`（不是執行檔）：

```matlab
mipi_raw_convert('capture.raw', 1920, 1080, 'out.png')
```

### 最簡單：下載後直接開網頁

不需要安裝 Node 或 Python。

1. 下載這個專案（GitHub 的 Code → Download ZIP）
2. 解壓縮
3. **雙擊 `mipi-raw.html`**，用 Chrome / Edge / Firefox 開啟
4. 把 `.raw` 拖進去（或按「載入示範畫面」）
5. 確認寬高與 Bayer 排列後，按 PNG / JPG / BMP 下載

轉換都在瀏覽器裡完成，檔案不會上傳。不要開 `raw.html`（那是給 `npm run dev` 用的開發頁）。

支援的封包：

- **MIPI RAW10**：每 4 個 10-bit 像素打包成 5 bytes（CSI-2 標準）
- **Unpacked 16-bit**：每像素 2 bytes，10-bit 可在低位或高位

Bayer 可選 RGGB / GRBG / GBRG / BGGR，或當灰階 Mono。

### 開發時的網頁版

```bash
npm install
npm run dev
```

瀏覽器開啟 `/raw.html`。若改了轉換邏輯，執行 `npm run build:standalone` 更新 `mipi-raw.html`。

### 命令列

```bash
python3 -m pip install -r requirements-mipi-raw.txt
python3 mipi_raw_convert.py capture.raw -W 1920 -H 1080 --bayer RGGB -o out.png
python3 mipi_raw_convert.py capture.raw -W 1920 -H 1080 -o out.jpg
python3 mipi_raw_convert.py capture.raw -W 1920 -H 1080 -o out.bmp
```

產生示範 RAW 並轉圖：

```bash
python3 mipi_raw_convert.py --make-sample 640x480 --bayer RGGB -o sample.raw
python3 mipi_raw_convert.py sample.raw -W 640 -H 480 --bayer RGGB -o sample.png
```

只猜測解析度：

```bash
python3 mipi_raw_convert.py capture.raw --guess
```

常用參數：

- `-W` / `-H`：寬高。MIPI RAW10 的寬度必須是 4 的倍數
- `--format`：`mipi10`、`u16le`、`u16msb`、`u16be`
- `--bayer`：`RGGB`、`GRBG`、`GBRG`、`BGGR`、`mono`
- `--offset`：檔頭 bytes
- `--stride`：每列 bytes（含 padding）
- `--tone`：`shift`（右移 2 bit）、`stretch`、`percentile`
- `--wb`：`auto`、`off` 或 `R,G,B`

### 測試

```bash
python3 -m unittest -v test_mipi_raw_convert.py
npm test
```
