#!/usr/bin/env python3
"""
AI向け強化HTML生成
- 条・項・号にdata属性付与
- 本則⇄施行令⇄規則の委任リンク抽出
"""

import xml.etree.ElementTree as ET
import os
import re
import html
import json


def clean_text(text: str) -> str:
    """テキストを整形（余分な空白を削除）"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_references(text: str, law_type: str) -> list:
    """
    条文テキストから委任先の参照を抽出
    law_type: 'act' (法律), 'order' (政令), 'rule' (規則)
    """
    refs = []

    # 政令への参照（法律から）
    if law_type == 'act':
        # 「政令で定める」パターン
        if re.search(r'政令で定める', text):
            refs.append({'type': 'order', 'pattern': '政令で定める'})
        # 「令第○条」パターン
        matches = re.findall(r'令第([一二三四五六七八九十百千]+(?:の[一二三四五六七八九十]+)?)条', text)
        for m in matches:
            refs.append({'type': 'order', 'article': m})

    # 省令・規則への参照
    if law_type in ['act', 'order']:
        if re.search(r'(省令|規則)で定める', text):
            refs.append({'type': 'rule', 'pattern': '省令/規則で定める'})
        # 「規則第○条」パターン
        matches = re.findall(r'規則第([一二三四五六七八九十百千]+(?:の[一二三四五六七八九十]+)?)条', text)
        for m in matches:
            refs.append({'type': 'rule', 'article': m})

    # 法律への参照（政令・規則から）
    if law_type in ['order', 'rule']:
        # 「法第○条」パターン
        matches = re.findall(r'法第([一二三四五六七八九十百千]+(?:の[一二三四五六七八九十]+)?)条', text)
        for m in matches:
            refs.append({'type': 'act', 'article': m})

    return refs


def kansuji_to_num(text: str) -> str:
    """漢数字を算用数字に変換（ファイル名用）"""
    kansuji_digit = {
        '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9
    }

    def convert_part(s: str) -> int:
        """漢数字の一部分を数値に変換"""
        if not s:
            return 0

        result = 0
        current = 0

        i = 0
        while i < len(s):
            c = s[i]
            if c in kansuji_digit:
                current = kansuji_digit[c]
                i += 1
            elif c == '十':
                if current == 0:
                    current = 1
                result += current * 10
                current = 0
                i += 1
            elif c == '百':
                if current == 0:
                    current = 1
                result += current * 100
                current = 0
                i += 1
            elif c == '千':
                if current == 0:
                    current = 1
                result += current * 1000
                current = 0
                i += 1
            else:
                i += 1

        result += current
        return result

    # 「の」で分割して各部分を変換
    parts = text.split('の')
    converted_parts = []

    for part in parts:
        if part:
            num = convert_part(part)
            converted_parts.append(str(num) if num > 0 else part)

    return '-'.join(converted_parts)


def extract_paragraph_text(para_elem) -> tuple:
    """Paragraph要素から条文テキストと号リストを抽出"""
    parts = []
    items = []

    # ParagraphSentenceを取得
    for sent in para_elem.findall('.//ParagraphSentence'):
        text = ''.join(sent.itertext())
        if text.strip():
            parts.append(clean_text(text))

    # Itemを取得
    for item in para_elem.findall('.//Item'):
        item_title = item.find('ItemTitle')
        item_sent = item.find('ItemSentence')

        item_num = ''
        item_text = ''
        if item_title is not None:
            item_num = clean_text(''.join(item_title.itertext()))
        if item_sent is not None:
            item_text = clean_text(''.join(item_sent.itertext()))

        if item_num or item_text:
            items.append({
                'num': item_num,
                'text': item_text
            })

    return '\n'.join(parts), items


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
            para_text, items = extract_paragraph_text(para)
            if para_text or items:
                paragraphs.append({
                    'num': para_num,
                    'text': para_text,
                    'items': items
                })

        result['articles'][num] = {
            'num': num,
            'title': title,
            'caption': caption,
            'paragraphs': paragraphs
        }

    return result


def detect_law_type(title: str) -> str:
    """法令名から種別を判定"""
    if '施行規則' in title:
        return 'rule'
    elif '施行令' in title:
        return 'order'
    else:
        return 'act'


def get_related_laws(law_type: str, base_name: str) -> dict:
    """関連法令のディレクトリ名を取得"""
    related = {}
    if law_type == 'act':
        related['order'] = f'{base_name}_seirei'
        related['rule'] = f'{base_name}_kisoku'
    elif law_type == 'order':
        related['act'] = base_name.replace('_seirei', '')
        related['rule'] = base_name.replace('_seirei', '_kisoku')
    elif law_type == 'rule':
        related['act'] = base_name.replace('_kisoku', '')
        related['order'] = base_name.replace('_kisoku', '_seirei')
    return related


def generate_enhanced_html(law_data: dict, article_num: str, law_type: str, related_laws: dict, base_url: str) -> str:
    """強化版HTMLを生成"""
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
    lines.append('<style>')
    lines.append('body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }')
    lines.append('.ref-link { color: #0066cc; text-decoration: none; font-size: 0.9em; }')
    lines.append('.ref-link:hover { text-decoration: underline; }')
    lines.append('.refs { margin-top: 20px; padding: 10px; background: #f5f5f5; border-radius: 4px; }')
    lines.append('.refs h3 { margin: 0 0 10px 0; font-size: 0.9em; color: #666; }')
    lines.append('.item { margin-left: 1em; }')
    lines.append('</style>')
    lines.append('</head>')
    lines.append('<body>')

    # 条のdata属性
    lines.append(f'<article data-law="{h(law_data["title"])}" data-article="{h(article_num)}">')
    lines.append(f'<h1>{h(law_data["title"])}</h1>')
    lines.append(f'<h2 id="article-{h(article_num)}">{h(title)}{h(caption)}</h2>')

    all_refs = []

    for para in article.get('paragraphs', []):
        para_num = para.get('num', '')
        para_text = para.get('text', '')
        items = para.get('items', [])

        # 参照を抽出
        refs = extract_references(para_text, law_type)
        all_refs.extend(refs)
        for item in items:
            refs = extract_references(item.get('text', ''), law_type)
            all_refs.extend(refs)

        # 項のdata属性付きdiv
        if para_num:
            lines.append(f'<div data-paragraph="{para_num}">')
        else:
            lines.append('<div>')

        # 項本文
        if para_text:
            if para_num:
                lines.append(f'<p>{para_num} {h(para_text)}</p>')
            else:
                lines.append(f'<p>{h(para_text)}</p>')

        # 号
        for item in items:
            item_num = item.get('num', '')
            item_text = item.get('text', '')
            if item_num or item_text:
                # 号番号からdata属性用の値を作成
                item_id = item_num.rstrip('　 ')
                lines.append(f'<p class="item" data-item="{h(item_id)}">{h(item_num)} {h(item_text)}</p>')

        lines.append('</div>')

    # 委任リンクセクション
    if all_refs:
        lines.append('<div class="refs">')
        lines.append('<h3>関連条文</h3>')
        lines.append('<ul>')

        seen = set()
        for ref in all_refs:
            ref_type = ref.get('type')
            ref_article = ref.get('article')
            ref_pattern = ref.get('pattern')

            if ref_article and ref_type in related_laws:
                # 具体的な条番号がある場合はリンク生成
                article_file = kansuji_to_num(ref_article)
                ref_dir = related_laws[ref_type]
                ref_url = f'{base_url}{ref_dir}/{article_file}.html'

                type_label = {'act': '法', 'order': '令', 'rule': '規則'}[ref_type]
                link_text = f'{type_label}第{ref_article}条'

                if link_text not in seen:
                    lines.append(f'<li><a class="ref-link" href="{ref_url}">{h(link_text)}</a></li>')
                    seen.add(link_text)
            elif ref_pattern and ref_type in related_laws:
                # パターンマッチの場合は目次へのリンク
                ref_dir = related_laws[ref_type]
                ref_url = f'{base_url}{ref_dir}/index.html'

                type_label = {'act': '法', 'order': '施行令', 'rule': '施行規則'}[ref_type]
                link_text = f'{type_label}（{ref_pattern}）'

                if link_text not in seen:
                    lines.append(f'<li><a class="ref-link" href="{ref_url}">{h(link_text)}</a></li>')
                    seen.add(link_text)

        lines.append('</ul>')
        lines.append('</div>')

    lines.append('</article>')
    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def generate_index(law_data: dict, law_type: str, related_laws: dict, base_url: str) -> str:
    """目次HTMLを生成"""
    h = html.escape

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append(f'<title>{h(law_data["title"])} - 目次</title>')
    lines.append('<style>')
    lines.append('body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }')
    lines.append('.related { margin: 20px 0; padding: 10px; background: #e8f4e8; border-radius: 4px; }')
    lines.append('</style>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>{h(law_data["title"])}</h1>')
    lines.append(f'<p>{h(law_data["number"])}</p>')
    lines.append(f'<p>全{len(law_data["articles"])}条</p>')

    # 関連法令リンク
    if related_laws:
        lines.append('<div class="related">')
        lines.append('<h3>関連法令</h3>')
        lines.append('<ul>')
        type_labels = {
            'act': '本則（法律）',
            'order': '施行令（政令）',
            'rule': '施行規則（省令）'
        }
        for ref_type, ref_dir in related_laws.items():
            ref_url = f'{base_url}{ref_dir}/index.html'
            lines.append(f'<li><a href="{ref_url}">{type_labels.get(ref_type, ref_type)}</a></li>')
        lines.append('</ul>')
        lines.append('</div>')

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
    if len(sys.argv) < 4:
        print("Usage: python generate_enhanced_html.py <input.xml> <output_dir> <base_name>")
        print("  base_name: hojinzei, sozei_tokubetsu など")
        sys.exit(1)

    xml_path = sys.argv[1]
    output_dir = sys.argv[2]
    base_name = sys.argv[3]
    base_url = '../'  # 相対パス

    print(f"解析中: {xml_path}")
    law_data = parse_articles(xml_path)

    print(f"法令名: {law_data['title']}")
    print(f"条文数: {len(law_data['articles'])}")

    law_type = detect_law_type(law_data['title'])
    print(f"法令種別: {law_type}")

    related_laws = get_related_laws(law_type, base_name)
    print(f"関連法令: {related_laws}")

    os.makedirs(output_dir, exist_ok=True)

    # 目次生成
    index_html = generate_index(law_data, law_type, related_laws, base_url)
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)

    # 各条文生成
    count = 0
    for num in law_data['articles']:
        article_html = generate_enhanced_html(law_data, num, law_type, related_laws, base_url)
        if article_html:
            with open(os.path.join(output_dir, f'{num}.html'), 'w', encoding='utf-8') as f:
                f.write(article_html)
            count += 1

    print(f"生成完了: {count}ファイル")


if __name__ == '__main__':
    main()
