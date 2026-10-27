# price-research-tool

通販サイトの商品一覧を**ブラウザを自動操作して**最後のページまで巡回し、価格を**書式つきのExcel**にまとめるPythonツールです。

練習用サイト [Web Scraper Test Sites（AJAX版）](https://webscraper.io/test-sites/e-commerce/ajax/computers/laptops) のノートパソコン一覧を対象に、全20ページ・117件を約30秒で集めます。

このサイトは、ページ番号のボタンを押すとJavaScriptで商品が入れ替わり、**URLが変わりません**。HTMLをダウンロードするだけの方法ではページを切り替えられないため、[Playwright](https://playwright.dev/python/) で実際のブラウザ（Chromium）を動かしてボタンを押しています。

## できること

- **ボタン操作で全ページを巡回**：ページ番号のボタンを順に押し、商品が入れ替わったことを確かめてから読み取ります（前のページを二重に取らない）
- **書式つきのExcelに出力**
  - 「商品一覧」シート：見出しの色・固定、絞り込みボタン、列幅、価格の色分け（安い＝緑／高い＝赤）、レビュー数の棒グラフ、商品ページへのリンク
  - 「集計」シート：商品数・平均価格・最安値・最高値、価格帯ごとの商品数と割合
- **途中で止まりにくい**
  - ページが開けない・切り替わらないときは、最大3回までやり直します
  - 項目が欠けている商品があっても全体は止めず、その商品だけ飛ばしてログに残します
  - 途中で続けられなくなったり Ctrl+C で止めたりしても、それまでに集めた分は保存します
- **相手のサーバーに配慮**：ページを切り替えるたびに1秒待ちます

## 出力例

[examples/sample.xlsx](examples/sample.xlsx)

**商品一覧シート**（先頭の5件）

| 商品名 | 価格（ドル） | 評価（1〜5） | レビュー数 | 説明 | 商品ページ |
|---|---|---|---|---|---|
| Asus VivoBook X441NA-GA190 | $295.99 | 5 | 1 | Asus VivoBook X441NA-GA190 Chocolate Black, 14", … | 開く |
| Prestigio SmartBook 133S Dark Grey | $299.00 | 5 | 9 | Prestigio SmartBook 133S Dark Grey, 13.3" FHD IPS, … | 開く |
| Prestigio SmartBook 133S Gold | $299.00 | 5 | 9 | Prestigio SmartBook 133S Gold, 13.3" FHD IPS, … | 開く |
| Aspire E1-510 | $306.99 | 5 | 2 | 15.6", Pentium N3520 2.16GHz, 4GB, 500GB, Linux | 開く |
| Lenovo V110-15IAP | $321.94 | 5 | 12 | Lenovo V110-15IAP, 15.6" HD, Celeron N3350 1.1GHz, … | 開く |

**集計シート**

| 価格帯 | 商品数 | 割合 | 平均価格 |
|---|---|---|---|
| $500未満 | 38 | 32.5% | $417.45 |
| $500〜$1,000 | 14 | 12.0% | $709.64 |
| $1,000〜$1,500 | 62 | 53.0% | $1,213.94 |
| $1,500以上 | 3 | 2.6% | $1,779.00 |

※ 練習用サイトのAJAX版は、すべての商品に星5つが表示される仕様のため、評価はすべて5になります（同じサイトの通常版では、同じ取り出し方で1〜5の評価を正しく取れます）。

実行中は進み具合が表示されます。

```
18:22:06 [INFO] 1/20ページ目: 6件（累計 6件）
18:22:07 [INFO] 2/20ページ目: 6件（累計 12件）
...
18:22:33 [INFO] 20/20ページ目: 3件（累計 117件）
18:22:33 [INFO] 合計 117件を output/prices_20261027_182206.xlsx に保存しました
```

## 使い方

[uv](https://docs.astral.sh/uv/) が必要です。初回だけ、Playwright用のブラウザを入れます。

```bash
git clone https://github.com/gishi503/price-research-tool.git
cd price-research-tool
uv run playwright install chromium
uv run price-research-tool
```

`output/prices_日時.xlsx` に保存されます。

| オプション | 説明 |
|---|---|
| `-o`, `--output` | 保存先のExcelファイルを指定する |
| `--max-pages` | 取得するページ数の上限（動作確認用） |
| `--show-browser` | ブラウザの画面を表示して、動きを見ながら実行する |

```bash
# ブラウザの動きを見ながら、3ページだけ取得する
uv run price-research-tool --max-pages 3 --show-browser
```

## ファイル構成

```
src/price_research_tool/
├── __init__.py   # 入口（オプションの読み取り、ログ設定、全体の流れ）
├── scraper.py    # ブラウザ操作・ページ切り替え・商品の読み取り、エラー時のやり直し
└── exporter.py   # 書式つきExcelへの保存（一覧シート・集計シート）
```

## 使用技術

- Python 3.14
- Playwright（ブラウザの自動操作）
- openpyxl（Excelの作成・書式設定）
- uv（パッケージ管理）、Ruff（コードのチェック・整形）

## ご依頼について

同じ仕組みで、次のような作業を自動化できます。

- 競合の通販サイトの価格・在庫の定期チェックと、Excelでの報告書づくり
- ボタン操作や「もっと見る」での読み込み、ログインが必要なサイトからの一覧の収集
- 集めたデータの集計（価格帯・カテゴリー別など）と、見やすい書式での出力

APIやページに埋め込まれたデータで取れる場合は、ブラウザを動かすよりも速く壊れにくい方法を選びます。対象サイトの利用規約と robots.txt を確認し、収集が認められている範囲で対応します。
