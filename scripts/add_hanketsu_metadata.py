#!/usr/bin/env python3
"""
判決HTMLにメタデータ（税目・争点・条文）を追加
"""

import os
import re
import json
from bs4 import BeautifulSoup


# 税目のパターン
TAX_TYPES = {
    '所得税': ['所得税', '源泉所得税', '源泉徴収', '復興特別所得税'],
    '法人税': ['法人税'],
    '消費税': ['消費税', '地方消費税'],
    '相続税': ['相続税'],
    '贈与税': ['贈与税'],
    '印紙税': ['印紙税', '過怠税'],
    '登録免許税': ['登録免許税'],
    '酒税': ['酒税'],
    '国税徴収': ['国税徴収', '滞納処分', '差押'],
}

# 主要な条文パターン
LAW_PATTERNS = [
    # 所得税法
    (r'所得税法[第]*(\d+)[条の\d]*', '所得税法'),
    (r'所法[第]*(\d+)', '所得税法'),
    # 法人税法
    (r'法人税法[第]*(\d+)[条の\d]*', '法人税法'),
    (r'法法[第]*(\d+)', '法人税法'),
    # 消費税法
    (r'消費税法[第]*(\d+)[条の\d]*', '消費税法'),
    # 相続税法
    (r'相続税法[第]*(\d+)[条の\d]*', '相続税法'),
    (r'相法[第]*(\d+)', '相続税法'),
    # 国税通則法
    (r'国税通則法[第]*(\d+)[条の\d]*', '国税通則法'),
    (r'通則法[第]*(\d+)', '国税通則法'),
    # 租税特別措置法
    (r'租税特別措置法[第]*(\d+)[条の\d]*', '措置法'),
    (r'措置法[第]*(\d+)', '措置法'),
    # 国税徴収法
    (r'国税徴収法[第]*(\d+)[条の\d]*', '国税徴収法'),
    # 印紙税法
    (r'印紙税法[第]*(\d+)[条の\d]*', '印紙税法'),
]

# 争点キーワード
ISSUE_KEYWORDS = [
    # 手続き関連
    ('更正の請求', '更正請求の可否'),
    ('修正申告.*無効', '修正申告の有効性'),
    ('処分.*取消', '課税処分の適法性'),
    ('加算税', '加算税の適法性'),
    ('延滞税', '延滞税の適法性'),
    # 所得税関連
    ('配当所得', '配当所得該当性'),
    ('給与所得', '給与所得該当性'),
    ('事業所得', '事業所得該当性'),
    ('譲渡所得', '譲渡所得該当性'),
    ('一時所得', '一時所得該当性'),
    ('雑所得', '雑所得該当性'),
    ('必要経費', '必要経費の範囲'),
    ('損益通算', '損益通算'),
    # 法人税関連
    ('寄附金', '寄附金該当性'),
    ('交際費', '交際費該当性'),
    ('役員報酬', '役員報酬の損金算入'),
    ('移転価格', '移転価格税制'),
    ('同族会社', '同族会社の行為計算否認'),
    ('貸倒損失', '貸倒損失の損金算入'),
    ('減価償却', '減価償却'),
    # 消費税関連
    ('仕入税額控除', '仕入税額控除'),
    ('課税売上', '課税売上該当性'),
    ('非課税', '非課税取引該当性'),
    ('輸出免税', '輸出免税'),
    # 相続税関連
    ('財産評価', '財産評価'),
    ('路線価', '路線価評価'),
    ('小規模宅地', '小規模宅地等の特例'),
    ('相続財産', '相続財産の範囲'),
    ('名義預金', '名義財産'),
    # 一般
    ('信義則', '信義則違反'),
    ('実質課税', '実質課税の原則'),
    ('租税回避', '租税回避行為'),
    ('仮装隠蔽', '仮装隠蔽行為'),
    ('重加算税', '重加算税の適法性'),
    ('不当利得', '不当利得返還請求'),
    ('国家賠償', '国家賠償請求'),
]


def extract_text_from_html(html_content: str) -> str:
    """HTMLからテキストを抽出"""
    soup = BeautifulSoup(html_content, 'html.parser')
    # body内のテキストを取得
    body = soup.find('body')
    if body:
        return body.get_text(separator=' ')
    return soup.get_text(separator=' ')


def detect_tax_types(text: str, title: str) -> list:
    """税目を検出"""
    found = set()

    # タイトルから優先的に検出
    for tax_name, keywords in TAX_TYPES.items():
        for kw in keywords:
            if kw in title:
                found.add(tax_name)
                break

    # 本文からも検出（タイトルで見つからない場合）
    if not found:
        for tax_name, keywords in TAX_TYPES.items():
            for kw in keywords:
                if kw in text:
                    found.add(tax_name)
                    break

    return sorted(list(found))


def extract_legal_provisions(text: str) -> list:
    """条文を抽出"""
    provisions = set()

    for pattern, law_name in LAW_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches[:5]:  # 各法律から最大5条まで
            if isinstance(match, tuple):
                match = match[0]
            provisions.add(f'{law_name}{match}条')

    return sorted(list(provisions))[:10]  # 最大10条文


def detect_issues(text: str, title: str) -> list:
    """争点を検出"""
    found = []
    combined = title + ' ' + text[:5000]  # 冒頭5000文字で判定

    for keyword, issue_name in ISSUE_KEYWORDS:
        if re.search(keyword, combined):
            if issue_name not in found:
                found.append(issue_name)
                if len(found) >= 3:  # 最大3つ
                    break

    return found


def update_html_with_metadata(html_path: str, metadata: dict) -> str:
    """HTMLにメタデータを追加"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')

    # 既存のメタタグを削除
    for meta in soup.find_all('meta', attrs={'name': ['tax-type', 'issues', 'provisions']}):
        meta.decompose()

    head = soup.find('head')
    if head:
        # 新しいメタタグを追加
        if metadata.get('tax_types'):
            meta_tax = soup.new_tag('meta', attrs={
                'name': 'tax-type',
                'content': ','.join(metadata['tax_types'])
            })
            head.append(meta_tax)

        if metadata.get('issues'):
            meta_issues = soup.new_tag('meta', attrs={
                'name': 'issues',
                'content': ','.join(metadata['issues'])
            })
            head.append(meta_issues)

        if metadata.get('provisions'):
            meta_prov = soup.new_tag('meta', attrs={
                'name': 'provisions',
                'content': ','.join(metadata['provisions'])
            })
            head.append(meta_prov)

    # メタデータ表示部分を更新
    meta_div = soup.find('div', class_='meta')
    if meta_div:
        # 既存の追加メタデータを削除
        for p in meta_div.find_all('p'):
            if any(x in p.get_text() for x in ['税目:', '争点:', '条文:']):
                p.decompose()

        # 新しいメタデータを追加
        if metadata.get('tax_types'):
            p = soup.new_tag('p')
            strong = soup.new_tag('strong')
            strong.string = '税目:'
            p.append(strong)
            p.append(f' {", ".join(metadata["tax_types"])}')
            meta_div.append(p)

        if metadata.get('issues'):
            p = soup.new_tag('p')
            strong = soup.new_tag('strong')
            strong.string = '争点:'
            p.append(strong)
            p.append(f' {", ".join(metadata["issues"])}')
            meta_div.append(p)

        if metadata.get('provisions'):
            p = soup.new_tag('p')
            strong = soup.new_tag('strong')
            strong.string = '条文:'
            p.append(strong)
            p.append(f' {", ".join(metadata["provisions"])}')
            meta_div.append(p)

    return str(soup)


def main():
    html_dir = '/home/user/ai-law-db/simple/hanketsu/2023'

    # 既存のindex.jsonを読み込み
    with open(os.path.join(html_dir, 'index.json'), 'r', encoding='utf-8') as f:
        cases = json.load(f)

    # 番号でマッピング
    case_map = {c['number']: c for c in cases}

    # HTMLファイルを処理
    html_files = [f for f in os.listdir(html_dir) if f.endswith('.html') and f != 'index.html']

    print(f'処理対象: {len(html_files)}件')

    for i, filename in enumerate(sorted(html_files), 1):
        number = filename.replace('.html', '')
        html_path = os.path.join(html_dir, filename)

        print(f'[{i}/{len(html_files)}] {number}...', end=' ')

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            text = extract_text_from_html(html_content)
            title = case_map.get(number, {}).get('title', '')

            # メタデータ抽出
            metadata = {
                'tax_types': detect_tax_types(text, title),
                'issues': detect_issues(text, title),
                'provisions': extract_legal_provisions(text)
            }

            # HTMLを更新
            updated_html = update_html_with_metadata(html_path, metadata)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(updated_html)

            # index.jsonのエントリを更新
            if number in case_map:
                case_map[number]['tax_types'] = metadata['tax_types']
                case_map[number]['issues'] = metadata['issues']
                case_map[number]['provisions'] = metadata['provisions']

            print(f'税目:{metadata["tax_types"]} 争点:{len(metadata["issues"])}件')

        except Exception as e:
            print(f'エラー: {e}')

    # index.jsonを更新
    updated_cases = [case_map[c['number']] for c in cases if c['number'] in case_map]
    with open(os.path.join(html_dir, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(updated_cases, f, ensure_ascii=False, indent=2)

    print(f'\nindex.json 更新完了')

    # 統計
    tax_stats = {}
    for case in updated_cases:
        for tax in case.get('tax_types', []):
            tax_stats[tax] = tax_stats.get(tax, 0) + 1

    print('\n税目別統計:')
    for tax, count in sorted(tax_stats.items(), key=lambda x: -x[1]):
        print(f'  {tax}: {count}件')


if __name__ == '__main__':
    main()
