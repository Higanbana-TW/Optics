# Optics

## Lens distortion 長方形逆向預變形 Excel 計算器

[`lens_distortion_line_calculator.xlsx`](lens_distortion_line_calculator.xlsx) 以 sensor 上指定的四點為目標，反算可直接匯入 CAD 的物方預變形座標：

- 最多 2000 筆半視角／Optical distortion (%) 資料
- 預設 3840×2160、pixel size 2 µm、實體尺寸 7.68×4.32 mm
- Sensor 四點直接使用左上角原點的絕對 mm 座標
- 物方 CAD 座標以光軸投影點為原點，單位為 mm

工作表會輸出物方預變形的四角 CAD 座標，以及每邊最多 50 段的完整曲邊座標。內建正向投影驗證、mm 誤差及 sensor／物方圖形。詳細座標定義、畸變符號與模型限制請見檔案內「使用說明」頁。

重新產生檔案：

```bash
python3 -m pip install openpyxl
python3 generate_lens_distortion_excel.py
```
