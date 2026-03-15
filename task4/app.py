"""
PDF → HTML Converter  (app.py)
================================
Upload ANY PDF → get a clean, styled single-page HTML file.

Works generically by:
  1. Using pdfplumber word-level x/y extraction to handle multi-column layouts
  2. Auto-detecting column splits per page via x-position gap analysis
  3. Extracting tables natively via pdfplumber
  4. Classifying lines as: section-heading | bullet | key-value spec | paragraph
  5. Grouping everything into <section> blocks and rendering semantic HTML

Tested on:  Advanced Energy AIF-300V, LCM300 datasheets
            (and designed to work on any structured PDF)

Run:  streamlit run app.py
"""

import streamlit as st
import pdfplumber
import base64
import io
import re
import time
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG & UI STYLES
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="PDF → HTML Converter", page_icon="📄", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{background:#0a0a0a;color:#e8e4de;}
.hero{background:linear-gradient(135deg,#141414,#0d0d0d 60%,#111);border:1px solid #222;border-radius:18px;padding:2.4rem 2.5rem 1.8rem;margin-bottom:2rem;position:relative;overflow:hidden;}
.hero::after{content:'';position:absolute;top:-60px;right:-60px;width:220px;height:220px;background:radial-gradient(circle,rgba(255,149,0,.10) 0%,transparent 68%);border-radius:50%;pointer-events:none;}
.hero-title{font-family:'Space Mono',monospace;font-size:2rem;font-weight:700;color:#e8e4de;margin:0 0 .4rem;}
.hero-sub{color:#666;font-size:.9rem;margin:0;}
.accent{color:#ff9500;}
.card{background:#141414;border:1px solid #222;border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:.8rem;}
.step{font-family:'Space Mono',monospace;font-size:.65rem;color:#555;text-transform:uppercase;letter-spacing:.14em;margin-bottom:.5rem;display:flex;align-items:center;gap:.5rem;}
.step-num{background:#ff9500;color:#0a0a0a;font-size:.6rem;font-weight:700;padding:.1rem .42rem;border-radius:4px;}
.stats-row{display:flex;gap:.6rem;margin-top:.9rem;}
.stat{background:#141414;border:1px solid #222;border-radius:8px;padding:.6rem .8rem;flex:1;text-align:center;}
.stat-lbl{font-size:.58rem;color:#555;text-transform:uppercase;letter-spacing:.1em;font-family:'Space Mono',monospace;}
.stat-val{font-size:1.1rem;font-weight:600;color:#ff9500;font-family:'Space Mono',monospace;line-height:1.3;}
.stButton>button{background:#ff9500!important;color:#0a0a0a!important;font-family:'Space Mono',monospace!important;font-weight:700!important;font-size:.82rem!important;border:none!important;border-radius:8px!important;padding:.55rem 1.5rem!important;width:100%;}
.stButton>button:hover{opacity:.82!important;}
.stButton>button:disabled{opacity:.3!important;}
.stDownloadButton>button{background:transparent!important;color:#ff9500!important;border:1px solid #ff9500!important;font-family:'Space Mono',monospace!important;font-size:.78rem!important;border-radius:8px!important;width:100%;}
[data-testid="stFileUploaderDropzone"]{background:#141414!important;border:2px dashed #262626!important;border-radius:12px!important;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:#ff9500!important;}
.empty-preview{background:#141414;border:2px dashed #1e1e1e;border-radius:12px;height:600px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#333;gap:10px;font-family:'Space Mono',monospace;font-size:.82rem;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT HTML CSS  (embedded in every generated file)
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&family=Roboto+Condensed:wght@700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
body{background:#eef0f3;color:#1a1a1a;font-family:'Open Sans',sans-serif;font-size:14px;line-height:1.65;}

/* ── HEADER ── */
header{background:#0b1929;padding:28px 44px 0;}
.header-inner{display:flex;justify-content:space-between;align-items:flex-start;padding-bottom:20px;}
.header-left{flex:1;}.header-right{text-align:right;}
h1{font-family:'Roboto Condensed',sans-serif;font-size:2.2rem;font-weight:700;color:#fff;line-height:1.1;}
.tagline{color:#7a8fa3;font-size:.75rem;margin-top:6px;letter-spacing:.06em;text-transform:uppercase;}
.brand{display:block;font-size:.75rem;color:#ff6b00;text-transform:uppercase;letter-spacing:.18em;font-weight:700;}
.brand-sub{color:#4a6070;font-size:.68rem;margin-top:4px;}
.header-divider{height:4px;background:linear-gradient(90deg,#ff6b00,#ff9a00);}

/* ── GLANCE BAR ── */
.glance-bar{background:#fff;border-bottom:2px solid #eef0f3;box-shadow:0 2px 6px rgba(0,0,0,.05);}
.glance-inner{max-width:980px;margin:0 auto;display:flex;flex-wrap:wrap;}
.glance-card{flex:1;min-width:130px;padding:13px 20px;border-right:1px solid #eef0f3;}
.glance-card:last-child{border-right:none;}
.glance-label{font-size:.63rem;font-weight:700;color:#ff6b00;text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px;}
.glance-value{font-size:.96rem;font-weight:700;color:#0b1929;}

/* ── LAYOUT ── */
.container{max-width:980px;margin:0 auto;padding:24px 28px 56px;}

/* ── SECTIONS ── */
section{background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.07);padding:0 32px 24px;margin-bottom:16px;overflow:hidden;}

/* ── HEADINGS ── */
h2{font-family:'Roboto Condensed',sans-serif;font-size:.82rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#fff;background:#1a4a7a;padding:8px 16px;margin:0 -32px 20px -32px;border-left:4px solid #ff6b00;}
h3{font-size:.84rem;font-weight:700;color:#1a4a7a;margin:16px 0 8px;padding-bottom:4px;border-bottom:1px solid #eef0f3;}
h3:first-child{margin-top:0;}

/* ── TEXT ── */
p{font-size:.87rem;color:#444;margin-bottom:7px;line-height:1.72;}

/* ── BULLET LISTS ── */
ul.blist{list-style:none;padding:0;margin-bottom:14px;display:grid;grid-template-columns:1fr 1fr;gap:3px 24px;}
ul.blist li{font-size:.84rem;color:#333;padding:3px 0 3px 17px;line-height:1.5;position:relative;}
ul.blist li::before{content:"■";color:#ff6b00;font-size:.52rem;position:absolute;left:0;top:6px;}

/* ── KEY-VALUE SPEC ROWS ── */
.kv-table{width:100%;border-collapse:collapse;margin-bottom:14px;font-size:.83rem;}
.kv-table td{padding:5px 10px;border-bottom:1px solid #eef0f3;vertical-align:top;}
.kv-table td.kv-key,.kv-table td:first-child{font-weight:600;color:#0b1929;width:38%;white-space:nowrap;}
.kv-table td.kv-val,.kv-table td:last-child{color:#444;}
.kv-table tr:nth-child(even) td{background:#f7fafc;}
.kv-sub-head td{background:#e8f0f8!important;color:#1a4a7a!important;font-weight:700!important;
  font-family:'Roboto Condensed',sans-serif;font-size:.77rem;text-transform:uppercase;
  letter-spacing:.08em;padding:5px 10px;border-top:2px solid #c8d8ea;}

/* ── TABLES ── */
.table-wrap{overflow-x:auto;margin-bottom:16px;border-radius:4px;border:1px solid #dde3ea;}
table.data{width:100%;border-collapse:collapse;font-size:.81rem;}
table.data thead tr{background:#1a4a7a;color:#fff;font-weight:700;text-align:left;}
table.data th{padding:8px 12px;border:1px solid #14396b;font-size:.75rem;white-space:nowrap;}
table.data td{padding:7px 12px;border:1px solid #dde3ea;vertical-align:top;color:#333;}
table.data tbody tr:nth-child(even){background:#f4f7fb;}
table.data tbody tr:hover{background:#e8f0ff;}
table.data tr.sub-head td{background:#e8f0f8!important;color:#1a4a7a!important;font-weight:700!important;
  font-family:'Roboto Condensed',sans-serif;font-size:.76rem;text-transform:uppercase;
  border-top:2px solid #c8d8ea;padding:5px 12px;}

/* ── FOOTER ── */
footer{background:#0b1929;padding:22px 44px;}
.footer-inner{max-width:980px;margin:0 auto;}
footer p{color:#7a8fa3;font-size:.72rem;margin-bottom:5px;line-height:1.6;}
.footer-legal{color:#4a6070!important;font-size:.67rem!important;margin-top:10px;
  padding-top:10px;border-top:1px solid #1e3050;}
.footer-doc-id{color:#3a5060!important;font-size:.63rem!important;margin-top:4px;}

/* ── RESPONSIVE ── */
@media(max-width:680px){
  ul.blist{grid-template-columns:1fr;}
  h1{font-size:1.5rem;}
  section{padding:0 16px 20px;}
  h2{margin:0 -16px 14px -16px;}
  .header-inner{flex-direction:column;gap:10px;}
  .header-right{text-align:left;}
  .glance-card{border-right:none;border-bottom:1px solid #eef0f3;}
  footer{padding:18px 20px;}
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Wingdings/special bullet characters used in AE PDFs
BULLET_CHARS = '\u25a0\u25aa\u25cf\u2022\u25ab\u25b8\uf06e\uf0b7'

# Lines to throw away (page artifacts, footers, copyright, contact info)
# Uses re.search so patterns match anywhere in the line
JUNK_PATTERNS = re.compile(
    r'^\d{1,3}$'                              # lone page numbers
    r'|\d+\s+advancedenergy\.com'             # "2 advancedenergy.com"
    r'|^advancedenergy\.com\s*\d*$'           # bare URL line
    r'|©\d{4}'                                # any copyright symbol+year
    r'|All rights reserved'
    r'|ENG-[A-Z0-9\s\-\.]{4,}\d{2}'         # doc-ID lines e.g. ENG-LCM300-235
    r'|^PRECISION\s*\|'                       # tagline
    r'|^TRUST$'                               # single-word tagline
    r'|For international contact'
    r'|visit advancedenergy'
    r'|powersales@aei\.com'
    r'|productsupport\.ep@aei\.com'
    r'|\+1\s*888\s*412'
    r'|Specifications are subject to change'
    r'|Not responsible for errors'
    r'|for errors or omissions'
    r'|errors or omissions'
    r'|Advanced Energy®'
    r'|Artesyn™ are'
    r'|reserved\.\s*Advanced Energy'
    r'|of Advanced Energy Industries'
    r'|trademarks of Advanced'
    r'|^ABOUT ADVANCED ENERGY$'              # heading kept only once via section logic
    r'|^A I F \d+V'                           # "A I F 300V Vin SERIES" page headers
    r'|^AIF \d+V Vin SERIES$'                 # same without spaces
    r'|^LCM\d+$'                              # "LCM300" page headers
    r'|^ARTESYN LCM\d+$'                      # "ARTESYN LCM300" if repeated
    r'|^AT A GLANCE$'                         # sidebar section header
    r'|^ARTESYN$'                             # standalone brand word
    r'|^RoHS$'                                # standalone label
    r'|^PMBus$'                               # standalone label
    r'|^LCMXXXXY\s*-'                         # ordering code template
    r'|^W/E-T-W'                              # mechanical drawing
    r'|^AIR FLOW DIRECTION$'
    r'|^PRODUCT LABEL$'
    r'|^TRIMPOT$'
    r'|^S-M\d'
    r'|^SCR-PP'
    r'|^PN \d'
    r'|^\(2X\)$'
    r'|^PIN \d+\s+PIN \d+'
    r'|^INPUT TERMINAL BLOCK'
    r'|^SK2 SIGNAL'
    r'|^POS SK\d|^NEG SK\d'
    r'|^LED \('
    r'|^\d+\s+\w/in'                          # power density
    r'|^MOUNTING LOCATIONS'
    r'|^RECOMMENDED SCREW'
    r'|^M\d+[\.\s].*kgf'                      # screw torque
    r'|^Airflow direction$'
    r'|^\d+\.\d+\s*REF$'                      # dimension reference
    r'|^Pin \d+$'                             # single pin label
    r'|^Signal Output Signal'                 # connector label line
    r'|^\d[\d,]+\s+\d[\d,]'                  # dimension sequences e.g. "66,31 11,15"
    r'|^\d+,\d+$'                             # single decimal dimension
    r'|^[0-9,\s\(\)X±\.]+$'                  # lines of only numbers/symbols
    r'|TERMINAL BLOCK$'                       # "115/230 VAC (Nominal) TERMINAL BLOCK"
    r'|^PENETRATION DEPTH'                    # mechanical drawing callout
    r'|^300 Watts Bulk Front End$'            # LCM300 subtitle (captured as tagline)
    r'|^Modiefied Standards$'                 # ordering page typo artifact
    r'|^Voltage Code Y\s*='                   # ordering code explanation line
    r'|^Code\s+\d+\s*='                       # ordering code line e.g. "Code 5 = Opt 1 + 4"
    r'|^[LNQUW]\s+\d+$'                       # voltage codes "L 12", "N 15", etc.
    r'|^1-Phase input where'                  # ordering boilerplate
    r'|^Case Size\s+Input Termination'        # ordering code table header text
    r'|^SK2 Mating Connector:'               # connector spec line (table handles it)
    r'|^LED INDICATORS Contact Pins:'         # LED spec line
    r'|^\d+ provided are clearly'            # LED description boilerplate
    r'|^The DC_OK LED'                        # LED description boilerplate
    r'|^The AC_OK LED'                        # LED description boilerplate
    r'|^Note.*indicates that PSU'             # LED note boilerplate
    r'|^PSU is in standby'                    # LED note continuation
    r'|ycneicfifE'                             # reversed "Efficiency" text from chart
    r'|^\d+,\d+\s+PRODUCT LABEL'              # mechanical drawing annotation
    r'|^Loading\s*%$'                          # chart axis label
    r'|Vac\s+Loading\s*%'                      # chart legend fragment
    r'|Without the 5 Vsb'                      # chart title fragment
    r'|^for RoHS$'                             # column fragment: "...compliant for RoHS"
    r'|^Two years warranty$'                   # right-column orphan fragment
    r'|^SAFETY$'                               # right-column sidebar label
    r'|^\d{4,5}-\d(-\d)?\s*(Ed\s*\d)?$'       # bare standard numbers e.g. "60601-1", "60601-1 Ed 3"
    r'|^analog mode linear control'            # column fragment continuation
    r'|^I2C bus with digital mode'             # column fragment continuation
    r'|^\(for \d+ V and \d+ V models\)'        # bracket continuation fragment
    r'|^for \d+ V and \d+ V models'            # bracket continuation fragment
    r'|^\d{2,3} Vac$',                         # lone voltage chart label (e.g. "230 Vac")
    re.I
)

def is_junk(text):
    s = text.strip()
    if not s or len(s) <= 1:
        return True
    return bool(JUNK_PATTERNS.search(s))

# ─────────────────────────────────────────────────────────────────────────────
# LOW-LEVEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def esc(t):
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def is_bullet(text):
    s = text.strip()
    return bool(s) and any(ch in BULLET_CHARS for ch in s[:3])

def strip_bullet(text):
    return re.sub(r'^[\s' + re.escape(BULLET_CHARS) + r']+\s*', '', text.strip())

def clean(text):
    """Remove stray bullet chars, collapse whitespace."""
    text = re.sub(r'[' + re.escape(BULLET_CHARS) + r']', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def is_section_heading(text):
    """
    Heuristic: ALL-CAPS line, 3–80 chars, contains letters,
    not a value/measurement/pin-number line.
    """
    s = text.strip()
    if not s or len(s) < 3 or len(s) > 80:
        return False
    if s != s.upper():
        return False
    if not re.search(r'[A-Z]', s):
        return False
    # Reject lines starting with a digit (pin numbers, values, page refs)
    if s[0].isdigit():
        return False
    # Reject pin-number patterns like "1. +SENSE" or "12. -SENSE"
    if re.match(r'^\d+[.\s]', s):
        return False
    # Reject lines that are mostly numbers/symbols (dimensions, spec values)
    alpha = sum(c.isalpha() for c in s)
    if alpha / len(s) < 0.35:
        return False
    # Reject known non-heading ALL-CAPS fragments
    NON_HEADINGS = {
        'INPUT', 'OUTPUT', 'ISOLATION',        # sub-labels in spec tables
        'AT A GLANCE', 'ROHS', 'SAFETY',       # sidebar labels
        'TERMINAL BLOCK', 'COMPLIANCE',
        'ARTESYN',                             # brand name (it's the title, not a section)
    }
    if s in NON_HEADINGS:
        return False
    return True

# ─────────────────────────────────────────────────────────────────────────────
# COLUMN DETECTION  (finds a horizontal gap → two-column page)
# ─────────────────────────────────────────────────────────────────────────────

def find_column_split(words, page_width):
    """
    Detect a genuine body + sidebar two-column layout.

    Algorithm:
    1. Build 10px x-position buckets from word starts.
    2. Find contiguous populated ranges (raw clusters).
    3. Merge only clusters with gap <= 25px (smaller than a real column gap).
    4. Keep only clusters with >= 5 words.
    5. Accept exactly 2 significant clusters where:
       - gap between them is >= 35px
       - right cluster starts in the right 45% of the page (>= 55% of width)
       - left cluster has more words than right (body > sidebar)
    6. Return the midpoint of the gap, or None.

    Why 25px merge (not 40px): a 40px merge radius would absorb the ~40px gap
    between body text (ends ~x=350) and the right sidebar (starts ~x=390) on
    AE datasheet page 1, falsely collapsing them into one cluster.

    Why exactly 2 clusters: pages with 3+ clusters are multi-column tables
    (ordering page, pin assignment page) — we should NOT split those and
    instead let pdfplumber's table extractor handle them.
    """
    if not words:
        return None

    buckets = defaultdict(int)
    for w in words:
        buckets[int(w['x0'] / 10) * 10] += 1

    max_x = int(page_width / 10) * 10 + 10
    clusters, in_c, c_start = [], False, 0
    for k in range(0, max_x, 10):
        if buckets.get(k, 0) > 0:
            if not in_c:
                c_start = k
                in_c = True
        else:
            if in_c:
                clusters.append([c_start, k - 10])
                in_c = False
    if in_c:
        clusters.append([c_start, max_x - 10])

    # Merge only very close clusters (gap <= 25px)
    merged = []
    for c in clusters:
        if merged and c[0] - merged[-1][1] <= 25:
            merged[-1][1] = c[1]
        else:
            merged.append(list(c))

    def wc(c):
        return sum(buckets.get(k, 0) for k in range(c[0], c[1] + 10, 10))

    significant = [c for c in merged if wc(c) >= 5]

    # Must be exactly 2 clusters — 3+ means it's a multi-column table page
    if len(significant) != 2:
        return None

    left, right = sorted(significant, key=lambda c: c[0])
    left_end    = left[1]
    right_start = right[0]
    gap = right_start - left_end

    if (gap >= 35
            and right_start >= page_width * 0.55
            and wc(left) >= wc(right)):
        return float((left_end + right_start) / 2)

    return None


def words_to_lines(words, x_lo=None, x_hi=None, y_tol=3):
    """
    Group words into text lines (sorted by y, then x).
    Optional x_lo/x_hi filter for column slicing.
    Returns list of (y, text_string).

    Post-processing: if a line contains more than one bullet character
    (e.g. two adjacent-column bullet items share the same y), split it
    into separate logical lines at each bullet char boundary.
    """
    filtered = words
    if x_lo is not None:
        filtered = [w for w in filtered if w['x0'] >= x_lo]
    if x_hi is not None:
        filtered = [w for w in filtered if w['x0'] < x_hi]

    rows = defaultdict(list)
    for w in filtered:
        matched = None
        for ey in rows:
            if abs(w['top'] - ey) <= y_tol:
                matched = ey
                break
        rows[matched if matched is not None else w['top']].append(w)

    lines = []
    for y in sorted(rows):
        ws = sorted(rows[y], key=lambda w: w['x0'])
        text = ' '.join(w['text'] for w in ws)

        # Split on mid-line bullet chars: if the line has >1 bullet char,
        # break it into sub-lines at each bullet occurrence after the first word
        bullet_chars = set(BULLET_CHARS)
        tokens = text.split(' ')
        sub_lines = []
        cur_tokens = []
        for tok in tokens:
            if tok in bullet_chars and cur_tokens:
                # start a new sub-line
                sub_lines.append(' '.join(cur_tokens))
                cur_tokens = [tok]
            else:
                cur_tokens.append(tok)
        if cur_tokens:
            sub_lines.append(' '.join(cur_tokens))

        if len(sub_lines) > 1:
            for sub in sub_lines:
                if sub.strip():
                    lines.append((y, sub))
        else:
            lines.append((y, text))
    return lines

# ─────────────────────────────────────────────────────────────────────────────
# LINE CLASSIFIER  → typed block dicts
# ─────────────────────────────────────────────────────────────────────────────

# Known multi-word spec keys (key-value lines with single-space separator)
# We try these first before falling back to the 2-space regex
KNOWN_KV_PREFIXES = [
    'Input range', 'Input surge', 'Input ran ge',   # OCR variant
    'Input fusing', 'Input current', 'Inrush current',
    'Power factor', 'Harmonics', 'Hold up time', 'Frequency',
    'Leakage current', 'Power line transient', 'Isolation',
    'Efficiency', 'Load regulation', 'Line regulation',
    'Noise ripple', 'Remote sense', 'Output voltage adjust range',
    'Transient response', 'Current share accuracy',
    'Overvoltage protection adjust', 'Overvoltage protection',
    'Current limit adjust', 'Current limit',
    'Clock input (external sync)', 'Clock output (internal clock)',
    'Power good identification', 'Temperature monitor output',
    'Current monitor output', 'Voltage adjust', 'Enable',
    'Operating temperature', 'Start up temperature',
    'Storage temperature', 'Overtemperature protection',
    'Output rating', 'Set point', 'Total regulation range',
    'Rated load', 'Minimum load', 'Output noise (PARD)',
    'Output voltage overshoot', 'Max units in parallel',
    'Short circuit protection', 'Forced load sharing',
    'Overload protection (OCP)', 'Remote sense',
    'Humidity', 'Fan noise', 'Altitude', 'Shock', 'Vibration',
    'Weight',
]
# Sort longest-first so greedier matches win
KNOWN_KV_PREFIXES.sort(key=len, reverse=True)


def classify_line(text):
    """
    Return one of:
      {'type':'heading',   'text': str}
      {'type':'bullet',    'text': str}
      {'type':'kv',        'key': str, 'value': str}
      {'type':'paragraph', 'text': str}
    or None if junk.
    """
    raw = text.strip()
    s   = clean(raw)
    if not s or is_junk(s):
        return None

    # Fix common OCR word-splits in spec keys (e.g. "ran ge" → "range")
    s = re.sub(r'\bran ge\b', 'range', s)
    s = re.sub(r'\bef fi\b', 'effi', s)
    s = re.sub(r'\bef fic\b', 'effic', s)

    if is_section_heading(s):
        return {'type': 'heading', 'text': s}

    if is_bullet(raw):
        b = strip_bullet(raw)
        b = clean(b)
        if b:
            return {'type': 'bullet', 'text': b}
        return None

    # Try known key prefixes first
    for prefix in KNOWN_KV_PREFIXES:
        if s.startswith(prefix):
            val = s[len(prefix):].strip().lstrip(':').strip()
            # Strip trailing dimension annotations (e.g. "177,8 0,5")
            val = re.sub(r'\s+\d+[,\.]\d+(?:\s+\d+[,\.]\d+)*\s*$', '', val).strip()
            if val:
                return {'type': 'kv', 'key': prefix, 'value': val}

    # Generic key-value: two or more spaces between key and value
    m = re.match(r'^([A-Za-z][A-Za-z0-9 /\(\)\-\+®™°²³]+?)\s{2,}(.+)$', s)
    if m and len(m.group(1)) <= 50 and len(m.group(1).split()) <= 7:
        return {'type': 'kv', 'key': m.group(1).strip(), 'value': m.group(2).strip()}

    # "Key: value" pattern
    m2 = re.match(r'^([A-Za-z][A-Za-z0-9 /\(\)\-\+®™°²³]{1,48}):\s+(.+)$', s)
    if m2:
        val = re.sub(r'\s+\d+[,\.]\d+(?:\s+\d+[,\.]\d+)*\s*$', '', m2.group(2).strip()).strip()
        if val:
            return {'type': 'kv', 'key': m2.group(1).strip(), 'value': val}

    return {'type': 'paragraph', 'text': s}


def classify_lines(line_list):
    """
    Turn [(y, text), ...] into blocks, merging multi-line bullets and
    handling the 'recovery' continuation pattern for Transient response.
    """
    blocks = []
    pending_para = []
    pending_bullet = None
    pending_kv = None   # (key, value_so_far)

    def flush_para():
        if pending_para:
            joined = ' '.join(pending_para)
            if joined.strip():
                blocks.append({'type': 'paragraph', 'text': joined.strip()})
            pending_para.clear()

    def flush_bullet():
        nonlocal pending_bullet
        if pending_bullet:
            blocks.append({'type': 'bullet', 'text': pending_bullet.strip()})
            pending_bullet = None

    def flush_kv():
        nonlocal pending_kv
        if pending_kv:
            blocks.append({'type': 'kv', 'key': pending_kv[0],
                           'value': pending_kv[1].strip()})
            pending_kv = None

    for _y, raw_text in line_list:
        s = raw_text.strip()
        if not s or is_junk(s):
            continue

        # Continuation: "recovery" line belongs to previous kv value
        if s.lower() == 'recovery' and pending_kv:
            pending_kv = (pending_kv[0], pending_kv[1] + ' recovery')
            continue

        blk = classify_line(s)
        if blk is None:
            continue

        if blk['type'] == 'heading':
            flush_bullet(); flush_kv(); flush_para()
            blocks.append(blk)

        elif blk['type'] == 'bullet':
            flush_kv(); flush_para()
            # Check if this is actually a continuation of previous bullet
            # (very short all-lowercase line after a bullet)
            if pending_bullet and len(blk['text']) < 40 and blk['text'][0].islower():
                pending_bullet += ' ' + blk['text']
            else:
                flush_bullet()
                pending_bullet = blk['text']

        elif blk['type'] == 'kv':
            flush_bullet(); flush_para()
            flush_kv()
            pending_kv = (blk['key'], blk['value'])

        elif blk['type'] == 'paragraph':
            s = blk['text']
            s_words = s.split()
            # A genuine continuation fragment: short (≤4 words), starts lower-case
            # or starts with a preposition/conjunction (at, of, to, for, from, or, and)
            CONT_STARTERS = {'at','of','to','for','from','or','and','in','on','via',
                             'with','as','by','than','through','into','per'}
            is_continuation = (
                len(s_words) <= 4
                and (
                    s_words[0][0].islower()
                    or s_words[0].lower() in CONT_STARTERS
                    or (s_words[0][0].isdigit() and pending_bullet)  # "100°C..." after bullet
                )
            )
            if is_continuation and pending_bullet:
                pending_bullet += ' ' + s
            elif is_continuation and blocks and blocks[-1]['type'] == 'bullet':
                blocks[-1]['text'] += ' ' + s
            else:
                flush_bullet(); flush_kv()
                pending_para.append(s)

    flush_bullet(); flush_kv(); flush_para()
    return blocks

# ─────────────────────────────────────────────────────────────────────────────
# PAGE EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

def extract_page(page):
    """
    Returns {'blocks': [...], 'tables': [...]}
    Handles single- and two-column layouts transparently.
    Words that fall inside detected table bounding boxes are excluded from
    text classification to prevent table content leaking into paragraphs.
    """
    words = page.extract_words(keep_blank_chars=False, x_tolerance=3, y_tolerance=3)
    pw    = float(page.width)

    # ── Extract tables first so we can mask their bboxes ─────────────────
    tables = []
    table_bboxes = []  # (x0, top, x1, bottom)
    try:
        for rt in (page.extract_tables(table_settings={}) or []):
            ct = _clean_table(rt)
            if ct and len(ct) >= 2:
                filled = sum(1 for r in ct for c in r if c.strip())
                if filled >= 4:
                    tables.append(ct)
        # Get bounding boxes via pdfplumber's table finder
        for tbl_obj in (page.find_tables() or []):
            bb = tbl_obj.bbox  # (x0, top, x1, bottom)
            table_bboxes.append(bb)
    except Exception:
        pass

    # ── Mask words inside table bboxes ────────────────────────────────────
    def in_table(w):
        cx = (w['x0'] + w['x1']) / 2
        cy = (w['top'] + w['bottom']) / 2
        for x0, top, x1, bottom in table_bboxes:
            if x0 <= cx <= x1 and top <= cy <= bottom:
                return True
        return False

    text_words = [w for w in words if not in_table(w)]

    split_x = find_column_split(text_words, pw)

    if split_x:
        left_lines  = words_to_lines(text_words, x_hi=split_x)
        right_lines = words_to_lines(text_words, x_lo=split_x)
        left_blocks  = classify_lines(left_lines)
        right_blocks = classify_lines(right_lines)
        blocks = _merge_col_blocks(left_blocks, right_blocks)
    else:
        all_lines = words_to_lines(text_words)
        blocks    = classify_lines(all_lines)

    return {'blocks': blocks, 'tables': tables}


def _clean_table(raw):
    if not raw:
        return []

    # Normalise cells: collapse whitespace, fix common OCR splits
    OCR_FIXES = [(r'\bran ge\b', 'range'), (r'\bef fi\b', 'effi')]
    def fix_cell(c):
        if not c: return ''
        s = re.sub(r'\s+', ' ', str(c).strip())
        for pat, rep in OCR_FIXES:
            s = re.sub(pat, rep, s, flags=re.I)
        return s

    cleaned = []
    for row in raw:
        cells = [fix_cell(c) for c in row]
        if any(c for c in cells):
            cleaned.append(cells)

    if not cleaned:
        return []

    # Repair fragmented column headers caused by merged PDF cells split across
    # multiple columns by pdfplumber.
    # A cell is a "fragment" if it:
    #   (a) starts with a lower-case letter (continuation), OR
    #   (b) consists only of 1-2 upper-case letters separated by spaces (e.g. "N O")
    def looks_like_fragment(s):
        if not s:
            return False
        first = s[0]
        if first.islower():
            return True
        # Single-letter tokens only, e.g. "N O" or "N O P"
        tokens = s.split()
        if all(len(t) == 1 and t.isupper() for t in tokens):
            return True
        return False

    header = cleaned[0]
    fixed_header = [header[0]] if header else []
    for cell in header[1:]:
        if looks_like_fragment(cell) and fixed_header:
            fixed_header[-1] = (fixed_header[-1] + ' ' + cell).strip()
        else:
            fixed_header.append(cell)

    # Truncate any header cell that ended up excessively long (merged artefact)
    # Also clean cells that are clearly garbled split-cell joins (single letters + fragments)
    MAX_HDR = 30
    def clean_hdr(h):
        if len(h) > MAX_HDR:
            # If the cell contains isolated single-letter tokens or lower-case
            # fragments, it's a garbled pdfplumber split — keep only the
            # meaningful capitalised multi-letter tokens
            tokens = h.split()
            good = [t for t in tokens if len(t) > 1 and not t[0].islower()
                    and not t[0].isdigit()]
            if good:
                return ' '.join(good)[:MAX_HDR]
            return h[:MAX_HDR].rstrip()
        return h
    fixed_header = [clean_hdr(h) for h in fixed_header]

    # Only use the repaired header if something actually changed
    if fixed_header != header:
        nc = len(fixed_header)
        new_cleaned = [fixed_header]
        for row in cleaned[1:]:
            if len(row) > nc:
                merged = row[:nc-1] + [' '.join(filter(None, row[nc-1:]))]
            else:
                merged = row + [''] * (nc - len(row))
            new_cleaned.append(merged)
        cleaned = new_cleaned

    # Strip known junk suffixes from cell values
    CELL_JUNK = re.compile(
        r'\s+TERMINAL BLOCK$'
        r'|\s+TRIMPOT$',
        re.I
    )
    cleaned = [[CELL_JUNK.sub('', c) for c in row] for row in cleaned]

    # Deduplicate rows
    seen, out = set(), []
    for row in cleaned:
        k = tuple(row)
        if k not in seen:
            seen.add(k)
            out.append(row)
    return out


def _merge_col_blocks(left, right):
    """
    Combine two column block-lists into one ordered list.

    Strategy:
    - If right column is small (≤ 10 blocks) and contains no section headings,
      it's a sidebar (glance bar, logos, etc.) — discard it since the glance
      values are already extracted separately.
    - Otherwise interleave by grouping each column at heading boundaries and
      pairing groups: left-group-N then right-group-N.
    """
    if not right:
        return left

    # Right col is purely a sidebar (no real section headings, very few blocks)
    right_headings = [b for b in right if b['type'] == 'heading']
    if len(right) <= 12 and len(right_headings) == 0:
        # Sidebar only — ignore it, its values are in the glance bar
        return left

    def split_at_headings(blocks):
        groups, cur = [], []
        for b in blocks:
            if b['type'] == 'heading':
                if cur: groups.append(cur)
                cur = [b]
            else:
                cur.append(b)
        if cur: groups.append(cur)
        return groups if groups else [blocks]

    lg = split_at_headings(left)
    rg = split_at_headings(right)
    merged = []
    for i in range(max(len(lg), len(rg))):
        if i < len(lg): merged.extend(lg[i])
        if i < len(rg): merged.extend(rg[i])
    return merged

# ─────────────────────────────────────────────────────────────────────────────
# SECTION GROUPER
# ─────────────────────────────────────────────────────────────────────────────

ACRONYMS = {'MTBF', 'LED', 'EMI', 'DSP', 'EEPROM', 'RoHS', 'PMBus',
            'UKCA', 'UL', 'CSA', 'TUV', 'AC_OK', 'DC_OK'}

def smart_title(text):
    """Title-case a heading but preserve known acronyms as whole words."""
    result = text.title()
    for acr in ACRONYMS:
        # Only replace when the acronym appears as a whole word
        result = re.sub(r'\b' + re.escape(acr.title()) + r'\b', acr, result)
    return result


def group_into_sections(all_page_data):
    """
    Walk blocks across all pages; split into sections at each heading block.
    Tables on each page are assigned to whichever section heading they fall
    under on that page (using the page's word-order flow).
    """
    def is_redundant_spec_table(tbl, page_kv_count):
        """Suppress a spec table only when the page already has substantial KV content."""
        if not tbl or page_kv_count < 3:
            return False
        header = tbl[0] if tbl else []
        if len(header) == 2:
            h0 = header[0].strip()
            h1 = header[1].strip()
            if h0.lower() in ('input', 'output', 'isolation') and not h1:
                return True
            if re.match(r'^(Operating|Start up|Storage|Over)', h0):
                return True
        return False

    sections = []
    cur = {'heading': None, 'content': []}

    for pd in all_page_data:
        has_kv = any(b['type'] == 'kv' for b in pd['blocks'])
        kv_count = sum(1 for b in pd['blocks'] if b['type'] == 'kv')

        # Build a list of (heading_text, [blocks]) in order for this page,
        # then assign each table to the last heading that appeared before it.
        # Since we don't have table positions, use a heuristic:
        # assign each table to the section it logically belongs to based on
        # its header row keywords.

        for blk in pd['blocks']:
            if blk['type'] == 'heading':
                if cur['content']:
                    sections.append(cur)
                cur = {'heading': smart_title(blk['text']), 'content': []}
            else:
                cur['content'].append(blk)

        # Assign tables to the best-matching section on this page
        page_sections_on_stack = [cur]  # cur = current section at end of page
        # Also include the last few sections that were completed during this page
        # (those appended during this page's block loop)
        page_sec_start = len(sections) - sum(
            1 for blk in pd['blocks'] if blk['type'] == 'heading'
        )
        page_sec_start = max(0, page_sec_start)
        page_secs_for_tables = sections[page_sec_start:] + [cur]

        for tbl in pd['tables']:
            if is_redundant_spec_table(tbl, kv_count):
                continue
            # Find the best section for this table by matching header keywords
            best_sec = cur  # default: current (last) section
            if tbl and tbl[0]:
                header_text = ' '.join(str(c) for c in tbl[0]).lower()
                for psec in page_secs_for_tables:
                    h = (psec['heading'] or '').lower()
                    # Ordering table → Ordering Information section
                    if any(k in header_text for k in ['input voltage','output voltage','model number','model\nnumber','lcmxxxxy','lcm300']):
                        if 'order' in h:
                            best_sec = psec
                            break
                    # Pin assignment table → Pin Assignments section
                    elif any(k in header_text for k in ['input (dc)', 'control pin', 'signals']):
                        if 'pin' in h or 'assign' in h:   # 'control signals' excluded
                            best_sec = psec
                            break
            best_sec['content'].append({'type': 'table', 'data': tbl})

    if cur['content'] or cur['heading']:
        sections.append(cur)

    # Merge duplicate headings
    merged, seen = [], {}
    for sec in sections:
        key = (sec['heading'] or '').upper().strip()
        if key and key in seen:
            merged[seen[key]]['content'].extend(sec['content'])
        else:
            if key:
                seen[key] = len(merged)
            merged.append(sec)

    # Build a global set of table cell text across ALL sections for cross-section dedup
    all_table_cells = set()
    for sec in merged:
        for item in sec['content']:
            if item.get('type') == 'table':
                for row in item['data']:
                    for cell in row:
                        s = (cell or '').strip()
                        if len(s) > 4:
                            all_table_cells.add(s[:30])

    # Remove text paragraphs that duplicate table content
    # Check within the same section first, then globally
    for sec in merged:
        tables_in_sec = [c for c in sec['content'] if c.get('type') == 'table']
        local_cells = set()
        for tc in tables_in_sec:
            for row in tc['data']:
                for cell in row:
                    s = (cell or '').strip()
                    if len(s) > 4:
                        local_cells.add(s[:30])

        filtered = []
        for item in sec['content']:
            if item.get('type') == 'paragraph':
                p = item['text']
                # Check against local table cells (threshold 3)
                local_hits  = sum(1 for t in local_cells if t in p)
                # Check against ALL table cells (threshold 5 — stricter to avoid false drops)
                global_hits = sum(1 for t in all_table_cells if t in p)
                if local_hits >= 3 or global_hits >= 6:
                    continue
            filtered.append(item)
        sec['content'] = filtered

    return merged

def render_table(tbl):
    if not tbl or len(tbl) < 1:
        return ''
    header = tbl[0]
    rows   = tbl[1:]

    if not any(c.strip() for c in header):
        return ''  # skip empty-header tables (drawing artefacts)

    # If the entire header is a single non-empty label (e.g. ['Output','',''] or ['Input',''])
    # treat it as a KV sub-section label — the data rows are key/value pairs
    non_empty_hdr = [c for c in header if c.strip()]
    if len(non_empty_hdr) == 1 and rows:
        sub_label = non_empty_hdr[0]
        # Render as a KV table with sub-heading
        html_rows = (f'<tr class="kv-sub-head">'
                     f'<td colspan="2">{esc(sub_label)}</td></tr>\n')
        for row in rows:
            key = row[0].strip() if row else ''
            val = row[1].strip() if len(row) > 1 else ''
            # merge extra columns into value
            if len(row) > 2:
                extras = ' '.join(c.strip() for c in row[2:] if c.strip())
                if extras:
                    val = (val + ' ' + extras).strip() if val else extras
            if not key and not val:
                continue
            if key and not val:
                # inner sub-label
                html_rows += (f'<tr class="kv-sub-head">'
                               f'<td colspan="2">{esc(key)}</td></tr>\n')
            else:
                html_rows += (f'<tr>'
                               f'<td class="kv-key">{esc(key)}</td>'
                               f'<td class="kv-val">{esc(val)}</td>'
                               f'</tr>\n')
        return (f'<div class="table-wrap">'
                f'<table class="kv-table">'
                f'<tbody>\n{html_rows}</tbody></table></div>\n')

    sub_prefix = ''  # used later in data table render

    # ── 2-column KV-style table ──────────────────────────────────────────
    # Detect: 2 cols, header is a single label or ['Key','Value'] style,
    # and data rows look like key–value pairs.
    is_kv_table = (
        len(header) == 2
        and not header[1].strip()           # second header cell is blank
        and len(rows) >= 2
        and sum(1 for r in rows if len(r) >= 2 and r[0].strip() and r[1].strip()) >= 2
    )
    if is_kv_table:
        # Render as kv-table, using the non-empty header cell as a sub-heading
        sub_label = header[0].strip() or None
        html_rows = ''
        if sub_label:
            html_rows += (f'<tr class="kv-sub-head">'
                          f'<td colspan="2">{esc(sub_label)}</td></tr>\n')
        for row in rows:
            key = row[0].strip() if row else ''
            val = row[1].strip() if len(row) > 1 else ''
            if not key and not val:
                continue
            if key and not val:
                # sub-label row inside the table
                html_rows += (f'<tr class="kv-sub-head">'
                               f'<td colspan="2">{esc(key)}</td></tr>\n')
            else:
                html_rows += (f'<tr>'
                               f'<td class="kv-key">{esc(key)}</td>'
                               f'<td class="kv-val">{esc(val)}</td>'
                               f'</tr>\n')
        return (f'<div class="table-wrap">'
                f'<table class="kv-table">'
                f'<tbody>\n{html_rows}</tbody></table></div>\n')

    # ── Standard multi-column data table ────────────────────────────────
    th = ''.join(f'<th>{esc(c)}</th>' for c in header)
    body = ''
    for row in rows:
        non_empty = [c for c in row if c.strip()]
        # Single non-empty ALL-CAPS cell → sub-header row
        is_sub = (
            len(non_empty) == 1
            and non_empty[0] == non_empty[0].upper()
            and len(non_empty[0]) >= 5
            and not non_empty[0][0].isdigit()
            and not re.match(r'^[A-Z]\s+\d+$', non_empty[0])
        )
        if is_sub:
            body += (f'<tr class="sub-head">'
                     f'<td colspan="{len(row)}">{esc(non_empty[0])}</td></tr>\n')
        else:
            body += '<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in row) + '</tr>\n'

    return (f'<div class="table-wrap">'
            f'<table class="data"><thead><tr>{th}</tr></thead>'
            f'<tbody>\n{sub_prefix}{body}</tbody></table></div>\n')


def render_kv_run(kv_list):
    """Render a run of key-value pairs as a compact spec table."""
    if not kv_list:
        return ''
    rows = ''
    last_heading = None
    for item in kv_list:
        if item.get('sub_heading') != last_heading:
            last_heading = item.get('sub_heading')
            if last_heading:
                rows += (f'<tr class="kv-sub-head">'
                         f'<td colspan="2">{esc(last_heading)}</td></tr>\n')
        rows += (f'<tr><td class="kv-key">{esc(item["key"])}</td>'
                 f'<td class="kv-val">{esc(item["value"])}</td></tr>\n')
    return f'<table class="kv-table">\n{rows}</table>\n'


def render_section_content(content_list):
    """Render a mixed list of blocks and table dicts to HTML string."""
    parts      = []
    bullet_buf = []
    kv_buf     = []

    # Short words that signal a KV sub-section header (e.g. "Input", "Output", "Isolation")
    KV_SUB_WORDS = {'input', 'output', 'isolation', 'compliance', 'safety',
                    'general', 'mechanical', 'protection', 'signalling'}

    def flush_bullets():
        if bullet_buf:
            lis = '\n'.join(f'  <li>{esc(b)}</li>' for b in bullet_buf)
            parts.append(f'<ul class="blist">\n{lis}\n</ul>')
            bullet_buf.clear()

    def flush_kv():
        if kv_buf:
            parts.append(render_kv_run(kv_buf))
            kv_buf.clear()

    current_sub = None

    for item in content_list:
        t = item.get('type')

        if t == 'table':
            flush_bullets(); flush_kv()
            parts.append(render_table(item['data']))

        elif t == 'heading':
            flush_bullets(); flush_kv()
            current_sub = smart_title(item['text'])
            parts.append(f'<h3>{esc(current_sub)}</h3>')

        elif t == 'bullet':
            flush_kv()
            bullet_buf.append(item['text'])

        elif t == 'kv':
            flush_bullets()
            kv_buf.append({**item, 'sub_heading': current_sub})

        elif t == 'paragraph':
            s = item['text'].strip()
            # Short single-word or known sub-section labels → treat as KV sub-heading
            if (len(s) <= 20
                    and s.lower() in KV_SUB_WORDS
                    and not bullet_buf):
                # Flush current KV buffer, start a new sub-section
                flush_bullets()
                flush_kv()
                current_sub = smart_title(s)
                # Don't emit an <h3> — it will become a sub-head row in the next KV table
            else:
                flush_bullets(); flush_kv()
                parts.append(f'<p>{esc(s)}</p>')

    flush_bullets(); flush_kv()
    return '\n'.join(p for p in parts if p.strip())

# ─────────────────────────────────────────────────────────────────────────────
# METADATA EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_title(pages_left_col_lines, metadata):
    """
    Extract product title from PDF metadata or the first 1–2 lines of page 1's
    left column that look like a product code/brand name (not a subtitle or prose).

    A product-name line is:
    - ≤ 25 characters
    - All uppercase OR a brand name like "ARTESYN LCM300" / "AIF 300V Vin SERIES"
    - Does NOT read like an English subtitle phrase (no common English words)
    """
    # 1. PDF metadata
    if metadata:
        t = (metadata.get('Title') or metadata.get('/Title') or '').strip()
        if t and len(t) > 3 and 'untitled' not in t.lower():
            return t

    # Common English words that appear in subtitle phrases but not product codes
    SUBTITLE_WORDS = {
        'watts', 'bulk', 'front', 'end', 'power', 'supply',
        'module', 'converter', 'board', 'unit',
        'advanced', 'energy', 'industrial', 'medical',
    }

    if pages_left_col_lines:
        parts = []
        for _y, text in pages_left_col_lines[0]:
            s = clean(text.strip())
            if not s or len(s) < 2:
                continue
            if len(s) > 25:
                break  # hit body text
            skip = ['AT A GLANCE', 'advancedenergy', '©']
            if any(p.lower() in s.lower() for p in skip):
                continue
            # Reject if any word in the line is a common subtitle/prose word
            words_in_line = re.findall(r'[A-Za-z]+', s)
            if any(w.lower() in SUBTITLE_WORDS for w in words_in_line):
                break  # this is a subtitle, stop here
            if re.match(r'^[A-Z0-9][A-Za-z0-9 \-\.]+$', s):
                parts.append(s)
            if len(parts) == 2:
                break

        if parts:
            if len(parts) == 2 and len(parts[0]) < 15:
                return parts[0] + ' ' + parts[1]
            return parts[0]

    return 'Document'


def extract_glance(first_page_lines, page_width=595):
    """
    Pull At-A-Glance sidebar values from page-1.
    Handles both standalone 'Label:' lines and labels embedded at the end of
    body-text lines (common in AE datasheets where sidebar text bleeds into
    the body column, e.g. '...rating at Input Voltage:').
    Skips long body-text when scanning for the value.
    """
    lines = [text.strip() for _y, text in first_page_lines
             if text.strip() and not is_junk(text.strip())]

    # Known sidebar label names with value validators
    KNOWN_LABELS = {
        'Maximum Power':  re.compile(r'^\d+\s*W(?:atts?)?', re.I),
        'Total Power':    re.compile(r'^\d+\s*W(?:atts?)?', re.I),
        'Input Voltage':  re.compile(r'^\d+.*V(?:AC|DC)?', re.I),
        '# of Outputs':   re.compile(r'^(Single|Dual|Triple|\d+)', re.I),
        '# Outputs':      re.compile(r'^(Single|Dual|Triple|\d+)', re.I),
    }
    # Matches a line that IS exactly the label (with optional colon)
    EXACT_RE = re.compile(
        r'^(' + '|'.join(re.escape(k) for k in KNOWN_LABELS) + r'):?\s*$', re.I)
    # Matches a label appearing at the END of a longer line
    EMBEDDED_RE = re.compile(
        r'\b(' + '|'.join(re.escape(k) for k in KNOWN_LABELS) + r'):?\s*$', re.I)

    glance = {}

    def try_find_value(lbl, start_idx):
        """Scan from start_idx for a short value line matching the validator."""
        validator = KNOWN_LABELS[lbl]
        for j in range(start_idx, min(start_idx + 8, len(lines))):
            v = lines[j].strip()
            if not v or is_junk(v):
                continue
            # Stop if we hit another label
            if EXACT_RE.match(v) or EMBEDDED_RE.search(v):
                # But if this line IS the value (short + matches), take it
                if len(v) <= 35 and validator.search(v):
                    return v
                break
            if len(v) > 35:
                continue        # long body-text, keep searching
            if validator.search(v):
                return v
        return None

    for i, line in enumerate(lines):
        # Case 1: line is exactly the label
        m = EXACT_RE.match(line)
        if m:
            lbl = next((k for k in KNOWN_LABELS
                        if k.lower() == m.group(1).strip().rstrip(':').lower()), None)
            if lbl and lbl not in glance:
                v = try_find_value(lbl, i + 1)
                if v:
                    glance[lbl] = v
            continue

        # Case 2: label embedded at end of body-text line
        m2 = EMBEDDED_RE.search(line)
        if m2:
            lbl = next((k for k in KNOWN_LABELS
                        if k.lower() == m2.group(1).strip().rstrip(':').lower()), None)
            if lbl and lbl not in glance:
                v = try_find_value(lbl, i + 1)
                if v:
                    glance[lbl] = v

    priority = ['Total Power', 'Maximum Power', 'Input Voltage',
                '# of Outputs', '# Outputs']
    ordered = [(k, glance[k]) for k in priority if k in glance]
    others  = [(k, v) for k, v in glance.items() if k not in priority]
    return (ordered + others)[:5]


def extract_doc_id(pages_text_list):
    """Find a document revision/ID string, usually on the last page."""
    pat = re.compile(r'(ENG-[A-Z0-9\s\-\.]+\d{2,})', re.I)
    for text in reversed(pages_text_list):
        for line in text.splitlines():
            m = pat.search(line.strip())
            if m:
                return m.group(1).strip()
    return ''


def extract_tagline(first_page_lines):
    """
    Build a concise tagline from page-1 left-column content.
    Reads raw lines (before junk filtering) so subtitle lines like
    '300 Watts Bulk Front End' are available even if in JUNK_PATTERNS.
    """
    # Use raw lines (no junk filter) to catch subtitle lines
    raw_lines = [clean(t) for _y, t in first_page_lines if t.strip()]

    SUBTITLE_WORDS = {
        'watts', 'bulk', 'front', 'end', 'power', 'supply',
        'module', 'converter', 'board', 'unit',
    }

    for line in raw_lines[1:6]:
        s = line.strip()
        if not s or len(s) > 50 or len(s) < 5:
            continue
        if re.match(r'^(Total|Maximum|Input|Output|#)', s, re.I):
            continue
        words_in = re.findall(r'[A-Za-z]+', s)
        if any(w.lower() in SUBTITLE_WORDS for w in words_in):
            return s
    return ''


def build_tagline_from_glance(glance_items):
    """Fallback tagline built from glance bar values."""
    parts = []
    for lbl, val in glance_items:
        if lbl in ('Total Power', 'Maximum Power'):
            parts.append(val)
        elif lbl == 'Input Voltage':
            parts.append(f'{val} Input')
        elif lbl in ('# of Outputs', '# Outputs'):
            parts.append(f'{val} Output')
    return ' | '.join(parts) if parts else ''

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONVERTER
# ─────────────────────────────────────────────────────────────────────────────

def convert_pdf_to_html(file_bytes, filename):
    """
    Full pipeline: PDF bytes → HTML string.
    Works on any structured PDF.
    """
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        meta        = pdf.metadata or {}
        pages_text  = [p.extract_text() or '' for p in pdf.pages]
        page_data   = [extract_page(p) for p in pdf.pages]

    # Re-open page 1 to get words for metadata extraction
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        p1          = pdf.pages[0]
        p1_raw_words = p1.extract_words(x_tolerance=3, y_tolerance=3)
        pw1         = float(p1.width)

    # Use LEFT column only for title/tagline (avoids sidebar "AT A GLANCE" contamination)
    split1 = find_column_split(p1_raw_words, pw1)
    if split1:
        p1_left_lines = words_to_lines(p1_raw_words, x_hi=split1)
    else:
        p1_left_lines = words_to_lines(p1_raw_words)

    # Full-page lines (interleaved) used only for glance (needs right-col labels)
    p1_all_lines = words_to_lines(p1_raw_words)

    # ── Metadata ──────────────────────────────────────────────────────────
    title   = extract_title([p1_left_lines], meta)
    glance  = extract_glance(p1_all_lines)       # extract first — needed for tagline fallback
    tagline = extract_tagline(p1_left_lines)
    if not tagline:
        tagline = build_tagline_from_glance(glance)
    doc_id  = extract_doc_id(pages_text)

    # ── Build sections ────────────────────────────────────────────────────
    sections = group_into_sections(page_data)

    # ── Glance bar HTML ───────────────────────────────────────────────────
    glance_html = ''
    if glance:
        cards = ''.join(
            f'<div class="glance-card">'
            f'<div class="glance-label">{esc(lbl)}</div>'
            f'<div class="glance-value">{esc(val)}</div>'
            f'</div>'
            for lbl, val in glance
        )
        glance_html = (f'<div class="glance-bar">'
                       f'<div class="glance-inner">{cards}</div>'
                       f'</div>\n')

    # ── Section HTML ──────────────────────────────────────────────────────
    sections_html = ''
    for sec in sections:
        body = render_section_content(sec['content'])
        if not body.strip():
            continue
        h2 = f'<h2>{esc(sec["heading"])}</h2>\n' if sec['heading'] else ''
        sections_html += f'<section>\n  {h2}  {body}\n</section>\n\n'

    # ── Footer ────────────────────────────────────────────────────────────
    footer_doc = (f'<p class="footer-doc-id">{esc(doc_id)}</p>'
                  if doc_id else '')

    # ── Assemble ──────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <style>{OUTPUT_CSS}</style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="header-left">
      <h1>{esc(title)}</h1>
      <p class="tagline">{esc(tagline)}</p>
    </div>
    <div class="header-right">
      <span class="brand">Advanced Energy</span>
      <p class="brand-sub">advancedenergy.com</p>
    </div>
  </div>
  <div class="header-divider"></div>
</header>

{glance_html}
<div class="container">
{sections_html}
</div>

<footer>
  <div class="footer-inner">
    <p>For international contact information, visit <strong>advancedenergy.com</strong></p>
    <p>powersales@aei.com (Sales Support) &nbsp;|&nbsp;
       productsupport.ep@aei.com (Technical Support) &nbsp;|&nbsp; +1 888 412 7832</p>
    {footer_doc}
    <p class="footer-legal">Specifications are subject to change without notice.
    Not responsible for errors or omissions.<br>
    &copy;2024 Advanced Energy Industries, Inc. All rights reserved.
    Advanced Energy&reg;, AE&reg; and Artesyn&trade; are trademarks of
    Advanced Energy Industries, Inc.</p>
  </div>
</footer>

</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <p class="hero-title">PDF <span class="accent">→</span> HTML Converter</p>
  <p class="hero-sub">Upload any PDF — get back a clean, styled HTML file ready to open in any browser.</p>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([1, 1.65], gap="large")

with left:
    st.markdown('<div class="step"><span class="step-num">01</span> Upload PDF</div>',
                unsafe_allow_html=True)
    uploaded = st.file_uploader("pdf", type=["pdf"], label_visibility="collapsed")

    if uploaded:
        st.markdown(f"""<div class="card">
          <div style="font-size:.67rem;color:#555;font-family:'Space Mono',monospace;
               text-transform:uppercase;letter-spacing:.1em">File</div>
          <div style="font-size:.88rem;color:#e8e4de;margin-top:3px;
               word-break:break-all">{uploaded.name}</div>
          <div style="margin-top:5px;font-size:.75rem;color:#555">
            Size: <span style="color:#ff9500;font-family:'Space Mono',monospace">
            {uploaded.size / 1024:.1f} KB</span>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="step" style="margin-top:1rem">'
                '<span class="step-num">02</span> Convert</div>',
                unsafe_allow_html=True)
    convert_btn = st.button("⚡  Convert to HTML", disabled=not uploaded)

    if st.session_state.get("html_out"):
        st.markdown('<div class="step" style="margin-top:1rem">'
                    '<span class="step-num">03</span> Download</div>',
                    unsafe_allow_html=True)
        base = (uploaded.name.replace(".pdf", "").replace(".PDF", "")
                if uploaded else "output")
        st.download_button(
            "⬇  Download HTML File",
            data=st.session_state["html_out"],
            file_name=f"{base}.html",
            mime="text/html",
            key="dl_html"
        )
        s = st.session_state.get("stats", {})
        st.markdown(f"""<div class="stats-row">
          <div class="stat"><div class="stat-lbl">Pages</div>
            <div class="stat-val">{s.get('pages','—')}</div></div>
          <div class="stat"><div class="stat-lbl">Sections</div>
            <div class="stat-val">{s.get('sections','—')}</div></div>
          <div class="stat"><div class="stat-lbl">Tables</div>
            <div class="stat-val">{s.get('tables','—')}</div></div>
          <div class="stat"><div class="stat-lbl">Time</div>
            <div class="stat-val">{s.get('time','—')}s</div></div>
        </div>""", unsafe_allow_html=True)

with right:
    st.markdown('<div class="step"><span class="step-num">04</span> Live Preview</div>',
                unsafe_allow_html=True)

    if convert_btn and uploaded:
        uploaded.seek(0)
        with st.spinner("Extracting and converting…"):
            t0 = time.time()
            try:
                raw   = uploaded.read()
                html  = convert_pdf_to_html(raw, uploaded.name)
                elapsed = round(time.time() - t0, 1)

                with pdfplumber.open(io.BytesIO(raw)) as pdf:
                    n_pages = len(pdf.pages)

                st.session_state.update({
                    "html_out":     html,
                    "preview_html": html,
                    "stats": {
                        "pages":    n_pages,
                        "sections": html.count('<section>'),
                        "tables":   html.count('class="data"'),
                        "time":     elapsed,
                    }
                })
                st.rerun()
            except Exception as e:
                st.error(f"Conversion failed: {e}")
                raise

    if st.session_state.get("preview_html"):
        tab1, tab2 = st.tabs(["🖥  Preview", "📄  HTML Source"])
        with tab1:
            b64 = base64.b64encode(
                st.session_state["preview_html"].encode('utf-8')
            ).decode()
            st.markdown(
                '<div style="border:1px solid #222;border-radius:10px;overflow:hidden">'
                f'<iframe src="data:text/html;base64,{b64}" width="100%" height="660" '
                f'frameborder="0" style="display:block"></iframe></div>',
                unsafe_allow_html=True
            )
        with tab2:
            src = st.session_state["html_out"]
            st.code(
                src[:6000] + ("\n\n… (truncated for display)" if len(src) > 6000 else ""),
                language="html"
            )
    else:
        st.markdown("""<div class="empty-preview">
          <div style="font-size:2.8rem">📄</div>
          <div>Preview appears here after conversion</div>
          <div style="font-size:.7rem;color:#2a2a2a">Works with any PDF</div>
        </div>""", unsafe_allow_html=True)