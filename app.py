import streamlit as st
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from datetime import datetime, timezone
import email.utils
import json
import os
import hashlib

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="行业情报系统",
    page_icon="🛰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }
header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# ★ 数据源配置 ★
# 想增加监控源，在这里添加即可：
#
# RSS 源（有标准 RSS/Atom feed 的网站）：
#   格式：  "显示名称": "RSS地址",
#   例如：  "Dezeen": "https://www.dezeen.com/feed/",
#
# 爬虫源（没有 RSS，直接抓网页的网站）：
#   格式：  "显示名称": "网站地址",
#   例如：  "某网站": "https://www.example.com/news/",
#   注意：爬虫依赖 h2/h3 标签结构，部分网站可能抓不到内容
# ============================================================
RSS_FEEDS = {
    "House News":           "https://www.housenews.jp/rss",
    "Reform Online":        "https://www.reform-online.jp/rss",
    "KBB Review":           "https://www.kbbreview.com/feed/",
    "Kitchen & Bath Design":"https://www.kitchenbathdesign.com/feed/",
    "SupplyHT":             "https://www.supplyht.com/rss",
}

SCRAPE_SITES = {
    "SanitaerNews": "https://www.sanitaernews.de/",
    "SDBPRO":       "https://www.sdbpro.fr/industrie/",
}
# ============================================================

IMPORTANCE_KEYWORDS = [
    "launch", "new", "innovation", "trend", "report", "growth", "market",
    "发布", "新品", "创新", "趋势", "报告", "增长", "市场", "突破",
    "acquisition", "partner", "breakthrough", "exclusive", "首发", "独家"
]

# ============================================================
# 磁盘缓存（跨会话持久化）
# ============================================================
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".intel_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def cache_path(key):
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")

def cache_get(key, ttl=3600):
    p = cache_path(key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if datetime.now().timestamp() - data["ts"] > ttl:
            return None
        return data["value"]
    except:
        return None

def cache_set(key, value):
    p = cache_path(key)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"ts": datetime.now().timestamp(), "value": value}, f, ensure_ascii=False)
    except:
        pass

# ============================================================
# 工具函数
# ============================================================
def translate_text(text):
    if not text:
        return text
    cached = cache_get(f"tr:{text[:100]}", ttl=86400 * 7)
    if cached:
        return cached
    try:
        result = GoogleTranslator(source='auto', target='zh-CN').translate(text)
        cache_set(f"tr:{text[:100]}", result)
        return result
    except:
        return text

def parse_time(entry):
    for field in ['published_parsed', 'updated_parsed']:
        if hasattr(entry, field) and getattr(entry, field):
            t = getattr(entry, field)
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except:
                pass
    for field in ['published', 'updated']:
        if hasattr(entry, field):
            try:
                parsed = email.utils.parsedate(getattr(entry, field))
                if parsed:
                    return datetime(*parsed[:6], tzinfo=timezone.utc)
            except:
                pass
    return None

def format_time(dt):
    """显示完整发布时间，格式：2025-03-18 14:30"""
    if not dt:
        return "时间未知"
    return dt.strftime("%Y-%m-%d %H:%M")

def importance_score(title):
    score = 0
    title_lower = title.lower()
    for kw in IMPORTANCE_KEYWORDS:
        if kw.lower() in title_lower:
            score += 1
    return score

def load_rss(name, url):
    articles = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            dt = parse_time(entry)
            raw_summary = ""
            if hasattr(entry, 'summary'):
                raw_summary = BeautifulSoup(entry.summary, "html.parser").get_text()[:300]
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "source": name,
                "dt": dt.isoformat() if dt else None,
                "raw_summary": raw_summary
            })
    except:
        pass
    return articles

def scrape_site(name, url):
    articles = []
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("h2 a, h3 a, .title a, article a"):
            title = a.get_text().strip()
            link = a.get("href")
            if title and link and len(title) > 10:
                if not link.startswith("http"):
                    from urllib.parse import urljoin
                    link = urljoin(url, link)
                articles.append({
                    "title": title,
                    "link": link,
                    "source": name,
                    "dt": None,
                    "raw_summary": ""
                })
            if len(articles) >= 15:
                break
    except:
        pass
    return articles

def get_ai_summary(title, raw_summary, source):
    cache_key = f"ai:{title[:80]}"
    cached = cache_get(cache_key, ttl=86400)
    if cached:
        return cached
    try:
        from anthropic import Anthropic
        client = Anthropic()
        context = f"标题：{title}"
        if raw_summary:
            context += f"\n原文片段：{raw_summary}"
        context += f"\n来源：{source}"
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system="""你是专注于建筑、卫浴、厨房、装修行业的情报分析师。
根据文章标题和摘要，用2-3句话提炼核心事件/信息点，以及对行业的潜在影响（如有）。
语言简洁精准，中文输出，直接说核心内容，不要用"本文"、"这篇文章"等字样。""",
            messages=[{"role": "user", "content": context}]
        )
        result = msg.content[0].text.strip()
        cache_set(cache_key, result)
        return result
    except:
        return translate_text(title)[:120]

# ============================================================
# 采集数据（内存缓存30分钟，重开网页不重新抓取）
# ============================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_all_articles():
    all_articles = []
    for name, url in RSS_FEEDS.items():
        all_articles.extend(load_rss(name, url))
    for name, url in SCRAPE_SITES.items():
        all_articles.extend(scrape_site(name, url))
    seen = {}
    for a in all_articles:
        key = a["title"].strip()[:50]
        if key not in seen:
            seen[key] = a
    result = list(seen.values())
    for a in result:
        a["title_cn"] = translate_text(a["title"])
        a["importance"] = importance_score(a["title_cn"] + a["title"])
    return result

# ============================================================
# 界面
# ============================================================
st.title("🛰 行业情报系统")
st.caption("KITCHEN · BATH · REFORM · SUPPLY · DESIGN INTELLIGENCE")
st.divider()

# 顶部控制栏（替代侧边栏）
col_sort, col_count, col_ai, col_refresh = st.columns([2, 1, 2, 1])
with col_sort:
    sort_mode = st.selectbox("排序方式", ["时间优先", "重要性优先", "综合排序"], label_visibility="collapsed")
with col_count:
    show_count = st.selectbox("显示数量", [20, 30, 50], label_visibility="collapsed")
with col_ai:
    enable_ai = st.checkbox("启用 AI 深度摘要（需配置 API Key）", value=False)
with col_refresh:
    if st.button("🔄 刷新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# 加载数据
with st.spinner("加载情报数据..."):
    articles = fetch_all_articles()

# 排序
def sort_key(a):
    dt_str = a.get('dt')
    ts = 0
    if dt_str:
        try:
            ts = datetime.fromisoformat(dt_str).timestamp()
        except:
            pass
    imp = a.get('importance', 0)
    if sort_mode == "时间优先":
        return (-ts, -imp)
    elif sort_mode == "重要性优先":
        return (-imp, -ts)
    else:
        return (-(ts / 1e9 * 0.6 + imp * 0.4))

articles.sort(key=sort_key)

# 统计
with_time = sum(1 for a in articles if a.get('dt'))
c1, c2, c3 = st.columns(3)
c1.metric("情报总数", len(articles))
c2.metric("监控源", len(RSS_FEEDS) + len(SCRAPE_SITES))
c3.metric("有发布时间", with_time)

st.divider()
st.caption(f"显示前 {min(show_count, len(articles))} 条，共 {len(articles)} 条")

# 文章列表
for a in articles[:show_count]:
    title_cn = a.get('title_cn', a['title'])
    dt_str = a.get('dt')
    dt = None
    if dt_str:
        try:
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        except:
            pass
    time_str = format_time(dt)

    with st.container(border=True):
        col_src, col_time = st.columns([2, 3])
        col_src.markdown(f"`{a['source']}`")
        col_time.caption(f"🕐 {time_str}")

        st.markdown(f"**[{title_cn}]({a['link']})**")

        # 摘要：直接显示，无标签
        if enable_ai:
            with st.spinner(""):
                summary = get_ai_summary(a['title'], a.get('raw_summary', ''), a['source'])
        else:
            raw = a.get('raw_summary', '')
            summary = (translate_text(raw)[:200] + "...") if raw else ""

        if summary:
            st.caption(summary)

if len(articles) > show_count:
    st.caption(f"已显示 {show_count} / {len(articles)} 条")
