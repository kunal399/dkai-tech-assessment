# PDF → HTML Converter

Converts Advanced Energy (and any structured) product datasheet PDFs into
clean, styled, semantic HTML files.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Then open http://localhost:8501, upload a PDF and click **Convert to HTML**.

## How it works

1. **pdfplumber** extracts words with x/y coordinates from each page
2. A column-split algorithm detects two-column layouts automatically
3. Table bounding boxes mask table regions so text isn't double-extracted
4. Lines are classified as: section heading | bullet | key-value spec | paragraph
5. Tables are routed to the correct section by header-keyword matching
6. Everything is rendered into semantic HTML (`<section>`, `<h2>`, `<ul>`, `<table>`)
   with embedded CSS that visually matches the original PDF layout

## Tested on

- AIF 300V Vin Series (5-page DC-DC converter datasheet)
- LCM300 (8-page AC-DC power supply datasheet)
