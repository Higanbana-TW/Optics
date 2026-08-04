# Optics

## Lens distortion 歪斜線 Excel 計算器

[`lens_distortion_line_calculator.xlsx`](lens_distortion_line_calculator.xlsx) 可依下列資料，計算受徑向 lens distortion 影響後的直線 4 點座標：

- Lens distortion table 的 FOV / Distortion (%)
- Sensor pixel size
- Lens 焦距
- 物體與 lens 距離
- 物方直線起點與終點 X/Y（定義線段所必需）

工作表會輸出線段起點、1/3、2/3、終點的相對與絕對 pixel 座標，並繪製散佈圖。詳細座標定義、畸變符號與模型限制請見檔案內「使用說明」頁。

重新產生檔案：

```bash
python3 -m pip install openpyxl
python3 generate_lens_distortion_excel.py
```
