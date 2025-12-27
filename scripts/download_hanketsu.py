#!/usr/bin/env python3
"""
国税庁判決事例PDFダウンロードスクリプト
"""

import urllib.request
import urllib.parse
import os
import re
import time
import json
from html.parser import HTMLParser


class NTAIndexParser(HTMLParser):
    """国税庁インデックスページのパーサー"""

    def __init__(self):
        super().__init__()
        self.cases = []
        self.in_table = False
        self.in_td = False
        self.in_link = False
        self.current_case = {}
        self.current_href = None
        self.td_count = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'table':
            self.in_table = True
        elif tag == 'tr' and self.in_table:
            self.current_case = {}
            self.td_count = 0
        elif tag == 'td' and self.in_table:
            self.in_td = True
            self.td_count += 1
        elif tag == 'a' and self.in_td:
            href = attrs_dict.get('href', '')
            if '.pdf' in href.lower():
                self.in_link = True
                self.current_href = href

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag == 'td':
            self.in_td = False
        elif tag == 'a':
            self.in_link = False
        elif tag == 'tr' and self.current_case.get('number'):
            self.cases.append(self.current_case.copy())

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        if self.in_link and self.current_href:
            # PDFリンクのテキストから判決番号を抽出
            match = re.search(r'(\d+)', data)
            if match:
                self.current_case['number'] = match.group(1)
                self.current_case['pdf_url'] = self.current_href
        elif self.in_td and self.td_count == 2:
            # 2列目はタイトル
            if 'title' not in self.current_case:
                self.current_case['title'] = data
            else:
                self.current_case['title'] += ' ' + data


def fetch_page(url: str) -> str:
    """ページを取得"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        # エンコーディングを取得
        content_type = response.headers.get('Content-Type', '')
        if 'charset=' in content_type:
            encoding = content_type.split('charset=')[-1].strip()
        else:
            encoding = 'utf-8'

        content = response.read()

        # shift_jisで試す
        try:
            return content.decode('shift_jis')
        except:
            try:
                return content.decode('utf-8')
            except:
                return content.decode('latin-1')


def parse_index(html_content: str) -> list:
    """インデックスページをパース"""
    parser = NTAIndexParser()
    parser.feed(html_content)
    return parser.cases


def download_pdf(url: str, output_path: str) -> bool:
    """PDFをダウンロード"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(output_path, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"  エラー: {e}")
        return False


def main():
    import sys

    # デフォルト設定
    year = '2023'
    base_url = f'https://www.nta.go.jp/about/organization/ntc/soshoshiryo/kazei/{year}/index.htm'
    output_dir = f'/home/user/ai-law-db/data/hanketsu/{year}/pdf'
    limit = None  # None = 全件、数値 = 制限

    # コマンドライン引数
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"ダウンロード数制限: {limit}件")
        except:
            pass

    # 出力ディレクトリ作成
    os.makedirs(output_dir, exist_ok=True)

    print(f"インデックスページ取得中: {base_url}")
    html_content = fetch_page(base_url)

    print("パース中...")
    cases = parse_index(html_content)

    print(f"判決数: {len(cases)}件")

    if not cases:
        print("判決が見つかりませんでした")
        # HTMLをデバッグ用に保存
        with open(f'/home/user/ai-law-db/data/hanketsu/{year}/index_debug.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("デバッグ用HTMLを保存しました")
        return

    # メタデータ保存
    metadata_path = f'/home/user/ai-law-db/data/hanketsu/{year}/metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f"メタデータ保存: {metadata_path}")

    # ダウンロード
    if limit:
        cases = cases[:limit]

    success = 0
    for i, case in enumerate(cases, 1):
        number = case.get('number', 'unknown')
        pdf_url = case.get('pdf_url', '')

        if not pdf_url:
            continue

        # 相対URLを絶対URLに変換
        if pdf_url.startswith('/'):
            pdf_url = 'https://www.nta.go.jp' + pdf_url
        elif not pdf_url.startswith('http'):
            pdf_url = f'https://www.nta.go.jp/about/organization/ntc/soshoshiryo/kazei/{year}/' + pdf_url

        output_path = os.path.join(output_dir, f'{number}.pdf')

        if os.path.exists(output_path):
            print(f"[{i}/{len(cases)}] {number}.pdf - スキップ（既存）")
            success += 1
            continue

        print(f"[{i}/{len(cases)}] ダウンロード中: {number}.pdf")
        if download_pdf(pdf_url, output_path):
            success += 1
            time.sleep(0.5)  # 負荷軽減
        else:
            print(f"  失敗: {pdf_url}")

    print(f"\n完了: {success}/{len(cases)}件")


if __name__ == '__main__':
    main()
