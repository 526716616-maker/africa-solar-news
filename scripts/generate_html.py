"""
非洲离网太阳能市场资讯 - HTML 生成器
=====================================
将结构化新闻数据 + 点评渲染为资讯 HTML 页面。

输入格式 (data.json):
{
  "week": "2026-W24",
  "date": "2026-06-08",
  "issue": 23,
  "highlights": [
    {"num": "1000万+", "label": "年销售套数"},
    {"num": "1.5亿", "label": "累计服务人口"}
  ],
  "sections": [
    {
      "title": "一、行业动态",
      "items": [
        {
          "tag": "GOGLA · 市场报告",
          "title": "...",
          "summary": "...",
          "bullets": ["...", "..."],
          "source": "GOGLA Newsroom",
          "source_url": "https://...",
          "date": "2026-06-03"
        }
      ]
    },
    {
      "title": "二、重点企业动态",
      "companies": [
        {
          "icon": "MY",
          "name": "MySol / ENGIE Energy Access",
          "description": "..."
        }
      ]
    }
  ]
}

用法:
    python generate_html.py data.json > weekly.html
    python generate_html.py data.json -o output/week23.html
"""

import json
import os
import sys
from datetime import datetime


CSS = """\
/* ===== 非洲离网太阳能市场资讯 - 样式 ===== */
:root {
  --bg: #f8f9fa;
  --card: #ffffff;
  --text: #1a1a2e;
  --text-secondary: #555770;
  --text-tertiary: #8e8ea0;
  --border: #e8e8ee;
  --green-dark: #0F6E56;
  --green-light: #1D9E75;
  --green-bg: #E1F5EE;
  --green-tag-bg: rgba(15,110,86,0.08);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.container {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px 20px 48px;
}

/* ===== Header ===== */
.header {
  background: var(--green-dark);
  color: #fff;
  padding: 28px 28px 22px;
  border-radius: var(--radius-lg);
  margin-bottom: 24px;
}
.header h1 {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 2px;
  letter-spacing: -0.01em;
}
.header .subtitle {
  font-size: 13px;
  opacity: 0.78;
  font-weight: 400;
}
.header .meta {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.header .meta span {
  background: rgba(255,255,255,0.15);
  border-radius: var(--radius-sm);
  padding: 3px 10px;
  font-size: 11px;
  letter-spacing: 0.02em;
}

/* ===== Stats Row ===== */
.section-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 28px 0 10px;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 8px;
}
.stat-box {
  background: var(--card);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 12px;
  text-align: center;
}
.stat-box .num {
  font-size: 20px;
  font-weight: 700;
  color: var(--green-dark);
  margin-bottom: 4px;
}
.stat-box .lbl {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.3;
}
@media (max-width: 560px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
}

/* ===== News Card ===== */
.news-card {
  background: var(--card);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 18px;
  margin-bottom: 12px;
  transition: border-color 0.15s;
}
.news-card:hover { border-color: var(--green-light); }
.news-card .tag {
  display: inline-block;
  background: var(--green-tag-bg);
  color: var(--green-dark);
  font-size: 11px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 100px;
  margin-bottom: 10px;
}
.news-card h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text);
}
.news-card .summary {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.news-card .bullets {
  list-style: none;
  margin-bottom: 10px;
}
.news-card .bullets li {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 2px 0 2px 16px;
  position: relative;
}
.news-card .bullets li::before {
  content: "";
  position: absolute;
  left: 2px;
  top: 9px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--green-light);
}
.news-card .source {
  font-size: 11px;
  color: var(--text-tertiary);
}
.news-card .source a {
  color: var(--green-dark);
  text-decoration: none;
}
.news-card .source a:hover { text-decoration: underline; }

/* ===== Company Card ===== */
.company-card {
  background: var(--card);
  border: 0.5px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 16px 18px;
  margin-bottom: 12px;
  transition: border-color 0.15s;
}
.company-card:hover { border-color: var(--green-light); }
.company-card .tag {
  display: inline-block;
  background: var(--green-tag-bg);
  color: var(--green-dark);
  font-size: 11px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 100px;
  margin-bottom: 10px;
}
.company-card h3 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text);
}
.company-card p {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.company-card .source {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 8px;
}
.company-card .source a {
  color: var(--green-dark);
  text-decoration: none;
}
.company-card .source a:hover { text-decoration: underline; }

/* ===== Footer ===== */
.footer {
  text-align: center;
  font-size: 11px;
  color: var(--text-tertiary);
  border-top: 0.5px solid var(--border);
  padding-top: 20px;
  margin-top: 32px;
}
"""


def generate_html(data: dict) -> str:
    """根据数据字典生成完整 HTML"""

    week = data.get("week", "")
    date_str = data.get("date", "")
    issue = data.get("issue", "")
    highlights = data.get("highlights", [])
    sections = data.get("sections", [])

    # 拼装统计卡片
    stats_html = ""
    for h in highlights:
        stats_html += f'<div class="stat-box"><div class="num">{h["num"]}</div><div class="lbl">{h["label"]}</div></div>'

    # 拼装各板块
    sections_html = ""
    for sec in sections:
        sections_html += f'<div class="section-title">{sec["title"]}</div>\n'

        # 行业新闻卡片
        for item in sec.get("items", []):
            tag = item.get("tag", "")
            title = item.get("title", "")
            summary = item.get("summary", "")
            bullets = item.get("bullets", [])
            source = item.get("source", "")
            source_url = item.get("source_url", "")
            item_date = item.get("date", "")

            source_date = f"{source}"
            if item_date:
                source_date += f" · {item_date}"

            bullets_html = ""
            if bullets:
                bullets_html = '<ul class="bullets">'
                for b in bullets:
                    bullets_html += f"<li>{b}</li>"
                bullets_html += "</ul>"

            source_line = ""
            if source:
                if source_url:
                    source_line = f'<div class="source">来源：<a href="{source_url}" target="_blank" rel="noopener">{source_date}</a></div>'
                else:
                    source_line = f'<div class="source">来源：{source_date}</div>'

            tag_html = f'<span class="tag">{tag}</span>' if tag else ""

            sections_html += f"""\
<div class="news-card">
  {tag_html}
  <h3>{title}</h3>
  <p class="summary">{summary}</p>
  {bullets_html}
  {source_line}
</div>
"""

        # 企业卡片
        for company in sec.get("companies", []):
            name = company.get("name", "")
            desc = company.get("description", "")
            tag = company.get("tag", "企业动态")
            source = company.get("source", "")
            source_url = company.get("source_url", "")
            source_line = ""
            if source and source_url:
                source_line = f'<div class="source">来源：<a href="{source_url}" target="_blank" rel="noopener">{source}</a></div>'
            elif source:
                source_line = f'<div class="source">来源：{source}</div>'

            sections_html += f"""\
<div class="company-card">
  <span class="tag">{tag}</span>
  <h3>{name}</h3>
  <p>{desc}</p>
  {source_line}
</div>
"""

    issue_info = f"第 {issue} 期" if issue else ""
    date_info = date_str

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>非洲离网太阳能市场资讯 {date_info} {issue_info}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Africa Off-Grid Solar Market News</h1>
    <p class="subtitle">非洲离网太阳能市场资讯</p>
    <div class="meta">
      <span>{issue_info}</span>
      <span>{date_info}</span>
      <span>行业动态 · 企业跟踪</span>
    </div>
  </div>

  <div class="section-title">本期数据亮点</div>
  <div class="stats-row">{stats_html}</div>

  {sections_html}

  <div class="footer">
    Africa Solar News · {date_info} · 每日更新
  </div>

</div>
</body>
</html>"""


def main():
    import argparse

    parser = argparse.ArgumentParser(description="周报 HTML 生成器")
    parser.add_argument("data", help="JSON 数据文件路径")
    parser.add_argument("-o", "--output", help="输出 HTML 文件路径")
    parser.add_argument("--stdout", action="store_true", help="输出到 stdout")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = generate_html(data)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[OK] 已生成: {args.output}")
    else:
        print(html)


if __name__ == "__main__":
    main()
