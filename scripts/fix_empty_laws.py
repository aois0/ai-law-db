#!/usr/bin/env python3
"""
laws空問題の統合対応スクリプト
Phase 2: 上告受理申立却下を明示的に記載
Phase 3: 原判決引用を検出し原審lawsを継承
Phase 4: 残りのケースで再抽出
"""

import os
import re
import json
from bs4 import BeautifulSoup

# update_laws.pyから関数をインポート
from update_laws import extract_laws_from_text, extract_text_from_html

# 上告受理申立却下パターン
DISMISSAL_PATTERNS = [
    r'本件を上告審として受理しない',
    r'民訴法３１８条１項により受理すべきものとは認められない',
    r'民訴法318条1項により受理すべきものとは認められない',
    r'本件上告を棄却する',
    r'上告受理の申立て.*理由がない',
    r'上告を棄却する',
    r'上告についての上告理由がない',
    r'上告受理申立ての理由がない',
]

# 原判決引用パターン
CITATION_PATTERNS = [
    r'原判決.*事実及び理由.*記載のとおり.*引用',
    r'理由は.*原判決.*記載のとおり',
    r'原判決.*引用する',
    r'当裁判所.*原判決.*引用',
]

# 裁判所の階層
COURT_HIERARCHY = {
    '最高裁判所': 3,
    '東京高等裁判所': 2,
    '大阪高等裁判所': 2,
    '名古屋高等裁判所': 2,
    '福岡高等裁判所': 2,
    '仙台高等裁判所': 2,
    '札幌高等裁判所': 2,
    '広島高等裁判所': 2,
    '高松高等裁判所': 2,
}


def is_dismissal(text):
    """上告受理申立却下かどうかを判定"""
    text_nospace = re.sub(r'\s+', '', text)
    for pattern in DISMISSAL_PATTERNS:
        if re.search(pattern, text_nospace):
            return True
    return False


def is_citation(text):
    """原判決引用かどうかを判定"""
    text_nospace = re.sub(r'\s+', '', text)
    for pattern in CITATION_PATTERNS:
        if re.search(pattern, text_nospace):
            return True
    return False


def get_court_level(court_name):
    """裁判所の階層を取得"""
    for court, level in COURT_HIERARCHY.items():
        if court in court_name:
            return level
    # 地方裁判所はレベル1
    if '地方裁判所' in court_name or '地裁' in court_name:
        return 1
    return 0


def find_original_judgment(case, all_cases):
    """原審判決を検索"""
    title = case.get('title', '')
    court = case.get('court', '')
    current_level = get_court_level(court)

    # 事件名から「控訴」「上告」を除去
    base_title = re.sub(r'(控訴|上告受理申立|上告)事件$', '事件', title)
    base_title = re.sub(r'控訴審判決取消等?', '', base_title)
    base_title = base_title.strip()

    # 同一タイトル・下級審を検索
    for c in all_cases:
        c_title = c.get('title', '')
        c_court = c.get('court', '')
        c_level = get_court_level(c_court)

        # 下級審で同じタイトル
        if c_level < current_level and c_title == base_title:
            return c

        # タイトルが部分一致
        if c_level < current_level and base_title and base_title in c_title:
            return c

    return None


def main():
    html_dir = '/home/user/ai-law-db/simple/hanketsu'
    index_path = os.path.join(html_dir, 'index.json')

    # index.json読み込み
    with open(index_path, 'r', encoding='utf-8') as f:
        cases = json.load(f)

    print(f'総件数: {len(cases)}件')

    # 統計
    stats = {
        'total': len(cases),
        'empty_before': 0,
        'dismissal': 0,
        'citation': 0,
        'citation_inherited': 0,
        'reextracted': 0,
        'still_empty': 0,
    }

    # laws空のケースをカウント
    stats['empty_before'] = sum(1 for c in cases if not c.get('laws'))

    print(f'laws空（処理前）: {stats["empty_before"]}件')

    # 各ケースを処理
    for i, case in enumerate(cases, 1):
        number = case['number']
        laws = case.get('laws', [])

        # 既にlawsがある場合はスキップ
        if laws:
            continue

        html_path = os.path.join(html_dir, f'{number}.html')
        if not os.path.exists(html_path):
            continue

        try:
            text = extract_text_from_html(html_path)
            title = case.get('title', '')
            court = case.get('court', '')

            # Phase 2: 上告受理申立却下の検出
            if is_dismissal(text):
                case['laws'] = ['（上告受理申立却下）']
                case['judgment_type'] = 'dismissal'
                stats['dismissal'] += 1
                continue

            # Phase 3: 原判決引用の検出
            if is_citation(text):
                original = find_original_judgment(case, cases)
                if original and original.get('laws'):
                    # 原審lawsを継承
                    inherited_laws = ['（原判決引用）'] + list(original.get('laws', []))
                    case['laws'] = inherited_laws
                    case['laws_source'] = 'inherited'
                    case['original_case'] = original.get('number')
                    stats['citation_inherited'] += 1
                else:
                    # 原審が見つからない場合
                    case['laws'] = ['（原判決引用）']
                    case['judgment_type'] = 'appeal_rejected'
                stats['citation'] += 1
                continue

            # Phase 4: 再抽出を試みる
            new_laws = extract_laws_from_text(text, title)
            if new_laws:
                case['laws'] = new_laws
                stats['reextracted'] += 1
            else:
                # それでも空の場合、カテゴリ別に明示的マーク
                if '上告受理' in title and '本件を上告審として受理する' in text:
                    case['laws'] = ['（上告受理決定）']
                    case['judgment_type'] = 'acceptance'
                elif '損害賠償' in title or '国家賠償' in title:
                    case['laws'] = ['（損害賠償請求）']
                elif '国家損害賠償' in title:
                    case['laws'] = ['（国家賠償請求）']
                else:
                    case['laws'] = ['（条文参照なし）']
                stats['still_empty'] += 1

        except Exception as e:
            print(f'{number}: エラー - {e}')

        if i % 500 == 0:
            print(f'[{i}/{len(cases)}] 処理中...')

    # 保存
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    # 最終統計
    empty_after = sum(1 for c in cases if not c.get('laws'))
    with_laws = len(cases) - empty_after

    print(f'\n=== 処理結果 ===')
    print(f'総件数: {stats["total"]}件')
    print(f'laws空（処理前）: {stats["empty_before"]}件')
    print(f'')
    print(f'処理内訳:')
    print(f'  上告受理申立却下: {stats["dismissal"]}件')
    print(f'  原判決引用: {stats["citation"]}件（うち継承: {stats["citation_inherited"]}件）')
    print(f'  再抽出成功: {stats["reextracted"]}件')
    print(f'  残り空: {stats["still_empty"]}件')
    print(f'')
    print(f'laws空（処理後）: {empty_after}件')
    print(f'lawsあり: {with_laws}件 ({100*with_laws/len(cases):.1f}%)')


if __name__ == '__main__':
    main()
