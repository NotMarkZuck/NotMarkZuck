# Apartment Bar Generator (Grasshopper)

Draw a line in Rhino and this script builds a row of apartment boxes on both sides
of it. The line becomes the middle of a 5' corridor, an end unit caps each end,
and a slider sets the number of floors.

The script is in `apartment_bar.py`. Set your Rhino file units to **Feet**.

## Setup (about 5 minutes)

1. In Rhino, draw a line with the `Line` command. This is your corridor.
2. Type `Grasshopper` to open it.
3. Double-click on the empty canvas, type **Python**, and add the
   **Python 3 Script** component (in Rhino 7 it's called **GhPython Script**).
4. Zoom in on the component until you see the small **+** and **–** signs.
   Use them to make **7 inputs** and **4 outputs**.
5. Right-click each input and rename it, in this order:
   `Line`, `Floors`, `UnitWidth`, `UnitDepth`, `EndUnitLength`, `FloorHeight`, `CorridorWidth`
6. Right-click each output and rename it: `Units`, `EndUnits`, `Corridor`, `Info`
7. Set the input types (right-click the input, then **Type hint**):
   - `Line` → **Curve**
   - `Floors` → **int**
   - all the others → **float**
8. Double-click the component, delete what's in there, paste in all of
   `apartment_bar.py`, and click **OK**.
9. Connect things:
   - Add a **Curve** component (Params tab → Geometry → **Curve**, not **Line**),
     right-click it, choose **Set one Curve**, then click your Rhino line. Connect it
     to `Line`. (The **Line** component's "Set one Line" makes you draw a new line
     instead of picking the one you already drew.)
   - Add a **Number Slider**, set it to whole numbers (e.g. 1 to 10). Connect it to `Floors`.
   - The other inputs are optional (defaults below). Add sliders if you want to adjust them.
   - Connect a **Panel** to `Info` to see unit counts.

The boxes appear in Rhino right away. When you're happy, right-click the outputs
and choose **Bake** to turn them into real Rhino objects.

## Defaults (feet)

| Input | Default | Meaning |
|---|---|---|
| UnitWidth | 25 | Width of a typical unit along the corridor |
| UnitDepth | 30 | Depth from corridor to outside wall |
| EndUnitLength | 30 | How far each end unit runs along the line |
| FloorHeight | 10 | Floor-to-floor height |
| CorridorWidth | 5 | Corridor width |

The line can be straight, have corners (L, U, Z shapes drawn with the `Polyline`
command), be a smooth curve, or be a closed loop (no end units then). At corners
the units meet on an angle so nothing overlaps.

Typical units are stretched slightly so they always fill the corridor exactly
with no leftover gap. Each end unit spans the full width of the building
(both unit rows plus the corridor), so it closes off the end of the corridor.
