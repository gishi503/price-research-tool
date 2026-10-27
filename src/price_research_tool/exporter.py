"""集めた商品データを、書式つきのExcelファイルに保存する処理。"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

# 一覧シートの列: (データのキー, 見出し, 列の幅, 数値の表示形式)
COLUMNS = [
    ("name", "商品名", 40, None),
    ("price", "価格（ドル）", 14, "$#,##0.00"),
    ("rating", "評価（1〜5）", 13, "0"),
    ("reviews", "レビュー数", 12, "#,##0"),
    ("description", "説明", 70, None),
    ("url", "商品ページ", 14, None),
]

# 集計シートの価格帯: (表示名, 下限以上, 上限未満)
PRICE_BANDS = [
    ("$500未満", 0, 500),
    ("$500〜$1,000", 500, 1000),
    ("$1,000〜$1,500", 1000, 1500),
    ("$1,500以上", 1500, float("inf")),
]

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", start_color="1F4E78")
TITLE_FONT = Font(bold=True, size=14)
THIN_BORDER = Border(bottom=Side(style="thin", color="BFBFBF"))
LINK_FONT = Font(color="0563C1", underline="single")


def _style_header(ws: Worksheet, row: int, n_cols: int) -> None:
    """見出し行に色をつける。"""
    for col in range(1, n_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_products_sheet(ws: Worksheet, products: list[dict]) -> None:
    """1枚目のシート: 商品の一覧。"""
    ws.title = "商品一覧"
    ws.append([header for _, header, _, _ in COLUMNS])
    _style_header(ws, 1, len(COLUMNS))

    for product in products:
        row = [product[key] for key, _, _, _ in COLUMNS]
        row[-1] = "開く"  # URLはそのまま出すと長いので、リンクの文字にする
        ws.append(row)

        link_cell = ws.cell(row=ws.max_row, column=len(COLUMNS))
        link_cell.hyperlink = product["url"]
        link_cell.font = LINK_FONT

    last_row = ws.max_row
    for i, (_, _, width, number_format) in enumerate(COLUMNS, start=1):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = width
        if number_format:
            for (cell,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                cell.number_format = number_format

    for row in ws.iter_rows(min_row=2, max_row=last_row):
        for cell in row:
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column == 5)

    # 見出しを固定し、絞り込み（フィルター）ボタンをつける
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{last_row}"

    # 価格は 安い=緑 / 高い=赤 の色分け、レビュー数は棒グラフで見やすくする
    ws.conditional_formatting.add(
        f"B2:B{last_row}",
        ColorScaleRule(
            start_type="min", start_color="63BE7B",
            mid_type="percentile", mid_value=50, mid_color="FFEB84",
            end_type="max", end_color="F8696B",
        ),
    )  # fmt: skip
    ws.conditional_formatting.add(
        f"D2:D{last_row}",
        DataBarRule(start_type="min", end_type="max", color="5B9BD5"),
    )


def write_summary_sheet(ws: Worksheet, products: list[dict], source_url: str) -> None:
    """2枚目のシート: 全体の集計と、評価ごとの集計。"""
    ws.title = "集計"
    prices = [p["price"] for p in products]

    ws["A1"] = "価格調査の集計"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"取得日時: {datetime.now():%Y-%m-%d %H:%M}"
    ws["A3"] = f"取得元: {source_url}"

    ws.append([])
    ws.append(["項目", "値"])
    _style_header(ws, ws.max_row, 2)
    for label, value, fmt in [
        ("商品数", len(products), "#,##0"),
        ("平均価格", sum(prices) / len(prices), "$#,##0.00"),
        ("最安値", min(prices), "$#,##0.00"),
        ("最高値", max(prices), "$#,##0.00"),
    ]:
        ws.append([label, value])
        ws.cell(row=ws.max_row, column=2).number_format = fmt

    ws.append([])
    ws.append(["価格帯", "商品数", "割合", "平均価格"])
    _style_header(ws, ws.max_row, 4)
    for label, low, high in PRICE_BANDS:
        band = [price for price in prices if low <= price < high]
        ws.append(
            [
                label,
                len(band),
                len(band) / len(prices),
                sum(band) / len(band) if band else None,
            ]
        )
        ws.cell(row=ws.max_row, column=3).number_format = "0.0%"
        ws.cell(row=ws.max_row, column=4).number_format = "$#,##0.00"

    for letter, width in zip("ABCD", (18, 12, 10, 14)):
        ws.column_dimensions[letter].width = width


def save_excel(products: list[dict], path: Path, source_url: str) -> None:
    """商品の一覧と集計を、1つのExcelファイルに保存する。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    write_products_sheet(wb.active, products)
    write_summary_sheet(wb.create_sheet(), products, source_url)
    wb.save(path)
