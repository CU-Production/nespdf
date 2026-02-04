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
