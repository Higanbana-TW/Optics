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

## Tests

```bash
cd tools/iso12233 && python3 test_generate.py
```
