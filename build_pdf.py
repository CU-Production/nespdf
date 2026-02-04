#!/usr/bin/env python3
"""
nespdf - NES emulator inside a PDF (single-file, no dependencies).
Generates a PDF that embeds jsnes + ROM and runs the emulator using
form fields for display (like pdftris). Run: python build_pdf.py
Requires jsnes.min.js and mario.nes in the same directory.
"""
from base64 import b64encode
import os
import re
import sys

# --- Layout constants (match PDF object refs below) ---
SCRIPT_MAIN_ID = 42
PAGE_ID = 16
ANNOTS_ID = 21
FIRST_ROW_ID = 50
NUM_ROWS = 120
FIRST_BTN_ID = 170
FIRST_BTN_SCRIPT_ID = 179  # 9 scripts 179..187 (buttons 170..178)
# Temporary debug: 5 text fields (debug_0..debug_4) top-right. debug_0=main script status, debug_1=Run/ROM, debug_2=frame count, debug_3=last button clicked. Remove DEBUG_* and debugLog/field_list+make_text_field for debug_* to disable.
DEBUG_FIELD_IDS = list(range(188, 193))
NUM_DEBUG_FIELDS = 5

# Screen: 128x120 chars (2x scale from 256x240)
DISPLAY_COLS = 128
DISPLAY_ROWS = 120

# --- Glue script (runs inside PDF after jsnes is loaded) ---
# Display logic follows DoomPDF: globalThis.getField + ASCII-only chars (same-width in Chrome text fields)
# ROM base64 is built in multiple lines to avoid single-line length limits in PDF JS parser
GLUE_SCRIPT = r"""
var romBase64 = "";
ROM_CHUNKS_PLACEHOLDER
var DISPLAY_ROWS = 120;
var DISPLAY_COLS = 128;
function getField(name) {
  if (typeof globalThis !== "undefined" && typeof globalThis.getField === "function") return globalThis.getField(name);
  if (typeof this !== "undefined" && typeof this.getField === "function") return this.getField(name);
  return null;
}
function debugLog(msg, slot) { try { var f = getField("debug_" + (slot !== undefined ? slot : 0)); if (f && "value" in f) f.value = String(msg); } catch (e) {} }
debugLog("script start");
var screenFields = [];
for (var r = 0; r < DISPLAY_ROWS; r++) { try { var f = getField("field_" + r); screenFields[r] = (f && "value" in f) ? f : null; } catch (e) { screenFields[r] = null; } }
var debugField2 = null;
try { var f = getField("debug_2"); debugField2 = (f && "value" in f) ? f : null; } catch (e) {}
function drawTestPattern() {
  var cols = DISPLAY_COLS;
  for (var row = 0; row < DISPLAY_ROWS; row++) {
    var s = "";
    if (row === 0 || row === DISPLAY_ROWS - 1) { for (var c = 0; c < cols; c++) s += "#"; }
    else {
      s += "#";
      for (var c = 1; c < cols - 1; c++) {
        if (row === 59) { var t = "  NES PDF TEST - click Run  "; s += t.charAt(Math.floor((c - 1) / 4) % t.length) || " "; }
        else if (row === 60) { var t = "  (screen = field_0..119)  "; s += t.charAt(Math.floor((c - 1) / 4) % t.length) || " "; }
        else s += (row % 5 === 0 || c % 10 === 0) ? "." : " ";
      }
      s += "#";
    }
    try { var f = screenFields[row] || getField("field_" + row); if (f && "value" in f) f.value = s; } catch (e) {}
  }
  debugLog("test drawn", 4);
}
drawTestPattern();
function luminance(rgb24) {
  var r = (rgb24 >> 16) & 0xff, g = (rgb24 >> 8) & 0xff, b = rgb24 & 0xff;
  return (r * 0.299 + g * 0.587 + b * 0.114);
}
var rowCache = [];
for (var r = 0; r < DISPLAY_ROWS; r++) rowCache[r] = "";
function onFrame(fb) {
  var fields = (typeof app !== "undefined" && app.nespdf_screenFields) ? app.nespdf_screenFields : screenFields;
  var db2 = (typeof app !== "undefined" && app.nespdf_debugField2) ? app.nespdf_debugField2 : debugField2;
  var cache = (typeof app !== "undefined" && app.nespdf_rowCache) ? app.nespdf_rowCache : rowCache;
  var fc;
  if (typeof app !== "undefined") { app.nespdf_frameCount = (app.nespdf_frameCount || 0) + 1; fc = app.nespdf_frameCount; } else { frameCount++; fc = frameCount; }
  if (fc % 5 === 0) { try { var d = (typeof app !== "undefined" && app.nespdf_debugLog) ? app.nespdf_debugLog : debugLog; if (db2 && "value" in db2) db2.value = "frames:" + fc; else d("frames:" + fc, 2); } catch (e) {} }
  for (var row = 0; row < DISPLAY_ROWS; row++) {
    var s = "";
    for (var col = 0; col < DISPLAY_COLS; col++) {
      var y = row * 2, x = col * 2;
      var i0 = y * 256 + x, i1 = y * 256 + x + 1, i2 = (y + 1) * 256 + x, i3 = (y + 1) * 256 + x + 1;
      var avg = (luminance(fb[i0]) + luminance(fb[i1]) + luminance(fb[i2]) + luminance(fb[i3])) / 4;
      if (avg > 200) s += "_";
      else if (avg > 150) s += ":";
      else if (avg > 100) s += "?";
      else if (avg > 50) s += "/";
      else if (avg > 25) s += "b";
      else s += "#";
    }
    if (s === cache[row]) continue;
    cache[row] = s;
    try { var f = fields[row] || (typeof app !== "undefined" && app.nespdf_getField && app.nespdf_getField("field_" + row)); if (f && "value" in f) f.value = s; } catch (e) {}
  }
}
var nes = new jsnes.NES({ onFrame: onFrame, onAudioSample: function() {} });
debugLog("jsnes ok");
function base64Decode(b) {
  var k = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", r = "", i, n1, n2, n3, n4, outLen;
  for (i = 0; i < b.length; i += 4) {
    n1 = k.indexOf(b[i]); n2 = k.indexOf(b[i+1]); n3 = b[i+2]==="=" ? -1 : k.indexOf(b[i+2]); n4 = b[i+3]==="=" ? -1 : k.indexOf(b[i+3]);
    if (n1 < 0 || n2 < 0) break;
    r += String.fromCharCode((n1<<2)|(n2>>4));
    if (n3 >= 0) r += String.fromCharCode(((n2&15)<<4)|(n3>>2));
    if (n4 >= 0) r += String.fromCharCode(((n3&3)<<6)|n4);
  }
  return r;
}
function toBinaryString(x) {
  if (typeof x === "string") return x;
  if (x && typeof x.length === "number") { var s = ""; for (var i = 0; i < x.length; i++) s += String.fromCharCode((x[i] != null ? x[i] : 0) & 255); return s; }
  return "";
}
function ensureBinaryString(s) {
  if (typeof s !== "string" || s.length === 0) return "";
  var out = "";
  for (var i = 0; i < s.length; i++) out += String.fromCharCode(s.charCodeAt(i) & 0xff);
  return out;
}
var romStr = "";
try {
  romStr = base64Decode(romBase64);
  if (!romStr && typeof atob === "function") romStr = atob(romBase64);
  if (!romStr && typeof util !== "undefined" && util.decodeBase64) romStr = toBinaryString(util.decodeBase64(romBase64));
} catch (e) {}
romStr = ensureBinaryString(romStr);
var nesHeader = String.fromCharCode(0x4e, 0x45, 0x53, 0x1a);
var romOk = (romStr.length >= 16 && romStr.indexOf(nesHeader) === 0);
if (!romOk) debugLog("rom bad len=" + romStr.length + " h=" + (romStr.length>=4 ? [romStr.charCodeAt(0),romStr.charCodeAt(1),romStr.charCodeAt(2),romStr.charCodeAt(3)].join(",") : "?"), 4);
var running = false;
var frameCount = 0;
var keysDown = [];
for (var i = 0; i < 8; i++) keysDown[i] = false;
function toggleKey(btn) {
  var k = (typeof app !== "undefined" && app.nespdf_keysDown) ? app.nespdf_keysDown : keysDown;
  if (k[btn]) { keyUp(btn); k[btn] = false; }
  else { keyDown(btn); k[btn] = true; }
}
function runOneFrame() {
  var n = (typeof app !== "undefined" && app.nespdf_nes) ? app.nespdf_nes : nes;
  if (n && typeof n.frame === "function") { try { n.frame(); } catch(e) {} }
}
function tick() {
  if (typeof app !== "undefined" && app.nespdf_running === false) return;
  if (!running && (typeof app === "undefined" || app.nespdf_running !== true)) return;
  runOneFrame();
  if (typeof app !== "undefined" && app.nespdf_useInterval) return;
  if (typeof app !== "undefined" && app.setTimeout) app.setTimeout("app.nespdf_tick()", 33);
  else if (typeof setTimeout !== "undefined") setTimeout(tick, 33);
}
function startEmulator() {
  debugLog("run clicked", 1);
  if (running) return;
  running = true;
  if (typeof app !== "undefined") app.nespdf_running = true;
  if (!romOk) { debugLog("rom invalid", 1); running = false; if (typeof app !== "undefined") app.nespdf_running = false; return; }
  try { nes.loadROM(romStr); debugLog("rom ok", 1); } catch(e) { debugLog("rom err:" + e, 1); running = false; if (typeof app !== "undefined") app.nespdf_running = false; return; }
  if (typeof app !== "undefined") { app.nespdf_tick = tick; app.nespdf_nes = nes; app.nespdf_runOneFrame = runOneFrame; app.nespdf_useInterval = false; }
  for (var i = 0; i < 5; i++) runOneFrame();
  if (typeof app !== "undefined" && app.setInterval) { app.setInterval("app.nespdf_tick()", 33); app.nespdf_useInterval = true; debugLog("interval on", 1); }
  else if (typeof app !== "undefined" && app.setTimeout) { app.setTimeout("app.nespdf_tick()", 33); debugLog("timeout on", 1); }
  else if (typeof setInterval !== "undefined") { setInterval(tick, 33); if (typeof app !== "undefined") app.nespdf_useInterval = true; debugLog("interval on", 1); }
  else if (typeof setTimeout !== "undefined") { setTimeout(tick, 33); debugLog("timeout on", 1); }
  else { running = false; if (typeof app !== "undefined") app.nespdf_running = false; debugLog("no timer", 1); return; }
}
if (typeof setTimeout !== "undefined") setTimeout(startEmulator, 350); else if (typeof app !== "undefined" && app.setTimeout) app.setTimeout("startEmulator()", 350); else startEmulator();
function keyDown(btn) { var n = (typeof app !== "undefined" && app.nespdf_nes) ? app.nespdf_nes : nes; try { if (n) n.buttonDown(1, btn); } catch(e) {} }
function keyUp(btn) { var n = (typeof app !== "undefined" && app.nespdf_nes) ? app.nespdf_nes : nes; try { if (n) n.buttonUp(1, btn); } catch(e) {} }
if (typeof globalThis !== "undefined") { globalThis.startEmulator = startEmulator; globalThis.keyDown = keyDown; globalThis.keyUp = keyUp; globalThis.toggleKey = toggleKey; globalThis.debugLog = debugLog; globalThis.tick = tick; globalThis.nes = nes; if (typeof jsnes !== "undefined") globalThis.jsnes = jsnes; }
if (typeof app !== "undefined") { app.nespdf_tick = tick; app.startEmulator = startEmulator; app.nespdf_keyDown = keyDown; app.nespdf_keyUp = keyUp; app.nespdf_toggleKey = toggleKey; app.nespdf_keysDown = keysDown; app.nespdf_screenFields = screenFields; app.nespdf_debugField2 = debugField2; app.nespdf_rowCache = rowCache; app.nespdf_getField = getField; app.nespdf_debugLog = debugLog; }
"""

# jsnes Controller: A=0, B=1, SELECT=2, START=3, UP=4, DOWN=5, LEFT=6, RIGHT=7
# Toggle: click = press (keyDown), click again = release (keyUp) so holding one button = continuous move
BUTTONS = [
    ("btn_Run", "Run", "var D=globalThis.debugLog||function(){}; D('Run',3); var fn=(globalThis.startEmulator||(typeof startEmulator==='function'?startEmulator:null)); if(fn) fn();"),
    ("btn_Up", "U", "var D=globalThis.debugLog||function(){}; D('U',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_UP);"),
    ("btn_Down", "D", "var D=globalThis.debugLog||function(){}; D('D',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_DOWN);"),
    ("btn_Left", "L", "var D=globalThis.debugLog||function(){}; D('L',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_LEFT);"),
    ("btn_Right", "R", "var D=globalThis.debugLog||function(){}; D('R',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_RIGHT);"),
    ("btn_Select", "Se", "var D=globalThis.debugLog||function(){}; D('Se',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_SELECT);"),
    ("btn_Start", "St", "var D=globalThis.debugLog||function(){}; D('St',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_START);"),
    ("btn_B", "B", "var D=globalThis.debugLog||function(){}; D('B',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_B);"),
    ("btn_A", "A", "var D=globalThis.debugLog||function(){}; D('A',3); var J=globalThis.jsnes||jsnes,C=J.Controller,T=(typeof app!=='undefined'&&app.nespdf_toggleKey)||globalThis.toggleKey; if(T) T(C.BUTTON_A);"),
]
NUM_BUTTONS = len(BUTTONS)

# Page size (points)
PAGE_W, PAGE_H = 612, 792
# Screen: NES 256x240 with 8:7 pixel aspect -> display ratio 2048:1680 = 1.219. Full 128x120 chars visible.
# Target: width 512pt, height 512/1.22 = 420pt so ratio correct and fits page (margins 50 left, 50 right, 30 top).
SCREEN_X = 50
SCREEN_TOP = 762  # top of row 0; bottom of row 119 at 762 - 120*ROW_HEIGHT
# 128*CHAR_WIDTH = 512, 120*ROW_HEIGHT = 420 => CHAR_WIDTH=4, ROW_HEIGHT=3.5; ratio 512/420 = 1.22
CHAR_WIDTH = 4.0
ROW_HEIGHT = 3.5
BTN_SIZE = 28
# NES-style layout: below screen, moved up (y +160). (x,y) = bottom-left of button.
# Run center; D-pad U/D/L/R; Select, Start; B, A
BTN_POSITIONS = [
    (218, 328),   # 0 Run
    (76, 284), (76, 228), (62, 256), (90, 256),   # 1-4 U D L R
    (165, 242), (215, 242),   # 5-6 Select Start
    (280, 242), (328, 242),   # 7-8 B A
]


def pdf_escape(s):
    """Escape for PDF string: \\ () \\\\ """
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def stream_escape(s):
    """Ensure stream content does not contain literal 'endstream' on its own line."""
    return s.replace("\rendstream", "\r").replace("\nendstream", "\n")


def make_text_field(obj_id, name, x, y, w, h, default_val="", with_border_style=False, use_monospace=False):
    v = pdf_escape(default_val) if default_val else ""
    bs = "/BS << /W 0 >> " if with_border_style else ""
    da = " /DA (/Cour 8 Tf 0 g)" if use_monospace else ""
    return f"""{obj_id} 0 obj
<<
{bs}/F 4
/FT /Tx
/Ff 2
/MaxLen 256
/MK <<>>
/P {PAGE_ID} 0 R
/Q 0
/Rect [ {x:.1f} {y:.1f} {x + w:.1f} {y + h:.1f} ]
/Subtype /Widget
/T ({pdf_escape(name)})
/Type /Annot
/V ({v}){da}
>>
endobj
"""


def make_button(obj_id, name, label, script_ref, x, y, w, h, add_aa_u=False):
    aa_u = ""
    if add_aa_u:
        aa_u = f"/AA << /U << /JS {script_ref} 0 R /S /JavaScript >> >> "
    return f"""{obj_id} 0 obj
<<
/A << /JS {script_ref} 0 R /S /JavaScript >>
{aa_u}/F 4
/FT /Btn
/Ff 65536
/MK << /BG [ 0.9 0.9 0.9 ] /CA ({pdf_escape(label)}) >>
/P {PAGE_ID} 0 R
/Rect [ {x:.1f} {y:.1f} {x + w:.1f} {y + h:.1f} ]
/Subtype /Widget
/T ({pdf_escape(name)})
/Type /Annot
>>
endobj
"""


def make_script_stream(obj_id, content):
    escaped = stream_escape(content)
    return f"""{obj_id} 0 obj
<< /Length {len(escaped)} >>
stream
{escaped}
endstream
endobj
"""


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    jsnes_path = os.path.join(base, "jsnes.min.js")
    rom_path = os.path.join(base, "mario.nes")

    if not os.path.isfile(jsnes_path):
        print("Error: jsnes.min.js not found", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(rom_path):
        print("Error: mario.nes not found", file=sys.stderr)
        sys.exit(1)

    with open(jsnes_path, "r", encoding="utf-8", errors="replace") as f:
        jsnes_content = f.read()
    # PDF viewers can mishandle the literal \x1a in embedded JS; use runtime header so validation matches our romStr
    nes_literal = '.indexOf("NES' + '\x1a' + '")'
    nes_runtime = '.indexOf(String.fromCharCode(78,69,83,26))'
    if nes_literal in jsnes_content:
        jsnes_content = jsnes_content.replace(nes_literal, nes_runtime, 1)
    with open(rom_path, "rb") as f:
        rom_b64 = b64encode(f.read()).decode("ascii")

    ROM_CHUNK_SIZE = 2048
    rom_chunks = [rom_b64[i : i + ROM_CHUNK_SIZE] for i in range(0, len(rom_b64), ROM_CHUNK_SIZE)]
    # One line per chunk so the script does not hit PDF JS line-length limits
    rom_chunks_js = "\n".join('romBase64 += "' + c + '";' for c in rom_chunks)
    glue = GLUE_SCRIPT.replace("ROM_CHUNKS_PLACEHOLDER", rom_chunks_js)
    wrapped_glue = "try { " + glue + " } catch(e) { if (typeof app !== 'undefined' && app.alert) app.alert('Error: ' + (e.message || e)); }"
    main_script = jsnes_content + "\n" + wrapped_glue

    field_list = []
    fields_pdf = []

    # 120 row text fields (screen) at top of page - names field_0..field_119 like DoomPDF for Chrome
    for i in range(NUM_ROWS):
        obj_id = FIRST_ROW_ID + i
        y = SCREEN_TOP - (i + 1) * ROW_HEIGHT
        field_list.append(f"{obj_id} 0 R")
        fields_pdf.append(
            make_text_field(
                obj_id,
                f"field_{i}",
                SCREEN_X,
                y,
                DISPLAY_COLS * CHAR_WIDTH,
                ROW_HEIGHT,
                with_border_style=True,
                use_monospace=True,
            )
        )

    # Button script streams + buttons (NES layout positions). Run button gets /AA/U like DoomPDF.
    for i, (name, label, script_body) in enumerate(BUTTONS):
        script_id = FIRST_BTN_SCRIPT_ID + i
        btn_id = FIRST_BTN_ID + i
        field_list.append(f"{btn_id} 0 R")
        fields_pdf.append(make_script_stream(script_id, script_body))
        bx, by = BTN_POSITIONS[i]
        fields_pdf.append(make_button(btn_id, name, label, script_id, bx, by, BTN_SIZE, BTN_SIZE, add_aa_u=(i == 0)))

    # Debug fields (top-right): debug_0=status, debug_1=run/rom, debug_2=frames, debug_3=last btn
    DEBUG_X, DEBUG_Y0, DEBUG_W, DEBUG_H = 380, 755, 200, 10
    for i in range(NUM_DEBUG_FIELDS):
        oid = DEBUG_FIELD_IDS[i]
        field_list.append(f"{oid} 0 R")
        fields_pdf.append(
            make_text_field(oid, f"debug_{i}", DEBUG_X, DEBUG_Y0 - i * 12, DEBUG_W, DEBUG_H, default_val=("[debug " + str(i) + "]"))
        )

    field_list_str = " ".join(field_list)
    fields_blob = "\n".join(fields_pdf)

    catalog = f"""1 0 obj
<<
/AcroForm << /Fields [ {field_list_str} ] /DR << /Font << /Helv 10 0 R /Cour 11 0 R >> >> /DA (/Helv 8 Tf 0 g) >>
/OpenAction << /JS {SCRIPT_MAIN_ID} 0 R /S /JavaScript >>
/Pages 2 0 R
/Type /Catalog
>>
endobj
"""

    pages = f"""2 0 obj
<<
/Count 1
/Kids [ {PAGE_ID} 0 R ]
/Type /Pages
>>
endobj
"""

    page = f"""16 0 obj
<<
/AA << /O << /JS {SCRIPT_MAIN_ID} 0 R /S /JavaScript >> >>
/Annots [ {field_list_str} ]
/MediaBox [ 0 0 {PAGE_W} {PAGE_H} ]
/Parent 2 0 R
/Resources << /Font << /Helv 10 0 R /Cour 11 0 R >> >>
/Type /Page
>>
endobj
"""

    font = """10 0 obj
<<
/BaseFont /Helvetica
/Subtype /Type1
/Type /Font
>>
endobj
11 0 obj
<<
/BaseFont /Courier
/Subtype /Type1
/Type /Font
>>
endobj
"""

    main_script_obj = make_script_stream(SCRIPT_MAIN_ID, main_script)

    out_path = os.path.join(base, "nespdf.pdf")
    body_ordered = (
        catalog + pages + font + page + main_script_obj
        + "".join(fields_pdf)
    )
    header = b"%PDF-1.6\n\n"
    body_bytes = body_ordered.encode("utf-8")
    offsets = {}
    for m in re.finditer(rb"(\d+) 0 obj", body_bytes):
        obj_num = int(m.group(1))
        offsets[obj_num] = len(header) + m.start()
    max_obj = max(offsets.keys())
    size = max_obj + 1
    xref_lines = ["xref", "0 %d" % size]
    xref_lines.append("0000000000 65535 f ")
    for i in range(1, max_obj + 1):
        if i in offsets:
            xref_lines.append("%010d 00000 n " % offsets[i])
        else:
            xref_lines.append("0000000000 00000 f ")
    xref_block = "\n".join(xref_lines) + "\n"
    startxref_val = len(header) + len(body_bytes)
    trailer_block = "trailer\n<<\n/Root 1 0 R\n/Size %d\n>>\nstartxref\n%d\n%%%%EOF\n" % (
        size,
        startxref_val,
    )
    with open(out_path, "wb") as f:
        f.write(header)
        f.write(body_bytes)
        f.write(xref_block.encode())
        f.write(trailer_block.encode())

    print("Wrote", out_path)


if __name__ == "__main__":
    main()
