"""Web Scraper のテストサイト（AJAX版）から商品の一覧を取得する処理。

このサイトは、ページ番号のボタンを押すとJavaScriptで商品が入れ替わる（URLは変わらない）。
requests では「ボタンを押す」ことができないので、Playwright で本物のブラウザを動かす。
"""

import logging
from urllib.parse import urljoin

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page, sync_playwright

logger = logging.getLogger(__name__)

START_URL = "https://webscraper.io/test-sites/e-commerce/ajax/computers/laptops"

# サーバーに負担をかけないよう、ページごとに待つ秒数
WAIT_SECONDS = 1.0

# ページを開く・ページを切り替えるときに試す回数（1回目を含む）
MAX_ATTEMPTS = 3

# 1つの操作を待つ上限（ミリ秒）。Playwright の初期値の30秒は、失敗に気づくまでが長すぎる
TIMEOUT_MS = 15_000


class ScrapeError(Exception):
    """ページを開けない・切り替えられないなど、続けられないときのエラー。"""


class ParseError(Exception):
    """商品カードから必要な項目を取り出せなかったときのエラー。"""


def _text(card: Locator, selector: str) -> str:
    """要素の文字を取り出す。見つからなければ ParseError にする。

    Playwright は要素が現れるまで待つので、ないかもしれない要素は
    先に count() で確かめる（count() は待たずにすぐ数を返す）。
    """
    element = card.locator(selector)
    if element.count() == 0:
        raise ParseError(f"「{selector}」が見つかりません")
    return element.first.inner_text().strip()


def parse_product(card: Locator, page_url: str) -> dict:
    """商品1つ分のカードから項目を取り出す。"""
    link = card.locator("a.title")
    if link.count() == 0:
        raise ParseError("商品名のリンクが見つかりません")
    name = link.get_attribute("title")
    href = link.get_attribute("href")
    if not name or not href:
        raise ParseError("商品名またはリンク先が空です")

    price_text = _text(card, ".price")
    reviews_text = _text(card, "[itemprop=reviewCount]")
    try:
        price = float(price_text.lstrip("$").replace(",", ""))
        reviews = int(reviews_text)
    except ValueError as e:
        raise ParseError(
            f"数値にできません: 価格={price_text!r} レビュー数={reviews_text!r}"
        ) from e

    return {
        # 画面の文字は途中で切れていることがあるので、title 属性から取る
        "name": name,
        "price": price,
        "description": _text(card, ".description"),
        # 評価は星のアイコンの数で表されている
        "rating": card.locator(".ratings .ws-icon-star").count(),
        "reviews": reviews,
        "url": urljoin(page_url, href),
    }


def parse_current_page(page: Page, number: int) -> list[dict]:
    """今表示されているページの商品をすべて取り出す。取り出せない商品は飛ばす。"""
    products = []
    for i, card in enumerate(page.locator(".thumbnail").all(), start=1):
        try:
            products.append(parse_product(card, page.url))
        except ParseError as e:
            logger.warning("%dページ目の %d件目を飛ばしました: %s", number, i, e)
    return products


def count_pages(page: Page) -> int:
    """ページ番号のボタンの数から、全部で何ページあるかを調べる。

    1ページしかないときはボタン自体が出ないので、最低1ページとする。
    """
    return max(1, page.locator(".pagination button.page").count())


def open_start_page(page: Page, url: str) -> None:
    """最初のページを開き、商品が表示されるまで待つ。失敗したらやり直す。"""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            page.goto(url)
            # 商品が表示されるまで待つ（JavaScriptで描画されるため）
            page.locator(".thumbnail").first.wait_for()
            return
        except PlaywrightError as e:
            if attempt == MAX_ATTEMPTS:
                raise ScrapeError(
                    f"{url} を開けませんでした: {e.message.splitlines()[0]}"
                ) from e
            wait = 2**attempt
            logger.warning(
                "ページを開けませんでした（%d/%d回目）。%d秒後にやり直します",
                attempt,
                MAX_ATTEMPTS,
                wait,
            )
            page.wait_for_timeout(wait * 1000)


def go_to_page(page: Page, number: int) -> None:
    """ページ番号のボタンを押し、商品が入れ替わるまで待つ。失敗したらやり直す。

    ボタンを押した直後は、まだ前のページの商品が表示されている。
    すぐに読み取ると前のページを二重に取ってしまうので、
    「先頭の商品のリンクが変わった」ことを確認してから次に進む。
    """
    first_href = page.locator(".thumbnail a.title").first.get_attribute("href")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            page.locator(f'.pagination button.page[data-id="{number}"]').click()
            page.wait_for_function(
                "href => document.querySelector('.thumbnail a.title')"
                "?.getAttribute('href') !== href",
                arg=first_href,
            )
            return
        except PlaywrightError as e:
            if attempt == MAX_ATTEMPTS:
                raise ScrapeError(
                    f"{number}ページ目に切り替えられませんでした: {e.message.splitlines()[0]}"
                ) from e
            logger.warning(
                "%dページ目に切り替えられませんでした（%d/%d回目）。やり直します",
                number,
                attempt,
                MAX_ATTEMPTS,
            )


def scrape_all(
    start_url: str = START_URL,
    max_pages: int | None = None,
    headless: bool = True,
) -> list[dict]:
    """ページ番号のボタンを順に押して、全ページの商品を集める。

    途中でページを開けなくなったり、Ctrl+C で止めたりした場合は、
    そこまでに集めた分を返す（何も残らない、ということを避ける）。
    max_pages を指定すると、そのページ数で止める（動作確認用）。
    headless=False にすると、ブラウザの画面を表示して動きを見られる。
    """
    all_products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            page.set_default_timeout(TIMEOUT_MS)
            open_start_page(page, start_url)

            total = count_pages(page)
            if max_pages:
                total = min(total, max_pages)

            for number in range(1, total + 1):
                if number > 1:
                    page.wait_for_timeout(WAIT_SECONDS * 1000)  # サーバーへの配慮
                    go_to_page(page, number)
                products = parse_current_page(page, number)
                all_products.extend(products)
                logger.info(
                    "%d/%dページ目: %d件（累計 %d件）",
                    number,
                    total,
                    len(products),
                    len(all_products),
                )
        except ScrapeError as e:
            logger.error("%s。ここまでの %d件で終了します", e, len(all_products))
        except KeyboardInterrupt:
            logger.warning(
                "中断しました。ここまでの %d件を保存します", len(all_products)
            )
        finally:
            browser.close()

    return all_products
