#!/usr/bin/env python3
"""
国税庁判決事例PDFからシンプルHTMLを生成
"""

import pdfplumber
import os
import re
import json
import html as html_module


# シンプルなCSS（読みやすさ重視）
CSS = """
body {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
  font-family: "Hiragino Kaku Gothic Pro", "Yu Gothic", sans-serif;
  font-size: 16px;
  line-height: 1.8;
  color: #333;
  background: #fafafa;
}
h1 { font-size: 1.4em; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
h2 { font-size: 1.2em; color: #1e40af; margin-top: 1.5em; }
h3 { font-size: 1.1em; color: #1e3a8a; margin-top: 1.2em; border-left: 4px solid #3b82f6; padding-left: 10px; }
.meta { background: #e0f2fe; padding: 12px; border-radius: 6px; margin: 16px 0; }
.meta p { margin: 4px 0; }
section { margin: 24px 0; }
p { margin: 12px 0; text-align: justify; }
a { color: #2563eb; }
nav { margin: 20px 0; padding: 10px; background: #f1f5f9; border-radius: 6px; }
nav a { margin-right: 16px; }
"""

# 判決文の主要セクション
SECTIONS = [
    ('主文', 'main-text'),
    ('事実及び理由', 'facts-and-reasons'),
    ('事実', 'facts'),
    ('理由', 'reasons'),
    ('争点', 'issues'),
    ('当裁判所の判断', 'court-decision'),
    ('結論', 'conclusion'),
]


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
    # ページ番号（行末の単独数字）を削除
    text = re.sub(r'\n\d+\n', '\n', text)
    text = re.sub(r'\n\d+$', '', text)
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
        'sections': [],
        'text': ''
    }

    lines = text.split('\n')

    # メタデータ抽出（最初の15行から）
    for i, line in enumerate(lines[:15]):
        line = line.strip()

        # 裁判所名
        if '裁判所' in line and not result['court']:
            # 裁判所名だけ抽出
            court_match = re.search(r'(東京|大阪|名古屋|福岡|仙台|札幌|広島|高松|[\w]+)(高等|地方|簡易)?裁判所', line)
            if court_match:
                result['court'] = court_match.group()

        # 日付（令和○年○月○日）
        date_match = re.search(r'(令和|平成|昭和)\d*年\d*月\d*日', line)
        if date_match and not result['date']:
            result['date'] = date_match.group()

        # 判決結果（棄却・認容など）
        if not result['result']:
            for keyword in ['棄却', '認容', '却下', '取消', '一部認容']:
                if keyword in line:
                    result['result'] = keyword
                    break

        # 事件名
        if '事件' in line and not result['title']:
            result['title'] = line

    # タイトルがなければ最初の行を使用
    if not result['title'] and lines:
        result['title'] = lines[0].strip()[:100]

    # テキスト全体を保存
    cleaned = clean_text(text)
    result['text'] = cleaned

    # セクション分割
    result['sections'] = parse_sections(cleaned)

    return result


def parse_sections(text: str) -> list:
    """テキストをセクションに分割"""
    sections = []

    # セクション見出しのパターン
    # 「第１ 請求」「第２ 事案の概要」などの形式
    pattern = r'^(第[１２３４５６７８９0-9]+)\s+(.+?)$'

    lines = text.split('\n')
    current_section = {'title': '冒頭', 'content': []}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # セクション見出しをチェック
        match = re.match(pattern, line)
        if match:
            # 前のセクションを保存
            if current_section['content']:
                sections.append(current_section)
            current_section = {
                'title': f"{match.group(1)} {match.group(2)}",
                'content': []
            }
        # 主文、事実及び理由などの見出し
        elif line in ['主 文', '主文', '事実及び理由', '理 由', '理由', '事 実', '事実']:
            if current_section['content']:
                sections.append(current_section)
            current_section = {
                'title': line.replace(' ', ''),
                'content': []
            }
        else:
            current_section['content'].append(line)

    # 最後のセクションを保存
    if current_section['content']:
        sections.append(current_section)

    return sections


def generate_html(case: dict, year: str) -> str:
    """構造化されたHTMLを生成"""
    h = html_module.escape

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    lines.append(f'<title>{h(case["number"])} {h(case["title"][:50])} - 国税庁判決事例集</title>')
    lines.append(f'<style>{CSS}</style>')
    lines.append('</head>')
    lines.append('<body>')

    # ナビゲーション
    lines.append('<nav>')
    lines.append(f'<a href="index.html">目次に戻る</a>')
    lines.append('</nav>')

    # ヘッダー
    lines.append(f'<h1>判決 {h(case["number"])}</h1>')
    lines.append(f'<h2>{h(case["title"])}</h2>')

    # メタデータ
    lines.append('<div class="meta">')
    if case['court']:
        lines.append(f'<p><strong>裁判所:</strong> {h(case["court"])}</p>')
    if case['date']:
        lines.append(f'<p><strong>判決日:</strong> {h(case["date"])}</p>')
    if case['result']:
        lines.append(f'<p><strong>結果:</strong> {h(case["result"])}</p>')
    lines.append('</div>')

    # セクションごとに出力
    if case['sections']:
        for section in case['sections']:
            title = section['title']
            content = section['content']

            lines.append('<section>')
            lines.append(f'<h3>{h(title)}</h3>')

            # 内容を段落に
            para_text = []
            for line in content:
                if line:
                    para_text.append(line)
                else:
                    if para_text:
                        lines.append(f'<p>{h(" ".join(para_text))}</p>')
                        para_text = []

            if para_text:
                lines.append(f'<p>{h(" ".join(para_text))}</p>')

            lines.append('</section>')
    else:
        # セクション分割できなかった場合
        paragraphs = case['text'].split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if para:
                lines.append(f'<p>{h(para)}</p>')

    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def generate_index_html(cases: list, year: str) -> str:
    """目次HTMLを生成"""
    h = html_module.escape

    # 目次用CSS
    index_css = CSS + """
table { width: 100%; border-collapse: collapse; margin-top: 20px; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }
th { background: #f1f5f9; font-weight: bold; }
tr:hover { background: #f8fafc; }
.result-棄却 { color: #dc2626; }
.result-認容 { color: #16a34a; }
.result-一部認容 { color: #ca8a04; }
"""

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    lines.append(f'<title>国税庁判決事例集 {year} - 目次</title>')
    lines.append(f'<style>{index_css}</style>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>国税庁判決事例集 {year}</h1>')
    lines.append(f'<p>判決数: <strong>{len(cases)}件</strong></p>')

    # テーブル形式
    lines.append('<table>')
    lines.append('<tr><th>番号</th><th>事件名</th><th>裁判所</th><th>判決日</th><th>結果</th></tr>')

    for case in sorted(cases, key=lambda x: x.get('number', '')):
        num = case.get('number', 'unknown')
        title = case.get('title', '')[:60]
        court = case.get('court', '')
        date = case.get('date', '')
        result = case.get('result', '')
        result_class = f'result-{result}' if result else ''

        lines.append(f'<tr>')
        lines.append(f'<td><a href="{num}.html">{h(num)}</a></td>')
        lines.append(f'<td>{h(title)}</td>')
        lines.append(f'<td>{h(court)}</td>')
        lines.append(f'<td>{h(date)}</td>')
        lines.append(f'<td class="{result_class}">{h(result)}</td>')
        lines.append(f'</tr>')

    lines.append('</table>')
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
                'date': case['date'],
                'result': case.get('result', '')
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
