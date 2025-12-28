#!/usr/bin/env python3
"""
index.jsonからindex.htmlを生成
"""

import os
import json
import html as html_module

CSS = """
body {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: "Hiragino Kaku Gothic Pro", "Yu Gothic", sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  background: #fafafa;
}
h1 { font-size: 1.4em; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }
table { width: 100%; border-collapse: collapse; margin-top: 20px; }
th, td { padding: 8px 6px; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
th { background: #1e40af; color: white; font-weight: bold; position: sticky; top: 0; }
tr:hover { background: #f0f9ff; }
.result-棄却 { color: #dc2626; }
.result-認容 { color: #16a34a; }
.result-一部認容 { color: #ca8a04; }
.result-取消 { color: #2563eb; }
.result-却下 { color: #6b7280; }
.tax-tag { display: inline-block; padding: 2px 6px; margin: 1px; border-radius: 3px; font-size: 11px; }
.tax-所得税 { background: #dbeafe; color: #1e40af; }
.tax-法人税 { background: #dcfce7; color: #166534; }
.tax-消費税 { background: #fef9c3; color: #854d0e; }
.tax-相続税 { background: #fce7f3; color: #9d174d; }
.tax-贈与税 { background: #f3e8ff; color: #6b21a8; }
.tax-印紙税 { background: #fee2e2; color: #991b1b; }
.tax-国税徴収 { background: #e0e7ff; color: #3730a3; }
td.issues { font-size: 12px; color: #666; max-width: 200px; }
td.provisions { font-size: 11px; color: #888; max-width: 180px; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
.stats { margin: 15px 0; padding: 12px; background: #e0f2fe; border-radius: 6px; }
.stats span { margin-right: 20px; }
.filter { margin: 15px 0; }
.filter select { padding: 6px 12px; margin-right: 10px; border: 1px solid #ccc; border-radius: 4px; }
"""

JS = """
function filterTable() {
  var taxType = document.getElementById('taxFilter').value;
  var result = document.getElementById('resultFilter').value;
  var rows = document.querySelectorAll('tbody tr');

  rows.forEach(function(row) {
    var taxCell = row.cells[2].textContent;
    var resultCell = row.cells[5].textContent;
    var showTax = !taxType || taxCell.includes(taxType);
    var showResult = !result || resultCell === result;
    row.style.display = (showTax && showResult) ? '' : 'none';
  });
}
"""


def generate_index_html(cases: list, title: str) -> str:
    h = html_module.escape

    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="ja">')
    lines.append('<head>')
    lines.append('<meta charset="UTF-8">')
    lines.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    lines.append(f'<title>{h(title)} - 目次</title>')
    lines.append(f'<style>{CSS}</style>')
    lines.append('</head>')
    lines.append('<body>')
    lines.append(f'<h1>{h(title)}</h1>')

    # 統計
    tax_stats = {}
    result_stats = {}
    for case in cases:
        for tax in case.get('tax_type', []):
            if not tax.startswith('（'):  # マーカーは除外
                tax_stats[tax] = tax_stats.get(tax, 0) + 1
        r = case.get('result', '')
        if r:
            result_stats[r] = result_stats.get(r, 0) + 1

    lines.append('<div class="stats">')
    lines.append(f'<span><strong>判決数:</strong> {len(cases)}件</span>')
    for tax, count in sorted(tax_stats.items(), key=lambda x: -x[1])[:5]:
        lines.append(f'<span class="tax-tag tax-{tax}">{tax}: {count}件</span>')
    lines.append('</div>')

    # フィルター
    lines.append('<div class="filter">')
    lines.append('<select id="taxFilter" onchange="filterTable()">')
    lines.append('<option value="">全税目</option>')
    for tax in sorted(tax_stats.keys()):
        lines.append(f'<option value="{tax}">{tax}</option>')
    lines.append('</select>')
    lines.append('<select id="resultFilter" onchange="filterTable()">')
    lines.append('<option value="">全結果</option>')
    for r in sorted(result_stats.keys()):
        lines.append(f'<option value="{r}">{r}</option>')
    lines.append('</select>')
    lines.append('</div>')

    # テーブル
    lines.append('<table>')
    lines.append('<thead>')
    lines.append('<tr><th>番号</th><th>事件名</th><th>税目</th><th>争点</th><th>日付</th><th>結果</th></tr>')
    lines.append('</thead>')
    lines.append('<tbody>')

    for case in sorted(cases, key=lambda x: x.get('number', '')):
        num = case.get('number', 'unknown')
        title = case.get('title', '')[:50]
        court = case.get('court', '')
        date = case.get('date', '')
        result = case.get('result', '')
        result_class = f'result-{result}' if result else ''
        tax_types = case.get('tax_type', [])
        issues = case.get('issue', [])

        # 税目タグ（マーカーは除外）
        tax_html = ' '.join([f'<span class="tax-tag tax-{t}">{t}</span>' for t in tax_types if not t.startswith('（')])

        # 争点（最大2つ、マーカーは表示）
        display_issues = [i for i in issues if not i.startswith('（')][:2]
        if not display_issues and issues:
            display_issues = issues[:1]  # マーカーのみの場合は表示
        issues_text = ', '.join(display_issues)
        if len([i for i in issues if not i.startswith('（')]) > 2:
            issues_text += '...'

        lines.append('<tr>')
        lines.append(f'<td><a href="{num}.html">{h(num)}</a></td>')
        lines.append(f'<td>{h(title)}</td>')
        lines.append(f'<td>{tax_html}</td>')
        lines.append(f'<td class="issues">{h(issues_text)}</td>')
        lines.append(f'<td>{h(date)}</td>')
        lines.append(f'<td class="{result_class}">{h(result)}</td>')
        lines.append('</tr>')

    lines.append('</tbody>')
    lines.append('</table>')
    lines.append(f'<script>{JS}</script>')
    lines.append('</body>')
    lines.append('</html>')

    return '\n'.join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='index.htmlを生成')
    parser.add_argument('--html-dir', default='/home/user/ai-law-db/simple/hanketsu/2023', help='HTMLディレクトリ')
    parser.add_argument('--title', default='国税庁判決事例集', help='タイトル')
    args = parser.parse_args()

    html_dir = args.html_dir
    title = args.title

    with open(os.path.join(html_dir, 'index.json'), 'r', encoding='utf-8') as f:
        cases = json.load(f)

    index_html = generate_index_html(cases, title)

    with open(os.path.join(html_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f'index.html 更新完了 ({len(cases)}件)')


if __name__ == '__main__':
    main()
