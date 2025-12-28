#!/usr/bin/env python3
"""
税目(tax_type)と争点(issue)をindex.jsonに追加
- tax_type: topicsからコピー
- issue: HTMLから争点セクションを抽出
"""

import os
import re
import json
from bs4 import BeautifulSoup

# 数字変換（全角→半角）
ZENKAKU_MAP = str.maketrans('０１２３４５６７８９', '0123456789')


def extract_text_from_html(html_path):
    """HTMLからテキスト抽出"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    soup = BeautifulSoup(content, 'html.parser')
    body = soup.find('body')
    if body:
        return body.get_text(separator='\n')
    return soup.get_text(separator='\n')


def extract_issues(text):
    """争点を抽出"""
    issues = []

    # スペースを正規化
    text_norm = re.sub(r'[ 　]+', ' ', text)

    # 争点セクションを探す
    issue_section = None

    # パターン1: 「主な争点」または「争点」セクション
    patterns = [
        r'(?:主な)?争点\s*(.*?)(?:当事者の主張|第３|４\s*主な争点に関する)',
        r'３\s*(?:主な)?争点\s*(.*?)(?:４|第３)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text_norm, re.DOTALL)
        if match:
            issue_section = match.group(1)
            break

    if not issue_section:
        return issues

    # （１）、（２）形式の争点を抽出
    # または (1)、(2) 形式
    issue_patterns = [
        r'（[０-９0-9一二三四五六七八九十]+）\s*([^（\n]{5,100})',
        r'\([0-9]+\)\s*([^\(\n]{5,100})',
    ]

    for pattern in issue_patterns:
        matches = re.findall(pattern, issue_section)
        for m in matches:
            issue_text = m.strip()
            # 「について」や「該当性」などで終わる争点を整形
            issue_text = re.sub(r'\s+', '', issue_text)
            if issue_text and len(issue_text) >= 5:
                issues.append(issue_text)

    # 重複除去
    seen = set()
    unique_issues = []
    for i in issues:
        if i not in seen:
            seen.add(i)
            unique_issues.append(i)

    return unique_issues


def main():
    html_dir = '/home/user/ai-law-db/simple/hanketsu'
    index_path = os.path.join(html_dir, 'index.json')

    # index.json読み込み
    with open(index_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    print(f'処理対象: {len(cases)}件')

    stats = {
        'tax_type_added': 0,
        'issue_added': 0,
        'total_issues': 0,
    }

    for i, case in enumerate(cases, 1):
        number = case['number']
        html_path = os.path.join(html_dir, f'{number}.html')

        # tax_type: topicsからコピー
        if 'topics' in case and case['topics']:
            case['tax_type'] = case['topics']
            stats['tax_type_added'] += 1
        else:
            case['tax_type'] = []

        # issue: HTMLから抽出
        if os.path.exists(html_path):
            try:
                text = extract_text_from_html(html_path)
                issues = extract_issues(text)
                case['issue'] = issues
                if issues:
                    stats['issue_added'] += 1
                    stats['total_issues'] += len(issues)
            except Exception as e:
                print(f'{number}: エラー - {e}')
                case['issue'] = []
        else:
            case['issue'] = []

        if i % 500 == 0:
            print(f'[{i}/{len(cases)}] 処理中...')

    # 保存
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    # 統計
    print(f'\n=== 完了 ===')
    print(f'tax_type追加: {stats["tax_type_added"]}件')
    print(f'issue追加: {stats["issue_added"]}件')
    print(f'総争点数: {stats["total_issues"]}件')
    print(f'平均争点数: {stats["total_issues"]/stats["issue_added"]:.1f}件/判決' if stats['issue_added'] else '')


if __name__ == '__main__':
    main()
