# RAW10 Lab

一個完全在瀏覽器內執行的 MIPI CSI-2 RAW10 影像轉換器，可將感測器原始資料轉成 BMP、JPG 或 PNG。

## 功能

- 解包標準 RAW10（每 4 pixels / 5 bytes）
- 支援 RGGB、BGGR、GRBG、GBRG Bayer 排列與 Mono 灰階
- 可設定影像尺寸、檔頭偏移及每列 stride / padding
- Bayer demosaic、自動白平衡、黑白階、Gamma 與曝光調整
- 輸出 24-bit BMP、高品質 JPG 或無損 PNG
- 全程在本機瀏覽器處理，檔案不會上傳

## 使用方式

### 不需安裝的離線版

只要下載 [`offline/RAW10-Lab-Offline.html`](offline/RAW10-Lab-Offline.html)，直接雙擊並使用 Chrome、Edge 或 Firefox 開啟即可。不需要安裝 Node.js、Python 或其他程式，也不需要網路連線。

> 此檔案仍需瀏覽器允許一般網頁指令碼執行。若機構政策封鎖本機 HTML 的指令碼，請先交由 IT 部門審核及核准。

### 開發版

```bash
npm install
npm run dev
```

開啟頁面後：

1. 選擇 `.raw`、`.raw10`、`.bin` 或 `.mipi` 檔案。
2. 輸入感測器有效寬度及高度。
3. 選擇正確 Bayer 排列；無 Bayer 資料請選 Mono。
4. 若檔案有 header 或每列 padding，填入 offset 與 stride。
5. 點選「解析並預覽」，再下載需要的格式。

> 本工具假設檔案使用標準 MIPI CSI-2 RAW10 packing。若來源是 16-bit container、左對齊 RAW10 或其他 vendor-specific packing，需先轉為標準 RAW10。

## 開發與測試

```bash
npm test
npm run build
npm run build:offline
```
