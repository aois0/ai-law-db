#!/usr/bin/env python3
"""2020年判決: HTMLを統合ディレクトリに移動し、包括的メタデータを追加"""

import os
import re
import json
import shutil
from bs4 import BeautifulSoup

# 税目パターン（包括版）
TAX_TYPES = {
    "法人税": ["法人税", "復興特別法人税", "地方法人税"],
    "所得税": ["所得税", "復興特別所得税", "源泉所得税", "源泉徴収"],
    "相続税": ["相続税"],
    "贈与税": ["贈与税"],
    "消費税": ["消費税", "地方消費税"],
    "CFC": ["外国子会社合算税制", "特定外国子会社", "外国関係会社", "タックスヘイブン",
            "措置法66条の6", "措置法６６条の６", "措置法40条の4", "措置法４０条の４",
            "措置法68条の90", "措置法６８条の９０"],
    "移転価格": ["移転価格", "国外関連取引", "独立企業間価格", "比較対象取引",
                "措置法66条の4", "措置法６６条の４", "措置法68条の88", "措置法６８条の８８"],
}

# 争点キーワード
ISSUE_KEYWORDS = [
    "更正処分", "課税処分", "重加算税", "過少申告加算税", "無申告加算税",
    "仕入税額控除", "必要経費", "損金算入", "益金算入",
    "寄附金", "交際費", "役員報酬", "役員給与",
    "財産評価", "路線価", "小規模宅地", "配偶者控除",
    "青色申告", "推計課税", "実額反証",
    "信義則", "租税回避", "仮装隠蔽",
    "国家賠償", "不当利得", "損害賠償",
]

# 法令正規化パターン
LAW_PATTERNS = [
    (r'租税特別措置法[第]?[６6][６6]条の[６6]', '租税特別措置法66条の6'),
    (r'措置法[第]?[６6][６6]条の[６6]', '租税特別措置法66条の6'),
    (r'租税特別措置法[第]?[６6][６6]条の[４4]', '租税特別措置法66条の4'),
    (r'措置法[第]?[６6][６6]条の[４4]', '租税特別措置法66条の4'),
    (r'法人税法[第]?[２2][２2]条', '法人税法22条'),
    (r'法人税法[第]?[３3][４4]条', '法人税法34条'),
    (r'法人税法[第]?[３3][７7]条', '法人税法37条'),
    (r'所得税法[第]?[３3][６6]条', '所得税法36条'),
    (r'所得税法[第]?[３3][７7]条', '所得税法37条'),
    (r'所得税法[第]?[４4][５5]条', '所得税法45条'),
    (r'相続税法[第]?[２2][２2]条', '相続税法22条'),
    (r'国税通則法[第]?[６6][５5]条', '国税通則法65条'),
    (r'国税通則法[第]?[６6][８8]条', '国税通則法68条'),
    (r'消費税法[第]?[３3][０0]条', '消費税法30条'),
]


def extract_text_from_html(html_path):
    """HTMLからテキストを抽出"""
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    body = soup.find('body')
    return body.get_text(separator=' ') if body else ''


def convert_date_to_iso(date_str):
    """和暦→ISO形式変換"""
    if not date_str:
        return ""
    era_years = {"令和": 2018, "平成": 1988, "昭和": 1925}
    for era, base in era_years.items():
        m = re.search(rf'{era}(\d+)年(\d+)月(\d+)日', date_str)
        if m:
            y = base + int(m.group(1))
            return f"{y}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def detect_topics(text, title):
    """トピック（税目）検出"""
    topics = []
    combined = title + " " + text[:5000]
    for topic, keywords in TAX_TYPES.items():
        for kw in keywords:
            if kw in combined:
                if topic not in topics:
                    topics.append(topic)
                break
    return topics


def detect_keywords(text, title):
    """キーワード検出"""
    keywords = []
    combined = title + " " + text[:5000]
    for kw in ISSUE_KEYWORDS:
        if kw in combined and kw not in keywords:
            keywords.append(kw)
    return keywords


def extract_laws(text):
    """法令抽出"""
    laws = set()
    for pattern, normalized in LAW_PATTERNS:
        if re.search(pattern, text):
            laws.add(normalized)
    return sorted(list(laws))


def main():
    src_dir = "/home/user/ai-law-db/simple/hanketsu/2020"
    dst_dir = "/home/user/ai-law-db/simple/hanketsu"

    # 2020年のindex.jsonを読み込み
    with open(os.path.join(src_dir, 'index.json'), 'r', encoding='utf-8') as f:
        cases_2020 = json.load(f)

    print(f"2020年: {len(cases_2020)}件処理")

    processed = []
    stats = {"topics": 0, "keywords": 0, "laws": 0}

    for i, case in enumerate(cases_2020, 1):
        number = case['number']
        src_html = os.path.join(src_dir, f"{number}.html")
        dst_html = os.path.join(dst_dir, f"{number}.html")

        print(f"[{i}/{len(cases_2020)}] {number}...", end=" ")

        # HTMLをコピー
        shutil.copy2(src_html, dst_html)

        # テキスト抽出
        text = extract_text_from_html(dst_html)
        title = case.get('title', '')

        # メタデータ生成
        topics = detect_topics(text, title)
        keywords = detect_keywords(text, title)
        laws = extract_laws(text)
        date_iso = convert_date_to_iso(case.get('date', ''))

        # 拡張メタデータ
        entry = {
            "number": number,
            "title": title,
            "court": case.get('court', ''),
            "date": case.get('date', ''),
            "date_iso": date_iso,
            "result": case.get('result', ''),
            "topics": topics,
            "laws": laws,
            "keywords": keywords
        }
        processed.append(entry)

        # 個別JSON生成
        json_data = entry.copy()
        json_data["text"] = text
        with open(os.path.join(dst_dir, f"{number}.json"), 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        # 統計
        if topics:
            stats["topics"] += 1
        if keywords:
            stats["keywords"] += 1
        if laws:
            stats["laws"] += 1

        print(f"topics:{topics}")

    print(f"\n完了: {len(processed)}件")
    print(f"topics非空: {stats['topics']}件")
    print(f"keywords非空: {stats['keywords']}件")
    print(f"laws非空: {stats['laws']}件")

    # トピック別統計
    topic_counts = {}
    for case in processed:
        for t in case.get('topics', []):
            topic_counts[t] = topic_counts.get(t, 0) + 1

    print("\nトピック別:")
    for t, c in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}件")

    # 結果を返す（後で統合用）
    return processed


if __name__ == '__main__':
    result = main()
    # 結果をJSONに保存
    with open('/tmp/2020_processed.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n/tmp/2020_processed.json に保存")
