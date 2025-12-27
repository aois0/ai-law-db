#!/usr/bin/env python3
"""
国税庁判決事例PDFからシンプルHTMLを生成
"""

import pdfplumber
import os
import re
import json
import html


def extract_text_from_pdf(pdf_path: str) -> str:
    """PDFから全テキストを抽出"""
    text_parts = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    return '\n\n'.join(text_parts)


def clean_text(text: str) -> str:
    """テキストを整形"""
    # 複数の空白を1つに
    text = re.sub(r'[ \t]+', ' ', text)
    # 複数の改行を2つに
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_hanketsu(text: str, case_number: str) -> dict:
    """判決テキストを解析してメタデータと本文を抽出"""
    result = {
        'number': case_number,
        'title': '',
        'court': '',
        'date': '',
        'result': '',
        'text': ''
    }

    lines = text.split('\n')

    # タイトル抽出（最初の数行から）
    for i, line in enumerate(lines[:10]):
        line = line.strip()

        # 裁判所名
        if '裁判所' in line and not result['court']:
            result['court'] = line

        # 日付（令和○年○月○日）
        date_match = re.search(r'(令和|平成|昭和)\S*年\S*月\S*日', line)
        if date_match and not result['date']:
            result['date'] = date_match.group()

        # 事件名
        if '事件' in line and not result['title']:
            result['title'] = line

    # タイトルがなければ最初の行を使用
    if not result['title'] and lines:
        result['title'] = lines[0].strip()[:100]

    # テキスト全体を保存
    result['text'] = clean_text(text)

    return result


def generate_html(case: dict, year: str) -> str:
    """シンプルなHTMLを生成"""
    h = html.escape

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append(f'<title>{h(case["number"])} - {h(case["title"][:50])}</title>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>国税庁判決事例集 {year}</h1>')
    lines.append(f'<h2>{h(case["number"])}: {h(case["title"])}</h2>')

    # メタデータ
    if case['court']:
        lines.append(f'<p>裁判所: {h(case["court"])}</p>')
    if case['date']:
        lines.append(f'<p>判決日: {h(case["date"])}</p>')

    # 本文を段落に分割
    paragraphs = case['text'].split('\n\n')
    for para in paragraphs:
        para = para.strip()
        if para:
            # 長い段落は複数の<p>に分割しない（AIが文脈を把握しやすいように）
            lines.append(f'<p>{h(para)}</p>')

    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def generate_index_html(cases: list, year: str) -> str:
    """目次HTMLを生成"""
    h = html.escape

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append(f'<title>国税庁判決事例集 {year} - 目次</title>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>国税庁判決事例集 {year}</h1>')
    lines.append(f'<p>判決数: {len(cases)}件</p>')
    lines.append('<ul>')

    for case in sorted(cases, key=lambda x: x.get('number', '')):
        num = case.get('number', 'unknown')
        title = case.get('title', '')[:50]
        court = case.get('court', '')
        date = case.get('date', '')
        lines.append(f'<li><a href="{num}.html">{h(num)}: {h(title)}</a> ({h(court)} {h(date)})</li>')

    lines.append('</ul>')
    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def main():
    import sys

    year = '2023'
    pdf_dir = f'/home/user/ai-law-db/data/hanketsu/{year}/pdf'
    output_dir = f'/home/user/ai-law-db/simple/hanketsu/{year}'
    limit = None

    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"処理数制限: {limit}件")
        except:
            pass

    os.makedirs(output_dir, exist_ok=True)

    # PDF一覧取得
    pdf_files = sorted([f for f in os.listdir(pdf_dir) if f.endswith('.pdf')])

    if limit:
        pdf_files = pdf_files[:limit]

    print(f"処理対象: {len(pdf_files)}件")

    cases = []
    success = 0
    errors = []

    for i, filename in enumerate(pdf_files, 1):
        case_number = filename.replace('.pdf', '')
        pdf_path = os.path.join(pdf_dir, filename)

        print(f"[{i}/{len(pdf_files)}] {case_number}...")

        try:
            # テキスト抽出
            text = extract_text_from_pdf(pdf_path)

            if len(text) < 100:
                print(f"  警告: テキストが短すぎます ({len(text)}文字)")
                errors.append((case_number, "テキスト抽出失敗"))
                continue

            # 解析
            case = parse_hanketsu(text, case_number)
            cases.append(case)

            # HTML生成
            html_content = generate_html(case, year)
            html_path = os.path.join(output_dir, f'{case_number}.html')

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            success += 1

        except Exception as e:
            print(f"  エラー: {e}")
            errors.append((case_number, str(e)))

    # 目次生成
    if cases:
        index_html = generate_index_html(cases, year)
        with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(index_html)

        # メタデータJSON
        metadata = []
        for case in cases:
            metadata.append({
                'number': case['number'],
                'title': case['title'],
                'court': case['court'],
                'date': case['date']
            })

        with open(os.path.join(output_dir, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {success}/{len(pdf_files)}件")
    print(f"出力先: {output_dir}")

    if errors:
        print(f"\nエラー ({len(errors)}件):")
        for num, err in errors:
            print(f"  {num}: {err}")


if __name__ == '__main__':
    main()
