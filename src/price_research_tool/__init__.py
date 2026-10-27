import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

from price_research_tool.exporter import save_excel
from price_research_tool.scraper import START_URL, scrape_all

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通販サイトの商品一覧を集めて、書式つきのExcelに保存します。"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="保存先のExcelファイル（省略時は output/prices_日時.xlsx）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="取得するページ数の上限（動作確認用。省略時は全ページ）",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="ブラウザの画面を表示して、動きを見ながら実行する",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    output = (
        args.output or Path("output") / f"prices_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    )

    try:
        products = scrape_all(max_pages=args.max_pages, headless=not args.show_browser)
    except PlaywrightError as e:
        # ブラウザ本体が入っていない、など起動そのものの失敗
        logger.error("ブラウザを起動できませんでした: %s", e.message.splitlines()[0])
        if "Executable doesn't exist" in e.message:
            logger.error("先に `uv run playwright install chromium` を実行してください")
        sys.exit(1)

    if not products:
        logger.error("1件も取得できなかったため、Excelは作成しません")
        sys.exit(1)

    try:
        save_excel(products, output, START_URL)
    except OSError as e:
        # 保存先に書き込めない、同じ名前のファイルをExcelで開いたまま、など
        logger.error("Excelを保存できませんでした: %s", e)
        sys.exit(1)

    logger.info("合計 %d件を %s に保存しました", len(products), output)
