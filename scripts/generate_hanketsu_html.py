#!/usr/bin/env python3
"""
国税庁判決事例PDFからシンプルHTMLを生成
"""

import pdfplumber
from pypdf import PdfReader
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
h4 { font-size: 1em; color: #374151; margin-top: 1em; margin-left: 10px; font-weight: 600; }
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


def extract_text_from_pdf(pdf_path: str) -> tuple:
    """PDFから全テキストを抽出

    Returns:
        tuple: (text, is_garbled) - テキストと文字化けフラグ
    """
    text_parts = []

    # まずpdfplumberで試す
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    full_text = '\n\n'.join(text_parts)

    # CIDコードが含まれている場合はpypdfで再抽出
    if '(cid:' in full_text:
        text_parts = []
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        full_text = '\n\n'.join(text_parts)

    # 文字化けチェック（特殊文字が多い場合）
    # 正常な日本語PDF: ひらがな・カタカナ・漢字が多い
    # 文字化け: 特殊Unicode文字が多い
    sample = full_text[:500]

    # 正常な日本語文字数
    normal_jp = len(re.findall(r'[ぁ-んァ-ン一-龯々〆〇]', sample))
    # 異常な文字（ミャンマー文字、シンハラ文字など）
    garbled = len(re.findall(r'[ँ-ॿༀ-࿿Ⴀ-ჿ㈀-㏿]', sample))

    is_garbled = garbled > 10 and garbled > normal_jp

    return full_text, is_garbled


def clean_text(text: str) -> str:
    """テキストを整形"""
    # CIDコードを削除（残っている場合）
    text = re.sub(r'\(cid:\d+\)', '', text)

    # pypdfの出力で見られる不要な改行を修正
    # 文の途中での改行を削除（句読点の後以外）
    text = re.sub(r'([^。、）」\n])\n([ぁ-んァ-ン一-龯])', r'\1\2', text)

    # ページ番号（行末の単独数字）を削除
    text = re.sub(r'\n\d+\n', '\n', text)
    text = re.sub(r'\n\d+$', '', text)

    # テーブルの崩れた出力を修正（連続した空白や記号）
    text = re.sub(r'[o O n N \.]{5,}', ' ', text)

    # 複数の空白を1つに
    text = re.sub(r'[ \t]+', ' ', text)

    # 複数の改行を2つに
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def extract_case_title(lines: list) -> str:
    """複数行にまたがる事件名を抽出"""
    # 最初の5行を結合（PDF改行対応）、改行で分断された文字を結合
    combined = ' '.join(line.strip() for line in lines[:5] if line.strip())
    # 「事 件」→「事件」のように分断されたものを結合
    combined = re.sub(r'事\s+件', '事件', combined)

    # パターン1: 最後の「第●●号」の後に続く事件名を抽出
    # 例: "令和●●年（○○）第●●号 所得税更正処分等取消請求事件"
    # 「号」の後のスペースや「、」を挟んで日本語の事件名が続く
    match = re.search(r'第[●\d]+号[）\s、]*([ぁ-んァ-ン一-龯々〆〇等の一部]+?(?:請求|処分|決定|通知)?事件)', combined)
    if match:
        title = match.group(1).strip()
        # 先頭の不要文字を削除
        title = re.sub(r'^[、\s]+', '', title)
        if len(title) >= 8:
            return title

    # パターン2: 税目キーワード + 〜事件の形式
    # 例: "所得税更正処分等取消請求事件", "相続税の更正すべき理由がない旨の通知処分取消請求上告及び上告受理事件"
    tax_keywords = '所得税|法人税|消費税|相続税|贈与税|印紙税|登録免許税|更正|課税|納税|損害賠償|不当利得|還付'
    match = re.search(rf'({tax_keywords})[ぁ-んァ-ン一-龯々〆〇等の一部請求処分決定通知取消控訴上告受理\s]+事件', combined)
    if match:
        title = match.group(0).strip()
        if len(title) >= 8:
            return title

    # パターン3: 単純に日本語 + 事件を探す（フォールバック）
    match = re.search(r'([ぁ-んァ-ン一-龯々〆〇]{5,}事件)', combined)
    if match:
        title = match.group(1).strip()
        return title

    return ''


def clean_title(title: str) -> str:
    """タイトルを整形"""
    # 余分なスペースを削除
    title = re.sub(r'\s+', '', title)
    return title


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

    # 事件名を抽出（複数行対応）
    result['title'] = clean_title(extract_case_title(lines))

    # メタデータ抽出（最初の15行から）
    for i, line in enumerate(lines[:15]):
        line = line.strip()

        # 裁判所名
        if '裁判所' in line and not result['court']:
            # 裁判所名だけ抽出
            court_match = re.search(r'(最高裁判所|東京|大阪|名古屋|福岡|仙台|札幌|広島|高松|熊本|津|奈良|那覇|神戸|横浜|さいたま|千葉|京都|[\w]+)(高等|地方|簡易)?裁判所', line)
            if court_match:
                result['court'] = court_match.group()

        # 日付（令和○年○月○日）
        date_match = re.search(r'(令和|平成|昭和)\d*年\d*月\d*日', line)
        if date_match and not result['date']:
            result['date'] = date_match.group()

        # 判決結果（棄却・認容など）
        if not result['result']:
            for keyword in ['棄却', '認容', '却下', '取消', '一部認容', '不受理']:
                if keyword in line:
                    result['result'] = keyword
                    break

    # タイトルがなければフォールバック
    if not result['title']:
        # 最初の5行を結合して事件を探す
        combined = ' '.join(line.strip() for line in lines[:5] if line.strip())
        if '事件' in combined:
            result['title'] = combined[:100]
        elif lines:
            result['title'] = lines[0].strip()[:100]

    # テキスト全体を保存
    cleaned = clean_text(text)
    result['text'] = cleaned

    # セクション分割
    result['sections'] = parse_sections(cleaned)

    return result


def parse_sections(text: str) -> list:
    """テキストをセクションに分割（改善版）

    PDFのテキスト抽出では改行が不規則なため、
    セクションマーカーをテキスト内から検出して分割する
    """
    sections = []

    # 「主文」の位置を見つける（メインコンテンツの開始点）
    main_match = re.search(r'主\s*文', text)
    if not main_match:
        # 主文が見つからない場合は全体を1セクションとして返す
        return [{'title': '本文', 'level': 1, 'content': [text]}]

    # 主文以降のテキストを処理
    main_text = text[main_match.start():]

    # セクションの位置を収集
    section_positions = []

    # 主文（常に最初）
    section_positions.append({
        'pos': 0,
        'title': '主文',
        'level': 1
    })

    # 事実及び理由（複合語なのでマッチしやすい）
    for match in re.finditer(r'事実及び理由', main_text):
        if match.start() > 20:  # 主文セクション内でなければ
            section_positions.append({
                'pos': match.start(),
                'title': '事実及び理由',
                'level': 1
            })

    # 第X パターン（スペースの後にタイトルが続く形式）
    # "第１ 控訴の趣旨" または "事実及び理由第１ 控訴の趣旨" のような形式を検出
    for match in re.finditer(r'第([１２３４５６７８９0-9一二三四五六七八九十]+)\s+([ぁ-んァ-ン一-龯々]{1,20})', main_text):
        if match.start() > 10:
            dai_num = match.group(1)
            dai_title = match.group(2).strip()
            section_positions.append({
                'pos': match.start(),
                'title': f'第{dai_num} {dai_title}',
                'level': 2
            })

    # 位置でソート
    section_positions.sort(key=lambda x: x['pos'])

    # 重複や近接を除去（50文字以内は同一セクションとみなす）
    # ただし第Xパターンが連続する場合は別セクションとして扱う
    filtered_positions = []
    for sp in section_positions:
        if not filtered_positions:
            filtered_positions.append(sp)
        else:
            last = filtered_positions[-1]
            dist = sp['pos'] - last['pos']
            # 事実及び理由の直後に第Xが来る場合は、事実及び理由を採用しない
            if dist < 50 and last['title'] == '事実及び理由' and '第' in sp['title']:
                filtered_positions[-1] = sp
            elif dist >= 50:
                filtered_positions.append(sp)

    # セクションを構築
    for i, sp in enumerate(filtered_positions):
        start = sp['pos']
        # 次のセクションの開始位置、または終端
        if i + 1 < len(filtered_positions):
            end = filtered_positions[i + 1]['pos']
        else:
            end = len(main_text)

        content = main_text[start:end]

        # セクションタイトル自体を除去
        if sp['title'] == '主文':
            content = re.sub(r'^主\s*文\s*', '', content)
        elif sp['title'] == '事実及び理由':
            content = re.sub(r'^事実及び理由\s*', '', content)
        elif '第' in sp['title']:
            # 第X + タイトル部分を除去
            content = re.sub(r'^第[１２３４５６７８９0-9一二三四五六七八九十]+\s+[ぁ-んァ-ン一-龯々]{1,20}\s*', '', content)

        content = content.strip()

        if content:
            sections.append({
                'title': sp['title'],
                'level': sp['level'],
                'content': [content]
            })

    return sections


def split_into_paragraphs(content_lines: list) -> list:
    """コンテンツを適切な段落に分割"""
    if not content_lines:
        return []

    # 全体を結合
    full_text = ' '.join(content_lines)

    paragraphs = []

    # 番号付き項目で分割するパターン
    # （１）、（２）または １、２ または (1)、(2)
    split_pattern = r'(?=（[１２３４５６７８９０一二三四五六七八九十\d]+）|(?<=[。\s])([１２３４５６７８９一二三四五六七八九十])\s|(?<=\s)\(\d+\)\s)'

    # まず大きな区切りで分割
    parts = re.split(split_pattern, full_text)

    current_para = []
    for part in parts:
        if part is None:
            continue
        part = part.strip()
        if not part:
            continue

        # 番号で始まる場合は新しい段落
        if re.match(r'^（[１２３４５６７８９０一二三四五六七八九十\d]+）', part):
            if current_para:
                paragraphs.append(' '.join(current_para))
                current_para = []
            current_para.append(part)
        elif re.match(r'^[１２３４５６７８９一二三四五六七八九十]\s', part):
            if current_para:
                paragraphs.append(' '.join(current_para))
                current_para = []
            current_para.append(part)
        else:
            current_para.append(part)

    if current_para:
        paragraphs.append(' '.join(current_para))

    # 段落が1つだけで長すぎる場合、句点で分割を試みる
    if len(paragraphs) == 1 and len(paragraphs[0]) > 1000:
        long_text = paragraphs[0]
        # 文末の句点+スペースで分割（ただし括弧内は除く）
        sentences = re.split(r'。\s+', long_text)
        if len(sentences) > 1:
            paragraphs = []
            for i, sent in enumerate(sentences):
                if sent.strip():
                    # 最後以外は句点を戻す
                    if i < len(sentences) - 1:
                        paragraphs.append(sent.strip() + '。')
                    else:
                        paragraphs.append(sent.strip())

    return paragraphs


def generate_html(case: dict, year: str) -> str:
    """構造化されたHTMLを生成（改善版）"""
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
            content = section.get('content', [])
            level = section.get('level', 1)

            lines.append('<section>')
            # レベルに応じた見出しタグ
            if level == 1:
                lines.append(f'<h3>{h(title)}</h3>')
            else:
                lines.append(f'<h4>{h(title)}</h4>')

            # 段落分割を適用
            paragraphs = split_into_paragraphs(content)
            for para in paragraphs:
                if para.strip():
                    lines.append(f'<p>{h(para)}</p>')

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
    import argparse

    parser = argparse.ArgumentParser(description='国税庁判決事例PDFからHTMLを生成')
    parser.add_argument('--year', default='2023', help='年度（例: 2022, 2023）')
    parser.add_argument('--pdf-dir', help='PDFディレクトリ（省略時は自動設定）')
    parser.add_argument('--output-dir', help='出力ディレクトリ（省略時は自動設定）')
    parser.add_argument('--limit', type=int, help='処理数制限')
    args = parser.parse_args()

    year = args.year
    pdf_dir = args.pdf_dir or f'/home/user/ai-law-db/data/hanketsu/{year}/pdf'
    output_dir = args.output_dir or f'/home/user/ai-law-db/simple/hanketsu/{year}'
    limit = args.limit

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
            text, is_garbled = extract_text_from_pdf(pdf_path)

            if len(text) < 100:
                print(f"  警告: テキストが短すぎます ({len(text)}文字)")
                errors.append((case_number, "テキスト抽出失敗"))
                continue

            if is_garbled:
                print(f"  警告: 文字化けを検出（特殊フォントPDF）")
                errors.append((case_number, "文字化け（特殊フォント）"))
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
