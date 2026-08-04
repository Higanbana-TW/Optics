# Optics

## Lens distortion TV本 Chart 逆向預變形 Excel 計算器

[`lens_distortion_line_calculator.xlsx`](lens_distortion_line_calculator.xlsx) 在 sensor 第一象限自動建立 TV本 chart，並反算可直接匯入 CAD 的物方預變形座標：

- 最多 2000 筆半視角／Optical distortion (%) 資料
- 預設 3840×2160、pixel size 2 µm、實體尺寸 7.68×4.32 mm
- 預設指定 1500 TV本、間隔 100，自動產生上下各 5 級，共 11 級
- 每級包含 5 條橫線及 5 條豎線，指定級中心位於第一象限 0.7 視場
- 11 級垂直排列：1000 TV本在上方外場，2000 TV本在下方內場
- 物方 CAD 座標以光軸投影點為原點，單位為 mm

工作表會輸出 110 條線的 440 個物方 CAD 角點，並提供正向投影驗證、mm 誤差及 sensor／物方圖形。中心 chart 暫不生成。詳細定義請見檔案內「使用說明」頁。

重新產生檔案：

```bash
python3 -m pip install openpyxl
python3 generate_lens_distortion_excel.py
```
