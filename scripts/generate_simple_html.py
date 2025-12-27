#!/usr/bin/env python3
"""
シンプルなHTML生成（AI読み取り最適化）
1条 = 1ファイル、最小限のマークアップ
"""

import xml.etree.ElementTree as ET
import os
import re
import html


def clean_text(text: str) -> str:
    """テキストを整形（余分な空白を削除）"""
    # 連続する空白を1つに
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_paragraph_text(para_elem) -> str:
    """Paragraph要素から条文テキストを抽出"""
    parts = []

    # ParagraphSentenceを取得
    for sent in para_elem.findall('.//ParagraphSentence'):
        text = ''.join(sent.itertext())
        if text.strip():
            parts.append(clean_text(text))

    # Itemを取得
    for item in para_elem.findall('.//Item'):
        item_title = item.find('ItemTitle')
        item_sent = item.find('ItemSentence')

        item_text = ''
        if item_title is not None:
            item_text += clean_text(''.join(item_title.itertext())) + ' '
        if item_sent is not None:
            item_text += clean_text(''.join(item_sent.itertext()))

        if item_text.strip():
            parts.append(item_text.strip())

    return '\n'.join(parts)


def parse_articles(xml_path: str) -> dict:
    """XMLから条文を抽出"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    law = root.find('.//ApplData/LawFullText/Law')
    if law is None:
        law = root.find('.//Law')
    if law is None:
        law = root

    result = {
        'title': '',
        'number': '',
        'articles': {}
    }

    law_title = law.find('.//LawTitle')
    if law_title is not None:
        result['title'] = clean_text(''.join(law_title.itertext()))

    law_num = law.find('.//LawNum')
    if law_num is not None:
        result['number'] = clean_text(''.join(law_num.itertext()))

    # MainProvision内のArticleのみ取得（附則を除く）
    main_provision = law.find('.//LawBody/MainProvision')
    if main_provision is None:
        main_provision = root

    for article in main_provision.iter('Article'):
        num = article.get('Num', '').replace('_', '-')
        if not num:
            continue

        caption_elem = article.find('ArticleCaption')
        title_elem = article.find('ArticleTitle')

        caption = clean_text(''.join(caption_elem.itertext())) if caption_elem is not None else ''
        title = clean_text(''.join(title_elem.itertext())) if title_elem is not None else ''

        # 条文本文を構築
        paragraphs = []
        for para in article.findall('Paragraph'):
            para_num = para.get('Num', '')
            para_text = extract_paragraph_text(para)
            if para_text:
                paragraphs.append({
                    'num': para_num,
                    'text': para_text
                })

        result['articles'][num] = {
            'num': num,
            'title': title,
            'caption': caption,
            'paragraphs': paragraphs
        }

    return result


def generate_simple_html(law_data: dict, article_num: str) -> str:
    """シンプルなHTMLを生成"""
    h = html.escape
    article = law_data['articles'].get(article_num)
    if not article:
        return None

    title = article.get('title', '')
    caption = article.get('caption', '')

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append(f'<title>{h(title)}{h(caption)} - {h(law_data["title"])}</title>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>{h(law_data["title"])}</h1>')
    lines.append(f'<h2>{h(title)}{h(caption)}</h2>')

    for para in article.get('paragraphs', []):
        para_num = para.get('num', '')
        para_text = para.get('text', '')

        # 各行を<p>で囲む
        for line in para_text.split('\n'):
            line = line.strip()
            if line:
                lines.append(f'<p>{h(line)}</p>')

    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def generate_index(law_data: dict) -> str:
    """目次HTMLを生成"""
    h = html.escape

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append(f'<title>{h(law_data["title"])} - 目次</title>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>{h(law_data["title"])}</h1>')
    lines.append(f'<p>{h(law_data["number"])}</p>')
    lines.append(f'<p>全{len(law_data["articles"])}条</p>')
    lines.append('<ul>')

    # 条番号でソート
    def sort_key(x):
        parts = re.split(r'[-_]', x)
        return [(0, int(p)) if p.isdigit() else (1, p) for p in parts]

    for num in sorted(law_data['articles'].keys(), key=sort_key):
        article = law_data['articles'][num]
        title = article.get('title', '')
        caption = article.get('caption', '')
        lines.append(f'<li><a href="{num}.html">{h(title)}{h(caption)}</a></li>')

    lines.append('</ul>')
    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def main():
    import sys
    if len(sys.argv) < 3:
        print("Usage: python generate_simple_html.py <input.xml> <output_dir>")
        sys.exit(1)

    xml_path = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"解析中: {xml_path}")
    law_data = parse_articles(xml_path)

    print(f"法令名: {law_data['title']}")
    print(f"条文数: {len(law_data['articles'])}")

    os.makedirs(output_dir, exist_ok=True)

    # 目次生成
    index_html = generate_index(law_data)
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)

    # 各条文生成
    count = 0
    for num in law_data['articles']:
        article_html = generate_simple_html(law_data, num)
        if article_html:
            with open(os.path.join(output_dir, f'{num}.html'), 'w', encoding='utf-8') as f:
                f.write(article_html)
            count += 1

    print(f"生成完了: {count}ファイル")


if __name__ == '__main__':
    main()
