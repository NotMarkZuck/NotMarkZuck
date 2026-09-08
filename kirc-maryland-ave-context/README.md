# UWM KIRC / N Maryland Ave — SketchUp context terrain

Builds a 200' x 200' SketchUp context model centred on the **concrete footbridge over
N Maryland Ave** (Wisconsin State Plane South, US ft: **E 2565620, N 399138**), from the
supplied campus CAD files.

## The key data problem

The large campus survey (`CAMPUS_KIRC_CAD_EXST_CONDITIONS_RVT_IMPORT.dwg`) predates KIRC
construction. Cross-checking its contours against the KIRC landscape drawing
(`CAMPUS_KIRC_CAD_BGND_RVT_IMPORT.dwg`) shows the KIRC site was **regraded ~3.7 ft higher**
(median; up to ~12 ft locally). So the two sources are merged:

| region | source |
|---|---|
| KIRC site (west of the `M.E.` match line at ~E 2565613) | KIRC as-built contours + spot elevations |
| Maryland Ave, footbridge, east side | campus survey 1-ft contours (`C-EG-1-E`) |

The KIRC drawing stores contour elevations only in **text labels** next to 2D linework, so
`topo.py` chains the contour segments and assigns each chain its nearest label. That labelling
is validated against KIRC's own spot elevations (median agreement **0.07 ft**).

## Pipeline

DWG files are read by converting to DXF with [LibreDWG](https://github.com/LibreDWG/libredwg)
(`dwg2dxf`), then parsed with `ezdxf`.

```
survey.py        inventory a DXF: units, extents, layers, entity mix, text
locate.py        find street/bridge labels and list all layers
box_recon.py     report what falls inside a candidate study box
build_terrain.py merge the two elevation sources -> gridded terrain (terrain.npz)
verify_terrain.py check the merged surface against its control points
site_lines.py    extract road/curb/walk/building linework in the box
prep_model.py    road-edge line fits + ribbons + bridge + outlines -> model_data.json
emit_payload.py  compact literal payloads for the SketchUp MCP build_model calls
plot_plan.py     plan drawing of the study area
preview3d.py     3D + plan preview of what was built
```

## Result

- Terrain: 65 x 65 grid @ 3.125 ft (8,192 triangles), relief **674.93 – 686.84 ft**.
  Fit vs 635 control points: **RMS 0.219 ft**, 89% within 0.25 ft.
- Model datum: site low point (674.93 ft) = Z 0; X/Y centred on the footbridge.
- Roadway 41.35 ft back-of-curb to back-of-curb (36.15 ft pavement), 6 in curb reveal;
  west sidewalk 6.12 ft; east paved area 18.81 ft.
- Footbridge deck 12.01 ft wide (10 ft clear between 1 ft parapets), underside 13.87 ft over
  the road crown — matches the "14' CLEARANCE ZONE" note in the section drawing.
  **The bridge is approximate** (plan position and width are from CAD; height is derived
  from the clearance note) and is isolated in its own groups.
