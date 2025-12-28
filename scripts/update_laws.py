#!/usr/bin/env python3
"""
index.jsonのlawsフィールドを更新
全角・半角・漢数字に対応した汎用パターンで法律参照を抽出
"""

import os
import re
import json
from bs4 import BeautifulSoup

# 数字変換（全角・漢数字→半角）
ZENKAKU_MAP = str.maketrans('０１２３４５６７８９', '0123456789')
KANJI_MAP = {
    '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
    '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
    '百': '100', '〇': '0'
}

def kanji_to_number(s):
    """漢数字を算用数字に変換"""
    if not s:
        return ''

    # 全角数字→半角
    s = s.translate(ZENKAKU_MAP)

    # 既に数字のみなら返す
    if s.isdigit():
        return s

    # 漢数字変換
    result = 0
    current = 0

    for char in s:
        if char in '一二三四五六七八九':
            current = int(KANJI_MAP.get(char, '0'))
        elif char == '十':
            if current == 0:
                current = 1
            result += current * 10
            current = 0
        elif char == '百':
            if current == 0:
                current = 1
            result += current * 100
            current = 0
        elif char == '〇':
            current = current * 10

    result += current
    return str(result) if result > 0 else s


# 主要法律リスト
LAWS = [
    '所得税法',
    '法人税法',
    '消費税法',
    '相続税法',
    '贈与税法',
    '国税通則法',
    '租税特別措置法',
    '国税徴収法',
    '行政事件訴訟法',
    '印紙税法',
    '地方税法',
    '登録免許税法',
    '酒税法',
    '国税犯則取締法',
    '民法',
    '会社法',
    '民事訴訟法',
    '刑法',
    '憲法',
    '所得税法施行令',
    '法人税法施行令',
    '消費税法施行令',
    '相続税法施行令',
    '租税特別措置法施行令',
    '国税通則法施行令',
    '所得税法施行規則',
    '法人税法施行規則',
    '消費税法施行規則',
    '相続税法施行規則',
    '租税特別措置法施行規則',
    '財産評価基本通達',
    '法人税基本通達',
    '所得税基本通達',
    '消費税法基本通達',
]

# 条文パターン（複数形式に対応）
# [法律名][第]?[数字(半角/全角/漢数字)]+条[の[数字]+]?[第[数字]+項]?
NUM_PATTERN = r'[０-９0-9一二三四五六七八九十百]+'


def infer_main_law_from_title(title):
    """タイトルから主要法律を推測"""
    if '所得税' in title:
        return '所得税法'
    elif '法人税' in title:
        return '法人税法'
    elif '消費税' in title:
        return '消費税法'
    elif '相続税' in title:
        return '相続税法'
    elif '贈与税' in title:
        return '贈与税法'
    return None


def extract_laws_from_text(text, title=''):
    """テキストから法律参照を抽出"""
    found = set()
    main_law = infer_main_law_from_title(title)

    # スペース・改行を除去したバージョンも用意
    text_nospace = re.sub(r'\s+', '', text)
    # 括弧書き（改正履歴等）を除去したバージョン
    text_nobracket = re.sub(r'（[^）]{0,100}）', '', text_nospace)

    for law in LAWS:
        # 1. 括弧なしテキストでシンプルパターン
        pattern = rf'{re.escape(law)}第?({NUM_PATTERN})条(?:の({NUM_PATTERN}))?'
        for match in re.finditer(pattern, text_nobracket):
            article = kanji_to_number(match.group(1))
            sub = match.group(2)
            if sub:
                found.add(f'{law}{article}条の{kanji_to_number(sub)}')
            else:
                found.add(f'{law}{article}条')

        # 2. 元テキスト（スペースなし）でもパターン検索
        for match in re.finditer(pattern, text_nospace):
            article = kanji_to_number(match.group(1))
            sub = match.group(2)
            if sub:
                found.add(f'{law}{article}条の{kanji_to_number(sub)}')
            else:
                found.add(f'{law}{article}条')

    # 略称対応
    abbreviations = [
        (r'所法第?({num})条'.replace('{num}', NUM_PATTERN), '所得税法'),
        (r'法法第?({num})条'.replace('{num}', NUM_PATTERN), '法人税法'),
        (r'消法第?({num})条'.replace('{num}', NUM_PATTERN), '消費税法'),
        (r'相法第?({num})条'.replace('{num}', NUM_PATTERN), '相続税法'),
        (r'通法第?({num})条'.replace('{num}', NUM_PATTERN), '国税通則法'),
        (r'通則法第?({num})条'.replace('{num}', NUM_PATTERN), '国税通則法'),
        (r'措法第?({num})条'.replace('{num}', NUM_PATTERN), '租税特別措置法'),
        (r'措置法第?({num})条'.replace('{num}', NUM_PATTERN), '租税特別措置法'),
        (r'徴法第?({num})条'.replace('{num}', NUM_PATTERN), '国税徴収法'),
        (r'徴収法第?({num})条'.replace('{num}', NUM_PATTERN), '国税徴収法'),
        (r'行訴法第?({num})条'.replace('{num}', NUM_PATTERN), '行政事件訴訟法'),
        (r'民訴法第?({num})条'.replace('{num}', NUM_PATTERN), '民事訴訟法'),
        (r'所令第?({num})条'.replace('{num}', NUM_PATTERN), '所得税法施行令'),
        (r'法令第?({num})条'.replace('{num}', NUM_PATTERN), '法人税法施行令'),
        (r'消令第?({num})条'.replace('{num}', NUM_PATTERN), '消費税法施行令'),
        (r'相令第?({num})条'.replace('{num}', NUM_PATTERN), '相続税法施行令'),
        (r'措令第?({num})条'.replace('{num}', NUM_PATTERN), '租税特別措置法施行令'),
        (r'措置法施行令第?({num})条'.replace('{num}', NUM_PATTERN), '租税特別措置法施行令'),
        (r'所規第?({num})条'.replace('{num}', NUM_PATTERN), '所得税法施行規則'),
        (r'法規第?({num})条'.replace('{num}', NUM_PATTERN), '法人税法施行規則'),
        (r'評基通({num})'.replace('{num}', NUM_PATTERN), '財産評価基本通達'),
        (r'法基通({num})'.replace('{num}', NUM_PATTERN), '法人税基本通達'),
        (r'所基通({num})'.replace('{num}', NUM_PATTERN), '所得税基本通達'),
        # 租税条約
        (r'日[^\s]{1,10}租税条約第?({num})条'.replace('{num}', NUM_PATTERN), '租税条約'),
        (r'租税条約第?({num})条'.replace('{num}', NUM_PATTERN), '租税条約'),
    ]

    for pattern, law_name in abbreviations:
        for match in re.finditer(pattern, text_nobracket):
            article = kanji_to_number(match.group(1))
            found.add(f'{law_name}{article}条')

    # 「同法」パターン: タイトルから推測した主要法律に適用
    if main_law and not found:
        doho_pattern = rf'同法第?({NUM_PATTERN})条(?:の({NUM_PATTERN}))?'
        for match in re.finditer(doho_pattern, text_nobracket):
            article = kanji_to_number(match.group(1))
            sub = match.group(2)
            if sub:
                found.add(f'{main_law}{article}条の{kanji_to_number(sub)}')
            else:
                found.add(f'{main_law}{article}条')

    return sorted(list(found))


def extract_text_from_html(html_path):
    """HTMLからテキスト抽出"""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')

    # メタデータ部分を除外
    meta_div = soup.find('div', class_='meta')
    if meta_div:
        meta_div.decompose()

    body = soup.find('body')
    if body:
        return body.get_text(separator=' ')
    return soup.get_text(separator=' ')


def main():
    html_dir = '/home/user/ai-law-db/simple/hanketsu'
    index_path = os.path.join(html_dir, 'index.json')

    # index.json読み込み
    with open(index_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    print(f'処理対象: {len(cases)}件')

    updated = 0
    total_laws = 0

    for i, case in enumerate(cases, 1):
        number = case['number']
        html_path = os.path.join(html_dir, f'{number}.html')

        if not os.path.exists(html_path):
            continue

        try:
            text = extract_text_from_html(html_path)
            title = case.get('title', '')
            laws = extract_laws_from_text(text, title)

            case['laws'] = laws

            if laws:
                updated += 1
                total_laws += len(laws)

            if i % 500 == 0:
                print(f'[{i}/{len(cases)}] 処理中...')

        except Exception as e:
            print(f'{number}: エラー - {e}')

    # 保存
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    with_laws = sum(1 for c in cases if c.get('laws'))
    print(f'\n完了:')
    print(f'  laws抽出あり: {with_laws}/{len(cases)} ({100*with_laws/len(cases):.1f}%)')
    print(f'  総条文数: {total_laws}')
    print(f'  平均条文数: {total_laws/with_laws:.1f}条/件' if with_laws else '')


if __name__ == '__main__':
    main()
