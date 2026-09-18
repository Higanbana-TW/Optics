# ISO 12233 charts (DXF)

Printable **ISO 12233:2000-style** resolution charts as DXF, at **4×** the 1X size (active picture height = **800 mm**).

This is a geometric recreation for workshop printing, not an ISO-certified manufactured target. Source vector geometry is the public chart published by Stephen H. Westin (Cornell). See `SOURCES.md`.

## Aspect ratios

ISO 12233:2000’s official visual chart is **16:9**. That plate also has crop arrows for **4:3**, **3:2**, and **1:1**. Using those arrows on a 16:9 print **crops** the corner crosses.

The **4:3 DXF does not crop the 16:9 plate and does not squeeze**. Feature shapes stay as drawn. The four corner resolution crosses are **translated** so each plus centre (KS high-res centroid) sits at the same 4:3 field point as the **EIAJ / ITE Test Chart A corner circles**: **0.762 of the 4:3 half-width** and **0.676 of the 4:3 half-height**. ISO wedge 本数 stay valid because nothing is scaled. Centre hyperbolic wedges and square-wave sweeps that would overlap those crosses are omitted; **diamond, square, and parallelogram SFR** patches and the centre zone plate stay. Picture height is still 800 mm at 4×; active width is 4/3 × height ≈ 1067 mm.

EIAJ TVL numbers are not ISO LW/PH; only the **四周** placement is reused. JS/L1 tips that stick past the 4:3 frame are clipped to the active rectangle.

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

Plot **monochrome**. Open the DXF in a 2D wireframe / shaded view with fills on (`FILLMODE=1`). The chart is drawn as SOLID triangles plus closed polylines so viewers that skip HATCH still show the wedges, not just the numbers.

If a cropped tile fills the camera frame, multiply the printed LW/PH labels by the factor in the `NOTES` line (`full PH / tile height`).

## Generate

```bash
python3 -m pip install -r tools/iso12233/requirements.txt
python3 tools/iso12233/generate.py --scale 4 --preview
```

`--scale 4` is 4× of the 200 mm 1X chart. Use `--aspect 16:9|4:3` and `--region full|center|periphery|sfr` to build a subset.

### 4K 本数 (Edmund 58-941 / Enhanced I3A style)

The published 2000 visual chart is a **1080p-class** plate: corner JS about **200–500 LW/PH**, centre J **100–600**, centre KS to **2000 LW/PH** (label `20`). A 4K sensor is not a global ×2 of that plate and not a uniform J×5 / JS×4 squeeze.

`--4k` follows the **2× Enhanced I3A/ISO 12233** labelling on Edmund Optics stock 58-941 (Applied Image QA-77), using the Cornell 2000 geometry. Wedge **length is unchanged**; only line pitch is squeezed, and O/P square-wave bursts are densified in place (×3, fine end 1000 → 3000). Extra QA-77 art (star sectors, gray SFR, branding) is **not** copied.

| Feature | 2000 labels | 4K labels (100× LW/PH) |
|---|---|---|
| Centre 5-line J | 1–6 | **6–20** (600–2000) |
| Centre 9-line KS | 6–20 | **12–40** (1200–4000) |
| Corner 5-line JS | 2–5 | **6–9** (600–900) |
| Corner 9-line KS | 6–9 | **12–18** (1200–1800) |
| Left KD diagonal | 6–9 | **6–9** (unchanged) |
| Right JS diagonal | 2–5 | **12–18** (1200–1800) |
| O/P square-wave | 1–10 | **12–30** (1200–3000) |
| G pulses | 1–10 | **1–10** |

```bash
python3 tools/iso12233/generate.py --aspect 16:9 --region full --scale 4 --4k --preview
python3 tools/iso12233/generate.py --aspect 16:9 --region full --scale 2 --4k --a4-tiles --preview
```

- `iso12233_16x9_4k_4x_full.dxf` — 4K 本数, 4× print (800 mm PH)
- `iso12233_16x9_4k_2x_full.dxf` — same 本数, 2× print (400 mm PH)
- `iso12233_16x9_4k_2x_a4_1of2.dxf` / `..._2of2.dxf` — two A4 landscape sheets with glue lines

### 16:9 1080p at 2×, split onto two A4 sheets

4× 16:9 is the large plate (`iso12233_16x9_4x_full.dxf`, 800 mm picture height). Compress 2×:

```bash
python3 tools/iso12233/generate.py --aspect 16:9 --region full --scale 2 --a4-tiles --preview
```

That writes:

- `iso12233_16x9_2x_full.dxf` — 2× plate (400 mm picture height)
- `iso12233_16x9_2x_a4_1of2.dxf` — A4 landscape **left**
- `iso12233_16x9_2x_a4_2of2.dxf` — A4 landscape **right**

A 2× plate at 100% is much larger than two A4s, so the A4 files scale the 2× chart so its **top and bottom are flush with the 210 mm A4 height**, then split left/right. A **12 mm overlap** of real chart is duplicated on both sheets (layer `GLUE`): dashed join line, registration crosses, and 20 mm ticks. Print **actual size / 100%**, landscape, no “fit to page”. Glue the 12 mm strip on page 1 **under** page 2, matching the crosses.

Labeled LW/PH is for the 2× 400 mm picture height. On the A4 print the active height is smaller; the `NOTES` line gives the multiply factor if that sheet fills the camera frame.

## Tests

```bash
cd tools/iso12233 && python3 test_generate.py
```
