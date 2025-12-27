#!/usr/bin/env python3
"""
法令XMLからzeiken.co.jpスタイルのサイトを生成

使用例:
    python generate_law_site.py data/shotokuzei.xml --output laws/shotokuzei/
"""

import argparse
import xml.etree.ElementTree as ET
import os
import json
import html
import re


def extract_text(element) -> str:
    """XML要素からテキストを再帰的に抽出"""
    if element is None:
        return ''
    texts = []
    if element.text:
        texts.append(element.text)
    for child in element:
        texts.append(extract_text(child))
        if child.tail:
            texts.append(child.tail)
    return ''.join(texts)


def parse_article_num(num_str: str) -> str:
    """条番号を正規化（例: 6_2 → 6-2）"""
    if not num_str:
        return ''
    return num_str.replace('_', '-')


def sort_article_num(x: str):
    """条番号をソート用のキーに変換"""
    parts = re.split(r'[-_]', x)
    result = []
    for p in parts:
        if p.isdigit():
            result.append((0, int(p)))  # 数字は (0, num) でソート
        else:
            result.append((1, p))  # 文字列は (1, str) でソート
    return result


def parse_law_structure(xml_path: str) -> dict:
    """法令XMLから階層構造を解析"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 法令本体を取得
    law = root.find('.//ApplData/LawFullText/Law')
    if law is None:
        law = root.find('.//Law')
    if law is None:
        law = root

    law_body = law.find('LawBody')
    if law_body is None:
        law_body = law

    result = {
        'title': '',
        'number': '',
        'toc': [],  # 目次構造
        'articles': {}  # 条番号 -> 条文データ
    }

    # 法令名・番号
    law_title = law.find('.//LawTitle')
    if law_title is not None:
        result['title'] = extract_text(law_title)

    law_num = law.find('.//LawNum')
    if law_num is not None:
        result['number'] = extract_text(law_num)

    # 階層構造を解析
    def process_structure(element, parent_path=[]):
        items = []

        for child in element:
            tag = child.tag

            if tag == 'Part':
                part_title = extract_text(child.find('PartTitle'))
                part_item = {
                    'type': 'part',
                    'title': part_title,
                    'children': process_structure(child, parent_path + [part_title])
                }
                items.append(part_item)

            elif tag == 'Chapter':
                chapter_title = extract_text(child.find('ChapterTitle'))
                chapter_item = {
                    'type': 'chapter',
                    'title': chapter_title,
                    'children': process_structure(child, parent_path + [chapter_title])
                }
                items.append(chapter_item)

            elif tag == 'Section':
                section_title = extract_text(child.find('SectionTitle'))
                section_item = {
                    'type': 'section',
                    'title': section_title,
                    'children': process_structure(child, parent_path + [section_title])
                }
                items.append(section_item)

            elif tag == 'Subsection':
                subsection_title = extract_text(child.find('SubsectionTitle'))
                subsection_item = {
                    'type': 'subsection',
                    'title': subsection_title,
                    'children': process_structure(child, parent_path + [subsection_title])
                }
                items.append(subsection_item)

            elif tag == 'Article':
                num = parse_article_num(child.get('Num', ''))
                caption = extract_text(child.find('ArticleCaption'))
                title = extract_text(child.find('ArticleTitle'))

                # 条文データを保存
                paragraphs = []
                for para in child.findall('Paragraph'):
                    para_num = para.get('Num', '')
                    para_sentence = child.find('.//ParagraphSentence')
                    para_text = extract_text(para)

                    # 項の中の号を取得
                    items_list = []
                    for item in para.findall('.//Item'):
                        item_num = extract_text(item.find('ItemTitle'))
                        item_sentence = extract_text(item.find('ItemSentence'))
                        items_list.append({
                            'num': item_num,
                            'text': item_sentence
                        })

                    paragraphs.append({
                        'num': para_num,
                        'text': para_text,
                        'items': items_list
                    })

                result['articles'][num] = {
                    'num': num,
                    'caption': caption,
                    'title': title,
                    'paragraphs': paragraphs,
                    'path': parent_path.copy()
                }

                items.append({
                    'type': 'article',
                    'num': num,
                    'caption': caption,
                    'title': title
                })

        return items

    # MainProvision（本則）を処理
    main_provision = law_body.find('MainProvision')
    if main_provision is not None:
        result['toc'] = process_structure(main_provision)
    else:
        result['toc'] = process_structure(law_body)

    return result


def generate_article_html(law_data: dict, article_num: str, law_code: str) -> str:
    """個別条文のHTMLを生成（2ペインレイアウト）"""
    h = html.escape
    article = law_data['articles'].get(article_num, {})

    if not article:
        return None

    # 前後の条文を取得
    all_nums = sorted(law_data['articles'].keys(), key=sort_article_num)
    try:
        idx = all_nums.index(article_num)
        prev_num = all_nums[idx - 1] if idx > 0 else None
        next_num = all_nums[idx + 1] if idx < len(all_nums) - 1 else None
    except:
        prev_num, next_num = None, None

    # パンくずリスト
    breadcrumb = ' &gt; '.join(article.get('path', []))

    html_content = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(article.get("title", ""))}{h(article.get("caption", ""))} - {h(law_data["title"])}</title>
<link rel="stylesheet" href="../../css/law.css">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Legislation",
  "name": "{h(law_data["title"])}",
  "legislationIdentifier": "{h(article_num)}",
  "text": "{h(article.get("title", ""))}"
}}
</script>
</head>
<body>
<div class="container">
  <!-- 左ペイン: 目次 -->
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <a href="index.html" class="law-title">{h(law_data["title"])}</a>
      <input type="text" id="search" placeholder="条文検索..." class="search-box">
    </div>
    <div class="toc" id="toc">
      {generate_toc_html(law_data['toc'], article_num)}
    </div>
  </nav>

  <!-- 右ペイン: 本文 -->
  <main class="content">
    <div class="breadcrumb">{breadcrumb}</div>

    <article class="article" data-num="{h(article_num)}">
      <header class="article-header">
        <h1 class="article-title">{h(article.get("title", ""))}</h1>
        <span class="article-caption">{h(article.get("caption", ""))}</span>
      </header>

      <div class="article-body">
'''

    # 各項を出力
    for para in article.get('paragraphs', []):
        para_num = para.get('num', '')
        para_text = h(para.get('text', ''))

        # 法令参照をリンクに変換（例: 第○条 → リンク）
        para_text = re.sub(
            r'第([一二三四五六七八九十百千]+)条',
            lambda m: f'<a href="{kanji_to_num(m.group(1))}.html" class="law-ref">第{m.group(1)}条</a>',
            para_text
        )

        html_content += f'''
        <div class="paragraph" data-para="{para_num}">
          <span class="para-num">{para_num}</span>
          <p class="para-text">{para_text}</p>
        </div>
'''

    html_content += f'''
      </div>
    </article>

    <nav class="article-nav">
      {'<a href="' + prev_num + '.html" class="prev">← 前条</a>' if prev_num else '<span class="prev disabled">← 前条</span>'}
      <a href="index.html" class="index">目次</a>
      {'<a href="' + next_num + '.html" class="next">次条 →</a>' if next_num else '<span class="next disabled">次条 →</span>'}
    </nav>
  </main>
</div>
<script src="../../js/law.js"></script>
</body>
</html>
'''
    return html_content


def kanji_to_num(kanji: str) -> str:
    """漢数字を算用数字に変換"""
    kanji_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                  '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
                  '百': 100, '千': 1000}

    result = 0
    current = 0

    for char in kanji:
        if char in kanji_nums:
            val = kanji_nums[char]
            if val >= 10:
                if current == 0:
                    current = 1
                result += current * val
                current = 0
            else:
                current = val

    result += current
    return str(result) if result > 0 else kanji


def generate_toc_html(toc: list, current_num: str = None, level: int = 0) -> str:
    """目次HTMLを生成"""
    h = html.escape
    html_parts = []

    for item in toc:
        item_type = item.get('type', '')

        if item_type == 'article':
            num = item.get('num', '')
            caption = item.get('caption', '')
            title = item.get('title', '')
            is_current = num == current_num

            html_parts.append(
                f'<a href="{num}.html" class="toc-article{"  current" if is_current else ""}">'
                f'<span class="toc-num">{h(title)}</span>'
                f'<span class="toc-caption">{h(caption)}</span></a>'
            )
        else:
            title = item.get('title', '')
            children = item.get('children', [])
            type_class = f'toc-{item_type}'

            html_parts.append(f'<div class="{type_class}">')
            html_parts.append(f'<div class="toc-heading">{h(title)}</div>')
            if children:
                html_parts.append(f'<div class="toc-children">{generate_toc_html(children, current_num, level + 1)}</div>')
            html_parts.append('</div>')

    return '\n'.join(html_parts)


def generate_index_html(law_data: dict, law_code: str) -> str:
    """目次ページHTMLを生成"""
    h = html.escape

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(law_data["title"])} - 目次</title>
<link rel="stylesheet" href="../../css/law.css">
</head>
<body>
<div class="container">
  <nav class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <a href="../../index.html" class="back-link">← 法令一覧</a>
      <h1 class="law-title">{h(law_data["title"])}</h1>
      <p class="law-number">{h(law_data["number"])}</p>
      <input type="text" id="search" placeholder="条文検索..." class="search-box">
    </div>
    <div class="toc" id="toc">
      {generate_toc_html(law_data['toc'])}
    </div>
  </nav>

  <main class="content index-content">
    <h1>{h(law_data["title"])}</h1>
    <p class="law-number">{h(law_data["number"])}</p>

    <div class="stats">
      <p>全 <strong>{len(law_data["articles"])}</strong> 条</p>
    </div>

    <div class="quick-access">
      <h2>条文へのクイックアクセス</h2>
      <div class="article-grid">
        {generate_article_grid(law_data)}
      </div>
    </div>
  </main>
</div>
<script src="../../js/law.js"></script>
</body>
</html>
'''


def generate_article_grid(law_data: dict) -> str:
    """条文グリッドを生成"""
    h = html.escape
    nums = sorted(law_data['articles'].keys(), key=sort_article_num)

    html_parts = []
    for num in nums[:100]:  # 最初の100条
        article = law_data['articles'][num]
        caption = article.get('caption', '')
        html_parts.append(f'<a href="{num}.html" class="grid-item" title="{h(caption)}">{h(num)}</a>')

    if len(nums) > 100:
        html_parts.append(f'<span class="grid-more">... 他{len(nums) - 100}条</span>')

    return '\n'.join(html_parts)


def generate_css() -> str:
    """CSSファイルを生成"""
    return '''
:root {
  --primary: #1a365d;
  --secondary: #2c5282;
  --accent: #3182ce;
  --bg: #f7fafc;
  --sidebar-bg: #fff;
  --border: #e2e8f0;
  --text: #2d3748;
  --text-light: #718096;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.8;
}

.container {
  display: flex;
  min-height: 100vh;
}

/* 左ペイン: サイドバー */
.sidebar {
  width: 320px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: fixed;
  height: 100vh;
  overflow: hidden;
}

.sidebar-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
}

.law-title {
  display: block;
  font-size: 1.1rem;
  font-weight: bold;
  color: var(--primary);
  text-decoration: none;
  margin-bottom: 0.5rem;
}

.back-link {
  display: block;
  font-size: 0.85rem;
  color: var(--accent);
  text-decoration: none;
  margin-bottom: 0.5rem;
}

.law-number {
  font-size: 0.85rem;
  color: var(--text-light);
}

.search-box {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  margin-top: 0.5rem;
  font-size: 0.9rem;
}

.toc {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.toc-part, .toc-chapter, .toc-section, .toc-subsection {
  margin-bottom: 0.25rem;
}

.toc-heading {
  padding: 0.5rem;
  font-weight: bold;
  font-size: 0.9rem;
  background: var(--bg);
  border-radius: 4px;
  cursor: pointer;
}

.toc-part > .toc-heading { color: var(--primary); }
.toc-chapter > .toc-heading { color: var(--secondary); font-size: 0.85rem; }
.toc-section > .toc-heading { font-size: 0.8rem; font-weight: normal; }

.toc-children {
  padding-left: 0.75rem;
  border-left: 2px solid var(--border);
  margin-left: 0.5rem;
}

.toc-article {
  display: block;
  padding: 0.4rem 0.5rem;
  text-decoration: none;
  color: var(--text);
  font-size: 0.85rem;
  border-radius: 4px;
  transition: background 0.2s;
}

.toc-article:hover { background: var(--bg); }
.toc-article.current { background: var(--accent); color: white; }

.toc-num { font-weight: bold; }
.toc-caption {
  display: block;
  font-size: 0.75rem;
  color: var(--text-light);
}
.toc-article.current .toc-caption { color: rgba(255,255,255,0.8); }

/* 右ペイン: コンテンツ */
.content {
  flex: 1;
  margin-left: 320px;
  padding: 2rem;
  max-width: 900px;
}

.breadcrumb {
  font-size: 0.85rem;
  color: var(--text-light);
  margin-bottom: 1rem;
}

.article {
  background: white;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.article-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid var(--primary);
}

.article-title {
  font-size: 1.5rem;
  color: var(--primary);
}

.article-caption {
  font-size: 1rem;
  color: var(--text-light);
}

.paragraph {
  margin: 1rem 0;
  padding-left: 2rem;
  position: relative;
}

.para-num {
  position: absolute;
  left: 0;
  font-weight: bold;
  color: var(--accent);
}

.para-text {
  text-align: justify;
}

.law-ref {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px dotted var(--accent);
}

.law-ref:hover {
  background: rgba(49, 130, 206, 0.1);
}

.article-nav {
  display: flex;
  justify-content: space-between;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}

.article-nav a, .article-nav span {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
}

.article-nav a {
  background: var(--accent);
  color: white;
}

.article-nav a:hover { background: var(--secondary); }

.article-nav .disabled {
  background: var(--border);
  color: var(--text-light);
}

/* 目次ページ */
.index-content h1 {
  color: var(--primary);
  margin-bottom: 0.5rem;
}

.stats {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg);
  border-radius: 8px;
}

.quick-access { margin-top: 2rem; }
.quick-access h2 { margin-bottom: 1rem; font-size: 1.2rem; }

.article-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(50px, 1fr));
  gap: 0.5rem;
}

.grid-item {
  padding: 0.5rem;
  text-align: center;
  background: white;
  border: 1px solid var(--border);
  border-radius: 4px;
  text-decoration: none;
  color: var(--text);
  font-size: 0.85rem;
}

.grid-item:hover { background: var(--accent); color: white; }

/* レスポンシブ */
@media (max-width: 768px) {
  .sidebar {
    width: 100%;
    position: relative;
    height: auto;
    max-height: 50vh;
  }
  .content { margin-left: 0; }
  .container { flex-direction: column; }
}
'''


def generate_js() -> str:
    """JavaScriptファイルを生成"""
    return '''
// 条文検索
document.getElementById('search')?.addEventListener('input', function(e) {
  const query = e.target.value.toLowerCase();
  const articles = document.querySelectorAll('.toc-article');

  articles.forEach(article => {
    const text = article.textContent.toLowerCase();
    article.style.display = text.includes(query) ? '' : 'none';
  });
});

// 目次の折りたたみ
document.querySelectorAll('.toc-heading').forEach(heading => {
  heading.addEventListener('click', function() {
    const children = this.nextElementSibling;
    if (children && children.classList.contains('toc-children')) {
      children.style.display = children.style.display === 'none' ? '' : 'none';
    }
  });
});

// 現在の条文をビューに表示
document.querySelector('.toc-article.current')?.scrollIntoView({
  behavior: 'smooth',
  block: 'center'
});
'''


def main():
    parser = argparse.ArgumentParser(description='法令XMLからサイトを生成')
    parser.add_argument('input', help='入力XMLファイル')
    parser.add_argument('--output', '-o', required=True, help='出力ディレクトリ')
    parser.add_argument('--code', '-c', default='law', help='法令コード')

    args = parser.parse_args()

    print(f"解析中: {args.input}")
    law_data = parse_law_structure(args.input)

    print(f"法令名: {law_data['title']}")
    print(f"条文数: {len(law_data['articles'])}")

    # 出力ディレクトリ作成
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(os.path.dirname(args.output.rstrip('/')) + '/../css', exist_ok=True)
    os.makedirs(os.path.dirname(args.output.rstrip('/')) + '/../js', exist_ok=True)

    # CSS/JS生成
    css_path = os.path.dirname(args.output.rstrip('/')) + '/../css/law.css'
    js_path = os.path.dirname(args.output.rstrip('/')) + '/../js/law.js'

    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(generate_css())
    print(f"CSS生成: {css_path}")

    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(generate_js())
    print(f"JS生成: {js_path}")

    # 目次ページ生成
    index_html = generate_index_html(law_data, args.code)
    with open(os.path.join(args.output, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    print(f"目次生成: {args.output}/index.html")

    # 各条文ページ生成
    count = 0
    for num in law_data['articles']:
        article_html = generate_article_html(law_data, num, args.code)
        if article_html:
            filepath = os.path.join(args.output, f'{num}.html')
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(article_html)
            count += 1

    print(f"条文ページ生成: {count}件")
    print("完了!")


if __name__ == '__main__':
    main()
