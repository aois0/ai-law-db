#!/usr/bin/env python3
"""
tax_typeとissueの改善版抽出スクリプト

tax_type:
- topicsから取得
- lawsから推測
- original_caseから継承
- 残りは「（税目情報なし）」

issue:
- 複数パターンに対応
  - 「主な争点」→「（１）（２）」形式
  - 「争点」→「１ ２ ３」形式（全角/半角両方）
  - インライン争点形式
"""

import os
import re
import json
from bs4 import BeautifulSoup


def extract_text_from_html(html_path):
    """HTMLからテキスト抽出"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    soup = BeautifulSoup(content, 'html.parser')
    body = soup.find('body')
    if body:
        return body.get_text(separator='\n')
    return soup.get_text(separator='\n')


# 法律から税目を推測
LAW_TO_TAX = {
    '所得税法': '所得税',
    '法人税法': '法人税',
    '消費税法': '消費税',
    '相続税法': '相続税',
    '贈与税法': '贈与税',
    '印紙税法': '印紙税',
    '酒税法': '酒税',
    '登録免許税法': '登録免許税',
    '地方税法': '地方税',
    '所得税法施行令': '所得税',
    '法人税法施行令': '法人税',
    '消費税法施行令': '消費税',
    '相続税法施行令': '相続税',
    '租税特別措置法': '租税特別措置法',
    '財産評価基本通達': '相続税',
    '所得税基本通達': '所得税',
    '法人税基本通達': '法人税',
    '消費税法基本通達': '消費税',
}


def infer_tax_from_laws(laws):
    """lawsから税目を推測"""
    taxes = set()
    for law in laws:
        # 特殊マーカーはスキップ
        if law.startswith('（'):
            continue
        for law_name, tax in LAW_TO_TAX.items():
            if law_name in law:
                taxes.add(tax)
    return list(taxes)


def infer_tax_from_title(title):
    """タイトルから税目を推測"""
    taxes = set()
    tax_keywords = [
        ('所得税', '所得税'),
        ('法人税', '法人税'),
        ('消費税', '消費税'),
        ('相続税', '相続税'),
        ('贈与税', '贈与税'),
        ('印紙税', '印紙税'),
        ('酒税', '酒税'),
        ('登録免許税', '登録免許税'),
        ('源泉所得税', '所得税'),
        ('源泉徴収', '所得税'),
    ]
    for keyword, tax in tax_keywords:
        if keyword in title:
            taxes.add(tax)
    return list(taxes)


def infer_tax_from_html(html_path):
    """HTMLから税目を推測"""
    if not os.path.exists(html_path):
        return []

    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()

    taxes = set()
    # 明示的な税法言及を探す（処分や更正の文脈で）
    patterns = [
        (r'所得税.{0,5}(?:更正|処分|課税)', '所得税'),
        (r'法人税.{0,5}(?:更正|処分|課税)', '法人税'),
        (r'消費税.{0,5}(?:更正|処分|課税)', '消費税'),
        (r'相続税.{0,5}(?:更正|処分|課税)', '相続税'),
        (r'贈与税.{0,5}(?:更正|処分|課税)', '贈与税'),
        (r'印紙税.{0,5}(?:更正|処分|課税)', '印紙税'),
        (r'酒税.{0,5}(?:更正|処分|課税)', '酒税'),
    ]

    for pattern, tax in patterns:
        if re.search(pattern, text):
            taxes.add(tax)

    return list(taxes)


def extract_issues(text):
    """争点を抽出（複数パターン対応）"""
    issues = []

    # スペースを正規化
    text_norm = re.sub(r'[ 　]+', ' ', text)
    text_nospace = re.sub(r'\s+', '', text)

    # パターン1: 「主な争点」セクション → 「（１）（２）」形式
    patterns_section = [
        r'(?:主な)?争点\s*[^\n]*\n(.*?)(?:主な争点に関する当事者|当事者の主張|第[３4４]|[４4]\s)',
        r'[３3]\s*(?:主な)?争点\s*[^\n]*\n?(.*?)(?:[４4]\s|第[３3])',
    ]

    for pattern in patterns_section:
        match = re.search(pattern, text_norm, re.DOTALL)
        if match:
            section = match.group(1)

            # （１）（２）形式を抽出
            issue_matches = re.findall(
                r'[（\(][０-９0-9一二三四五六七八九十]+[）\)]\s*([^（\(\n]{5,150})',
                section
            )
            for m in issue_matches:
                issue_text = re.sub(r'\s+', '', m.strip())
                if issue_text and len(issue_text) >= 5:
                    issues.append(issue_text)

            if issues:
                break

    # パターン2: 「争点及びこれに関する当事者の主張」→「１ ２ ３」形式
    if not issues:
        patterns_numbered = [
            r'争点(?:及び[^\n]*)?(?:主張|の主張)[^\n]*\n(.*?)(?:第[３4４]|当裁判所の判断)',
        ]

        for pattern in patterns_numbered:
            match = re.search(pattern, text_norm, re.DOTALL)
            if match:
                section = match.group(1)

                # １ ２ ３形式を抽出（全角/半角両方）
                issue_matches = re.findall(
                    r'(?:^|\n)\s*[１２３４５６７８９0-9]+\s+([^\n（]{10,150})',
                    section
                )
                for m in issue_matches:
                    issue_text = re.sub(r'\s+', '', m.strip())
                    # 「被告の主張」「原告の主張」で始まるものは除外
                    if issue_text and len(issue_text) >= 10 and not re.match(r'^[（\(]?[被原]告の主張', issue_text):
                        issues.append(issue_text)

                if issues:
                    break

    # パターン3: 「争点（１）」または「争点１」インライン形式
    if not issues:
        # 争点１（...）形式
        inline_matches = re.findall(
            r'争点[１２３４５６７８９0-9][（\(]([^）\)]{10,150})[）\)]',
            text_nospace
        )
        for m in inline_matches:
            issue_text = m.strip()
            if issue_text and len(issue_text) >= 10:
                issues.append(issue_text)

        # 争点（１）形式
        if not issues:
            inline_matches = re.findall(
                r'争点[（\(][０-９0-9一二三四五六七八九]+[）\)][^\n]{0,30}?([^）\)]{10,100})',
                text_nospace
            )
            for m in inline_matches:
                issue_text = m.strip()
                if issue_text and len(issue_text) >= 10:
                    issues.append(issue_text)

    # パターン4: 「争点は、〇〇である」形式
    if not issues:
        simple_match = re.search(
            r'(?:本件の)?(?:主な)?争点は[、,]?\s*([^。]{10,200})(?:である|か否か)',
            text_norm
        )
        if simple_match:
            issue_text = re.sub(r'\s+', '', simple_match.group(1).strip())
            if issue_text:
                issues.append(issue_text)

    # パターン5: 「争点本件〇〇」形式（争点の直後に内容）
    if not issues:
        direct_match = re.search(
            r'争点\s*本件([^（\(。]{10,150})',
            text_norm
        )
        if direct_match:
            issue_text = '本件' + re.sub(r'\s+', '', direct_match.group(1).strip())
            if issue_text:
                issues.append(issue_text)

    # パターン6: 「争点本件...（具体的には、...か否か）」形式
    if not issues:
        specific_match = re.search(
            r'争点\s*本件[^（]*[（\(]具体的には[、,]?\s*([^）\)]{10,200})[）\)]',
            text_norm
        )
        if specific_match:
            issue_text = re.sub(r'\s+', '', specific_match.group(1).strip())
            if issue_text:
                issues.append(issue_text)

    # パターン7: 「本件の争点は、〇〇である」形式
    if not issues:
        is_match = re.search(
            r'本件の?争点は[、,]?\s*([^。]{10,200})(?:である|か否か|とされる)',
            text_norm
        )
        if is_match:
            issue_text = re.sub(r'\s+', '', is_match.group(1).strip())
            if issue_text:
                issues.append(issue_text)

    # パターン8: 原判決引用の場合
    if not issues:
        if '原判決' in text_nospace and '引用' in text_nospace:
            # より緩いパターン: 争点...原判決...引用、または原判決...争点...引用
            citation_patterns = [
                r'争点[^。]{0,100}原判決[^。]{0,50}引用',
                r'原判決[^。]{0,50}争点[^。]{0,100}引用',
                r'争点[^。]{0,50}引用',
            ]
            for pattern in citation_patterns:
                if re.search(pattern, text_nospace):
                    issues.append('（原判決引用）')
                    break

    # パターン9: 上告受理申立却下/上告棄却の場合
    if not issues:
        dismissal_patterns = [
            r'本件を上告審として受理しない',
            r'民訴法３１８条１項により受理すべきものとは認められない',
            r'本件上告を棄却する',
        ]
        for pattern in dismissal_patterns:
            if re.search(pattern, text_nospace):
                issues.append('（上告受理申立却下）')
                break

    # パターン10: 控訴審原判決引用（より広いパターン）
    if not issues:
        broader_citation_patterns = [
            r'当事者の主張は[^。]*原判決[^。]*引用',
            r'前提事実[^。]*原判決[^。]*引用',
            r'事実及び理由[^。]*原判決[^。]*引用',
            r'原判決[^。]*のとおり[^。]*引用',
        ]
        for pattern in broader_citation_patterns:
            if re.search(pattern, text_nospace):
                issues.append('（原判決引用）')
                break

    # パターン11: 訴訟要件事案
    if not issues:
        if re.search(r'訴訟要件に関する|訴えの適法性|訴えの利益', text_nospace):
            issues.append('（訴訟要件）')

    # パターン12: 「本件は、」事案説明形式
    if not issues:
        case_desc_match = re.search(
            r'本件は[、,]\s*([^。]{20,200}?)(?:として|ものとして|旨)[^。]*?(?:事案|求める)',
            text_norm
        )
        if case_desc_match:
            issue_text = re.sub(r'\s+', '', case_desc_match.group(1).strip())
            if len(issue_text) >= 15:
                issues.append(issue_text[:100])

    # 重複除去
    seen = set()
    unique_issues = []
    for i in issues:
        # 正規化して比較
        normalized = re.sub(r'\s+', '', i)
        if normalized not in seen and len(normalized) >= 5:
            seen.add(normalized)
            unique_issues.append(i)

    return unique_issues[:10]  # 最大10件


def main():
    html_dir = '/home/user/ai-law-db/simple/hanketsu'
    index_path = os.path.join(html_dir, 'index.json')

    # index.json読み込み
    with open(index_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    print(f'処理対象: {len(cases)}件')

    # ケースを辞書化（original_case参照用）
    cases_dict = {c['number']: c for c in cases}

    stats = {
        'tax_from_topics': 0,
        'tax_from_laws': 0,
        'tax_from_title': 0,
        'tax_from_html': 0,
        'tax_from_original': 0,
        'tax_unknown': 0,
        'issue_extracted': 0,
        'issue_empty': 0,
        'total_issues': 0,
    }

    for i, case in enumerate(cases, 1):
        number = case['number']
        html_path = os.path.join(html_dir, f'{number}.html')
        title = case.get('title', '')

        # === tax_type処理 ===
        tax_type = []

        # 1. topicsから
        if case.get('topics'):
            tax_type = list(case['topics'])
            stats['tax_from_topics'] += 1

        # 2. lawsから推測
        if not tax_type and case.get('laws'):
            tax_type = infer_tax_from_laws(case['laws'])
            if tax_type:
                stats['tax_from_laws'] += 1

        # 3. タイトルから推測
        if not tax_type:
            tax_type = infer_tax_from_title(title)
            if tax_type:
                stats['tax_from_title'] += 1

        # 4. HTMLから推測
        if not tax_type:
            tax_type = infer_tax_from_html(html_path)
            if tax_type:
                stats['tax_from_html'] += 1

        # 5. original_caseから継承
        if not tax_type and case.get('original_case'):
            orig_num = case['original_case']
            if orig_num in cases_dict:
                orig_tax = cases_dict[orig_num].get('tax_type', [])
                if orig_tax:
                    tax_type = list(orig_tax)
                    stats['tax_from_original'] += 1

        # 6. それでも不明な場合
        if not tax_type:
            tax_type = ['（税目情報なし）']
            stats['tax_unknown'] += 1

        case['tax_type'] = tax_type

        # === issue処理 ===
        if os.path.exists(html_path):
            try:
                text = extract_text_from_html(html_path)
                issues = extract_issues(text)
                case['issue'] = issues
                if issues:
                    stats['issue_extracted'] += 1
                    stats['total_issues'] += len(issues)
                else:
                    stats['issue_empty'] += 1
            except Exception as e:
                print(f'{number}: エラー - {e}')
                case['issue'] = []
                stats['issue_empty'] += 1
        else:
            case['issue'] = []
            stats['issue_empty'] += 1

        if i % 500 == 0:
            print(f'[{i}/{len(cases)}] 処理中...')

    # 保存
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    # 統計
    print(f'\n=== 完了 ===')
    print(f'\n--- tax_type ---')
    print(f'topicsから: {stats["tax_from_topics"]}件')
    print(f'lawsから推測: {stats["tax_from_laws"]}件')
    print(f'タイトルから推測: {stats["tax_from_title"]}件')
    print(f'HTMLから推測: {stats["tax_from_html"]}件')
    print(f'original_caseから継承: {stats["tax_from_original"]}件')
    print(f'不明: {stats["tax_unknown"]}件')

    total_with_tax = len(cases) - stats['tax_unknown']
    print(f'\ntax_type有効: {total_with_tax}/{len(cases)} ({100*total_with_tax/len(cases):.1f}%)')

    print(f'\n--- issue ---')
    print(f'抽出成功: {stats["issue_extracted"]}件')
    print(f'空: {stats["issue_empty"]}件')
    print(f'総争点数: {stats["total_issues"]}件')
    if stats['issue_extracted']:
        print(f'平均争点数: {stats["total_issues"]/stats["issue_extracted"]:.1f}件/判決')

    print(f'\nissue有効: {stats["issue_extracted"]}/{len(cases)} ({100*stats["issue_extracted"]/len(cases):.1f}%)')


if __name__ == '__main__':
    main()
