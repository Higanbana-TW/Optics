# ISO 12233 charts (DXF)

Printable **ISO 12233:2000-style** resolution charts as DXF, at **4×** the 1X size (active picture height = **800 mm**).

This is a geometric recreation for workshop printing, not an ISO-certified manufactured target. Source vector geometry is the public chart published by Stephen H. Westin (Cornell). See `SOURCES.md`.

## Aspect ratios

ISO 12233:2000 is a **16:9** chart with crop marks for **4:3**, **3:2**, and **1:1**. That is the official 4:3 usage: fill the picture height and crop to the 4:3 arrows.

A native **4:3** DXF is also generated: the same 800 mm picture height, width = 4/3 × height, using those official 4:3 crop ticks. Frequency labels (×100 LW/PH) stay valid because picture height is unchanged.

CIPA’s later chart is **3:2**, not 4:3. These files follow the 2000 visual chart.

## Choosing a region

Each full DXF has layers you can freeze in CAD:

| Layer | Contents |
|---|---|
| `FRAME` | Border, framing arrows, registration |
| `CENTER` | Central wedges, zone plate, pulse bars |
| `PERIPHERY` | Corner wedges, checkerboards, edge patterns |
| `SFR` | Slanted-edge bars, H-bars, corner SFR squares |
| `LABELS` | Frequency / aspect-ratio text |
| `NOTES` | Scale and print notes |

Separate files are also written so you can send one piece to a print shop:

- `iso12233_16x9_4x_full.dxf` / `iso12233_4x3_4x_full.dxf`
- `..._center.dxf` — cropped central pack
- `..._periphery.dxf` — corners and edges
- `..._sfr.dxf` — slanted-edge SFR features only

Plot **monochrome**. If a cropped tile fills the camera frame, multiply the printed LW/PH labels by the factor in the `NOTES` line (`full PH / tile height`).

## Generate

```bash
python3 -m pip install -r tools/iso12233/requirements.txt
python3 tools/iso12233/generate.py --scale 4 --preview
```

`--scale 4` is 4× of the 200 mm 1X chart. Use `--aspect 16:9|4:3` and `--region full|center|periphery|sfr` to build a subset.

## Tests

```bash
cd tools/iso12233 && python3 test_generate.py
```
