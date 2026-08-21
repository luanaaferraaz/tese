#!/usr/bin/env python3
"""Build a print-friendly Excel with the summary tables for the email."""
from pathlib import Path
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

OUT = Path(__file__).resolve().parent / "resumo_resultados.xlsx"

HEADER_FILL = PatternFill("solid", fgColor="4472C4")
TITLE_FILL  = PatternFill("solid", fgColor="2F5496")
GREEN       = PatternFill("solid", fgColor="C6EFCE")
YELLOW      = PatternFill("solid", fgColor="FFEB9C")
RED         = PatternFill("solid", fgColor="FFC7CE")
GREY        = PatternFill("solid", fgColor="D9D9D9")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT  = Font(bold=True, color="FFFFFF", size=13)
BOLD        = Font(bold=True, size=11)
NORMAL      = Font(size=11)
CENTER      = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT        = Alignment(horizontal="left", vertical="center", wrap_text=True)
THIN        = Side(style="thin", color="BFBFBF")
BORDER      = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def pct_fill(v):
    """Colour a false-positive/accuracy percentage cell (higher fp = worse)."""
    if v >= 30:
        return RED
    if v >= 10:
        return YELLOW
    return GREEN


wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Resumo"
ws.sheet_view.showGridLines = False

r = 1
# ── Title ──
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
c = ws.cell(r, 1, "Resultados por modelo (727 testes válidos)")
c.fill = TITLE_FILL; c.font = TITLE_FONT; c.alignment = CENTER
r += 1
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
c = ws.cell(r, 1, "Sem DeepSeek (0 válidos) e sem Claude (agente indisponível na iaedu)")
c.font = Font(italic=True, size=9, color="666666"); c.alignment = LEFT
r += 2

# ── Table 1: per model ──
model_hdr = ["Modelo", "Testes válidos", "Accuracy (corretos)", "Deteção (com erro)"]
for j, h in enumerate(model_hdr, 1):
    c = ws.cell(r, j, h); c.fill = HEADER_FILL; c.font = HEADER_FONT
    c.alignment = CENTER; c.border = BORDER
r += 1

model_rows = [
    ("GPT-5.5",            167, "38% (41/107)",  "100% (60/60)"),
    ("LLaMA-3.3-70B",      280, "91% (164/180)", "80% (80/100)"),
    ("Qwen-2.5-Coder-7B",  280, "77% (139/180)", "90% (90/100)"),
]
for name, n, acc, det in model_rows:
    ws.cell(r, 1, name).font = BOLD
    ws.cell(r, 2, n).font = NORMAL
    ws.cell(r, 3, acc).font = NORMAL
    ws.cell(r, 4, det).font = NORMAL
    for j in range(1, 5):
        cell = ws.cell(r, j)
        cell.alignment = CENTER if j > 1 else LEFT
        cell.border = BORDER
    r += 1
r += 2

# ── Table 2 title ──
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
c = ws.cell(r, 1, "Falsos positivos por propriedade (algoritmos corretos)")
c.fill = TITLE_FILL; c.font = TITLE_FONT; c.alignment = CENTER
r += 1
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
c = ws.cell(r, 1, "% de vezes que o modelo marcou ERRADAMENTE a propriedade como violada (menor = melhor)")
c.font = Font(italic=True, size=9, color="666666"); c.alignment = LEFT
r += 2

prop_hdr = ["Propriedade", "GPT-5.5", "LLaMA-70B", "Qwen-7B"]
for j, h in enumerate(prop_hdr, 1):
    c = ws.cell(r, j, h); c.fill = HEADER_FILL; c.font = HEADER_FONT
    c.alignment = CENTER; c.border = BORDER
r += 1

# (label, gpt%, gpt_frac, llama%, llama_frac, qwen%, qwen_frac)
prop_rows = [
    ("Validity",          43, "46/107", 0,  "0/180",  5,  "9/180"),
    ("Integrity",         50, "24/48",  0,  "0/80",   5,  "4/80"),
    ("Agreement",         40, "34/84",  4,  "6/140",  16, "23/139"),
    ("Uniform Agreement", 36, "4/11",   25, "5/20",   0,  "0/20"),
    ("No creation",       22, "13/59",  5,  "5/100",  5,  "5/100"),
    ("No duplication",    0,  "0/59",   0,  "0/100",  10, "10/100"),
]
for label, g, gf, l, lf, q, qf in prop_rows:
    ws.cell(r, 1, label).font = BOLD
    ws.cell(r, 1).alignment = LEFT; ws.cell(r, 1).border = BORDER
    for j, (v, frac) in enumerate([(g, gf), (l, lf), (q, qf)], start=2):
        cell = ws.cell(r, j, f"{v}% ({frac})")
        cell.font = NORMAL; cell.alignment = CENTER; cell.border = BORDER
        cell.fill = pct_fill(v)
    r += 1

# ── column widths ──
ws.column_dimensions["A"].width = 22
ws.column_dimensions["B"].width = 18
ws.column_dimensions["C"].width = 20
ws.column_dimensions["D"].width = 20

wb.save(OUT)
print(f"Saved {OUT}")
