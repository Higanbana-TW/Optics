# RAW10 Lab

在瀏覽器本機將 10-bit MIPI RAW 影像轉換成一般影像格式的小工具。

- 標準 MIPI CSI-2 RAW10 packed 格式（每 4 像素使用 5 bytes）
- `RGGB`、`BGGR`、`GRBG`、`GBRG` Bayer 排列與雙線性去馬賽克
- 自訂影像寬高、row stride、黑電平與白電平
- 輸出 PNG、JPG（92% 品質）或 32-bit BMP
- 檔案完全在瀏覽器中處理，不會上傳

> RAW 檔案本身通常沒有尺寸或 Bayer 排列等 metadata，轉換時必須填入與感光元件輸出相符的設定。本工具目前處理單張 frame；如果檔案尾端還有資料，會在狀態訊息中標示並忽略。

## 開發

```bash
npm install
npm run dev
```

測試與建立正式版本：

```bash
npm test
npm run build
```
