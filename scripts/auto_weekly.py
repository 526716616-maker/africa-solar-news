"""全自动：抓取 raw JSON → 翻译为中文 → 生成资讯 HTML"""
import json
import os
import sys
import re
import time
from datetime import datetime, timezone
from deep_translator import GoogleTranslator

CST = timezone(__import__('datetime').timedelta(hours=8))

# ── 翻译 ──
_translator = None
_cache = {}

def get_translator():
    global _translator
    if _translator is None:
        _translator = GoogleTranslator(source='auto', target='zh-CN')
    return _translator

def translate_text(text: str, retries: int = 2) -> str:
    """翻译文本为中文，短文本跳过，失败返回原文"""
    if not text or len(text.strip()) < 5:
        return text
    if text in _cache:
        return _cache[text]
    # 纯中文/数字跳过
    if re.match(r'^[\u4e00-\u9fff\d\s\.\,\;\:\!\?\-\+]+$', text.strip()):
        return text
    for attempt in range(retries + 1):
        try:
            result = get_translator().translate(text)
            _cache[text] = result
            return result
        except Exception as e:
            if attempt < retries:
                print(f"  [retry] 翻译重试 {attempt+1}: {e}", file=sys.stderr)
                time.sleep(2)
            else:
                print(f"  [warn] 翻译失败: {e}", file=sys.stderr)
                return text

# ── 读取 raw JSON（自动找最新的） ──
raw_dir = os.path.join(os.path.dirname(__file__), "..", "output", "raw")
raw_dir = os.path.abspath(raw_dir)
raw_files = sorted([
    f for f in os.listdir(raw_dir)
    if f.endswith("-raw.json") and not f.startswith("latest")
], reverse=True)
if not raw_files:
    print("[ERROR] 没有找到 raw JSON 文件", file=sys.stderr)
    sys.exit(1)
raw_path = os.path.join(raw_dir, raw_files[0])
print(f"[INFO] 读取: {raw_files[0]}")
with open(raw_path, "r", encoding="utf-8") as f:
    raw = json.load(f)

# ── 自动计算期号 ──
html_dir = os.path.join(os.path.dirname(__file__), "..", "output", "html")
existing = [f for f in os.listdir(os.path.abspath(html_dir)) if f.startswith("week-") and f.endswith(".html")]
issue_num = len(existing) + 1

now = datetime.now(CST)

# ── 清洗工具 ──
def clean_summary(text: str, max_len: int = 300) -> str:
    """清洗 RSS/HTML 摘要：去标签、去垃圾文字、截断"""
    # 去掉 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 去掉多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 去掉 RSS 尾巴文字
    text = re.sub(r'The post .*? appeared first on .*?\.?$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'The post .*?$', '', text, flags=re.IGNORECASE)
    # 去掉结尾不完整的句子（截断在非句末处）
    text = text.strip()
    if text and text[-1] not in '.。!！?？':
        # 找最后一个完整句号
        last_period = max(text.rfind('. '), text.rfind('。'), text.rfind('! '), text.rfind('? '))
        if last_period > len(text) * 0.5:  # 至少过半
            text = text[:last_period+1]
    return text[:max_len].strip()
def extract_numbers(text):
    """从文本中提取有意义的数字，返回列表"""
    nums = []
    patterns = [
        r'(\d+[\d,.]*\s*(?:million|billion|MW|GW|kits|people))',
        r'(\$\d+[\d,.]*\s*(?:billion|million))',
        r'(\d+[\d,.]*\s*(?:MW|GW))',
    ]
    seen = set()
    for pat in patterns:
        for m in re.findall(pat, text, re.IGNORECASE):
            clean = m.strip()
            if clean not in seen:
                nums.append(clean)
                seen.add(clean)
    return nums

all_nums = []
all_titles_for_nums = ""
for src in raw["sources"]:
    for a in src["articles"]:
        all_titles_for_nums += a["title"] + " " + a.get("summary", "") + " "

# 手工补充本期明显的数字
highlights = [
    {"num": "500 MW", "label": "韩国提案赞比亚光伏项目"},
    {"num": "1亿", "label": "Ignite 2030年连接目标"},
    {"num": "1000万套", "label": "2025年离网太阳能销量"},
    {"num": "$210亿", "label": "离网太阳能投资缺口"},
]

# ── 分配文章到板块 ──
industry_items = []  # 一、行业动态
company_items = []   # 二、企业动态

# 记录每个源已分配的文章数（无日期的源限制3篇）
source_count = {}

for src in raw["sources"]:
    for a in src["articles"]:
        title = a["title"]
        summary = a.get("summary", "")[:300] if a.get("summary") else ""
        url = a.get("url", "")
        date = a.get("date", "")

        # 只保留最近7天的资讯（无日期的保留，有日期但超7天则过滤）
        cutoff_7d = (datetime.now(CST) - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d")
        if date and date < cutoff_7d:
            continue
        # 无日期的源每源最多3篇
        src_key = src["key"]
        if not date:
            source_count.setdefault(src_key, 0)
            if source_count[src_key] >= 3:
                continue
            source_count[src_key] += 1
        # 过滤无关内容
        skip_keywords = ["south asia", "flutterwave", "series e"]
        if any(kw in title.lower() for kw in skip_keywords):
            continue

        # 根据来源分类
        company_sources = {"engie", "sunking", "bboxx"}
        company_keywords = [
            "ignite power", "ignite energy", "sun king", "sunking",
            "bboxx", "d.light", "dlight", "m-kopa", "mkopa",
            "zola electric", "husk power", "nuru energy",
            "easy solar", "greenlight planet", "azuri tech",
            "solarnow", "one power", "mobisol", "fenix intl",
        ]

        is_company_article = (
            src["key"] in company_sources
            or any(kw in title.lower() for kw in company_keywords)
            or any(kw in summary.lower() for kw in company_keywords)
        )

        if is_company_article:
            # 企业动态
            if src["key"] == "engie":
                tag_prefix = "企业动态 · Ignite Power"
            elif src["key"] == "sunking":
                tag_prefix = "企业动态 · Sun King"
            elif src["key"] == "bboxx":
                tag_prefix = "企业动态 · BBOXX"
            else:
                tag_prefix = "企业动态"
            company_items.append({
                "tag": tag_prefix,
                "name": title[:100],
                "description": clean_summary(summary, 200) if summary else title[:200],
                "source": src["name"],
                "source_url": url,
                "date": date,
            })
        else:
            # 行业动态
            tag_map = {
                "gogla": "GOGLA · 行业报告",
                "techpoint": "Techpoint · 非洲科技",
                "pv-magazine": "PV Magazine · 太阳能",
                "afsia": "AFSIA · 非洲太阳能",
                "lighting-global": "Lighting Global · 离网照明",
                "bgfa": "BGFA · 离网基金",
                "energynews-africa": "Energy News · 非洲能源",
                "africa-newsroom": "Africa Newsroom · 能源新闻",
                "techcabal-energy": "TechCabal · 能源科技",
            }
            tag = tag_map.get(src["key"], src["name"])

            industry_items.append({
                "tag": tag,
                "title": title[:120],
                "summary": clean_summary(summary),
                "bullets": [],
                "source": src["name"],
                "source_url": url,
                "date": date,
            })

# 如果企业动态不够，从 ENGIE 文章中也加到行业动态
# 不重复添加

# ── 翻译为中文 ──
total_to_translate = len(industry_items) + len(company_items)
print(f"[INFO] 正在翻译 {total_to_translate} 篇文章为中文...")
for item in industry_items:
    item["title"] = translate_text(item["title"])
    item["summary"] = translate_text(item["summary"])
for item in company_items:
    item["name"] = translate_text(item["name"])
    item["description"] = translate_text(item["description"])
print("[INFO] 翻译完成")

# ── 组装 curated JSON ──
curated = {
    "week": raw["week"],
    "date": now.strftime("%Y-%m-%d"),
    "issue": issue_num,
    "highlights": highlights,
    "sections": [],
}

if industry_items:
    curated["sections"].append({
        "title": "一、行业动态",
        "items": industry_items,
    })

if company_items:
    curated["sections"].append({
        "title": "二、重点企业动态",
        "companies": company_items,  # 不限数量，全显示
    })

# ── 保存 curated JSON ──
curated_path = os.path.join(os.path.dirname(__file__), "..", "output", "raw", f"{now.strftime('%Y-%m-%d')}-weekly.json")
curated_path = os.path.abspath(curated_path)
with open(curated_path, "w", encoding="utf-8") as f:
    json.dump(curated, f, ensure_ascii=False, indent=2)
print(f"[OK] curated JSON: {curated_path}")
print(f"  行业动态: {len(industry_items)} 条")
print(f"  企业动态: {len(company_items)} 条")

# ── 生成 HTML ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from generate_html import generate_html
html = generate_html(curated)

html_path = os.path.join(os.path.dirname(__file__), "..", "output", "html", f"week-{issue_num:02d}-{now.strftime('%Y-%m-%d')}.html")
html_path = os.path.abspath(html_path)
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"[OK] HTML: {html_path}")

# ── 同步更新 index.html（自动跳转最新期） ──
latest_name = f"week-{issue_num:02d}-{now.strftime('%Y-%m-%d')}.html"
index_path = os.path.join(os.path.dirname(__file__), "..", "output", "html", "index.html")
index_path = os.path.abspath(index_path)
index_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>非洲离网太阳能市场资讯</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9fa;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}}
.card{{background:#fff;border-radius:14px;padding:40px 32px;text-align:center;max-width:400px;box-shadow:0 1px 3px rgba(0,0,0,0.06)}}
h1{{font-size:18px;color:#0F6E56;margin:0 0 8px}}
p{{font-size:13px;color:#555770;margin:0 0 24px}}
a.btn{{display:inline-block;background:#0F6E56;color:#fff;text-decoration:none;padding:10px 28px;border-radius:8px;font-size:14px;margin:6px}}
a.btn.outline{{background:transparent;color:#0F6E56;border:1px solid #0F6E56}}
</style>
<meta http-equiv="refresh" content="3; url={latest_name}">
</head>
<body>
<div class="card">
  <h1>🌍 非洲离网太阳能市场资讯</h1>
  <p>Africa Off-Grid Solar Market News</p>
  <a class="btn" href="{latest_name}">📰 查看最新期</a>
  <br>
  <a class="btn outline" href="archive.html">📚 查看往期</a>
  <p style="font-size:11px;color:#8e8ea0;margin-top:20px">3 秒后自动跳转...</p>
</div>
</body>
</html>"""
with open(index_path, "w", encoding="utf-8") as f:
    f.write(index_content)
print(f"[OK] index.html: {index_path}")

# ── 同步更新 archive.html（往期目录） ──
from generate_html import generate_archive_html
archive_path = os.path.join(os.path.dirname(__file__), "..", "output", "html", "archive.html")
archive_path = os.path.abspath(archive_path)

# 扫描所有期号 JSON，提取元数据
issues = []
for fname in sorted(os.listdir(os.path.abspath(raw_dir))):
    if not fname.endswith("-weekly.json") or fname.startswith("latest"):
        continue
    path = os.path.join(os.path.abspath(raw_dir), fname)
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    date_str = d.get("date", fname[:10])
    issue_num_2 = d.get("issue", 0)
    ind_count = len(d["sections"][0].get("items", [])) if d.get("sections") else 0
    comp_count = len(d["sections"][1].get("companies", [])) if len(d.get("sections", [])) > 1 else 0
    html_file = f"week-{issue_num_2:02d}-{date_str}.html"
    issues.append({
        "file": html_file,
        "issue": issue_num_2,
        "date": date_str,
        "industry": ind_count,
        "company": comp_count,
    })
# 按日期倒序
issues.sort(key=lambda x: x["date"], reverse=True)

archive_html = generate_archive_html(issues)
with open(archive_path, "w", encoding="utf-8") as f:
    f.write(archive_html)
print(f"[OK] archive.html: {archive_path} ({len(issues)} 期)")
