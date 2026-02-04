# nespdf

A NES emulator that runs inside a PDF file. Inspired by [DoomPDF](https://doompdf.org/) and [pdftris](https://github.com/ThomasRinsma/pdftris). Uses [jsnes](https://github.com/bfirsh/jsnes) as the emulator core.

## Requirements

- **Python 3** (no extra packages)
- `jsnes.min.js` – copy from jsnes build or npm
- `mario.nes` – NES ROM (place in project dir; ensure you have the right to use it)

## Build

From the project directory:

```bash
python build_pdf.py
```

This produces `nespdf.pdf` in the same folder. The script is a single file with no dependencies; it writes the PDF structure directly (like pdftris’ `gengrid.py`).

## How it works

- **Display**: Same approach as [DoomPDF](https://github.com/ading2210/doompdf): 120 text fields (`field_0`…`field_119`) at the top, one per scanline, each set to a string of ASCII characters for a 6-shade monochrome image (`#` `b` `/` `?` `:` `_`). Uses `globalThis.getField()` so it can work in Chromium-based browsers where the document is not `this`. Only updates a row when its string changes.
- **OpenAction** runs embedded JavaScript on open: loads jsnes, decodes the base64 ROM, then after a short delay starts the emulator and a ~30 fps timer.
- **Buttons** are laid out like an NES controller (D-pad left, Select/Start center, B/A right), placed just below the game area. **Run** starts the emulator if it didn’t auto-start.

## Usage

Open `nespdf.pdf` in **Chromium** (Chrome, Edge) or **Adobe Acrobat Reader**, and allow JavaScript when prompted. Click **Run** if the game doesn’t start automatically, then use the on-screen buttons to play.

## Troubleshooting

**Run / buttons do nothing**  
- **DoomPDF** uses button **Additional Actions** `/AA /D` (mouse down) and `/AA /U` (mouse up); **pdftris** uses the widget **activation** action `/A` with a separate script stream. We use both: `/A` plus `/AA /U` on the Run button so click is handled even if the viewer only supports one of them.  
- Button scripts run in a context that may not see the main script’s globals. We attach `startEmulator`, `keyDown`, `keyUp`, and `jsnes` to `globalThis` so button scripts call `globalThis.startEmulator()` etc.  
- The **page** has an open action `/AA /O` (like DoomPDF’s `page.AA.O`) so the main script can run when the page is shown, not only via document OpenAction.

**Game area stays blank**  
- The “screen” is 120 text fields; each frame we set `field_0`…`field_119` via `getField("field_"+row).value = string`.  
- If the viewer never runs the main script (no OpenAction and no page open action), the emulator never starts and nothing is drawn.  
- If the viewer runs the script but **does not support `getField`** (e.g. some built-in viewers), we cannot write to the fields and the area stays empty.  
- Use **Adobe Acrobat Reader** or a **Chromium** browser that allows PDF JavaScript; allow execution when prompted. If it still doesn’t draw, that viewer likely restricts or omits the form field API.
