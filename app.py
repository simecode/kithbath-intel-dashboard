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
import threading
from urllib.parse import urljoin

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
# 增加RSS源：在对应 _RSS 字典加一行  "名称": "RSS完整地址"
# 增加爬虫源：在对应 _SCRAPE 字典加一行  "名称": ("网页地址", "css选择器")
# ============================================================

MEDIA_RSS = {
    "House News":          "https://www.housenews.jp/rss",
    "KBB Review":          "https://www.kbbreview.com/feed/",
    "Woodworking Network": "https://www.woodworkingnetwork.com/rss.xml",
}

MEDIA_SCRAPE = {
    "Reform Online":            ("https://www.reform-online.jp/news/manufacturer/13979.php", "h4 a"),
    "SanitaerNews":             ("https://www.sanitaernews.de/", "h2 a, h3 a"),
    "SDBPRO":                   ("https://www.sdbpro.fr/industrie/", "h2 a, h3 a"),
    "Moebelmarkt":              ("https://www.moebelmarkt.de/news", "h2 a, h3 a"),
    "Alimarket":                ("https://www.alimarket.es/construccion/noticias", "h2 a, h3 a"),
    "El Periodico del Azulejo": ("https://www.elperiodicodelazulejo.es/industria", "h2 a, h3 a"),
    "Building Times AT":        ("https://buildingtimes.at/de/nachrichten", "h2 a, h3 a"),
    "Kitchen & Bath Design":    ("https://www.kitchenbathdesign.com/news/", "h2 a, h3 a"),
    "SupplyHT":                 ("https://www.supplyht.com/topics/2649-plumbing", "h2 a, h3 a"),
    "DIY International":        ("https://www.diyinternational.com/", "h2 a, h3 a"),
    "Ceramic World Web":        ("https://ceramicworldweb.com/index.php/en", "h2 a, h3 a"),
    "Industry ID":              ("https://www.industry.co.id/industri/keramik", "h4 a"),
}

ASSOC_RSS = {
    "Cerameunie": "https://cerameunie.eu/rss",
    "Abceram BR": "https://abceram.org.br/feed",
}

ASSOC_SCRAPE = {
    "VN Ceramic":         ("https://vnceramic.org.vn/", "h2 a, h3 a"),
    "Sanitaerwirtschaft": ("https://www.sanitaerwirtschaft.de/aktuell", "h2 a, h3 a"),
    "CCST":               ("https://ccst.org.tr/haberler", "li a"),
    "CAB Badania":        ("https://cab-badania.pl/en/", "li a"),
    "Apicer PT":          ("https://www.apicer.pt/apicer/pt/noticias", "li a"),
    "REIC Thailand":      ("https://www.reic.or.th/", "li a"),
    "VDMA":               ("https://www.vdma.eu/de/armaturen", "h2 a, h3 a"),
    "Acimac":             ("https://www.acimac.it/news-di-settore/", "h2 a, h3 a"),
}

IMPORTANCE_KEYWORDS = [
    "launch", "new", "innovation", "trend", "report", "growth", "market",
    "发布", "新品", "创新", "趋势", "报告", "增长", "市场", "突破",
    "acquisition", "partner", "breakthrough", "exclusive", "首发", "独家"
]

NAV_WORDS = [
    "home", "about", "contact", "login", "register", "menu", "search",
    "customer area", "apresentação", "เกี่ยวกับเรา", "yönetim",
    "subscribe", "newsletter", "privacy", "terms", "cookie",
    "read more", "lire plus", "mehr lesen", "ver más",
]

# ============================================================
# 持久化存储（文章永久存磁盘，不过期）
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(BASE_DIR, ".intel_store")
CACHE_DIR = os.path.join(BASE_DIR, ".intel_cache")   # 翻译/AI缓存
os.makedirs(STORE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

MEDIA_STORE  = os.path.join(STORE_DIR, "media.json")
ASSOC_STORE  = os.path.join(STORE_DIR, "assoc.json")
UPDATE_STATE = os.path.join(STORE_DIR, "update_state.json")

def store_read(path):
    """从磁盘读取文章列表，不存在返回空列表"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def store_write(path, articles):
    """把文章列表写入磁盘"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_update_state():
    if not os.path.exists(UPDATE_STATE):
        return {}
    try:
        with open(UPDATE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def set_update_state(key, value):
    state = get_update_state()
    state[key] = value
    try:
        with open(UPDATE_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except:
        pass

# ============================================================
# 翻译/AI 磁盘缓存（永久，7天翻译 / 1天AI）
# ============================================================
def cache_path(key):
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")

def cache_get(key, ttl=None):
    p = cache_path(key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if ttl and datetime.now().timestamp() - data["ts"] > ttl:
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

def clean_summary(raw_html):
    if not raw_html:
        return ""
    text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ").strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    clean_lines = []
    for line in lines:
        low = line.lower()
        if len(line) < 20:
            continue
        if low.startswith("by ") or low.startswith("author"):
            continue
        if line.strip() in ("...", "…", "-", "–"):
            continue
        clean_lines.append(line)
    result = " ".join(clean_lines)
    return result[:250] if result else ""

def load_rss(name, url):
    articles = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            dt = parse_time(entry)
            raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "source": name,
                "dt": dt.isoformat() if dt else None,
                "raw_summary": raw_summary,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except:
        pass
    return articles

def scrape_site(name, url, selector):
    articles = []
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        seen_titles = set()
        for a in soup.select(selector):
            title = a.get_text().strip()
            link = a.get("href", "")
            if not title or not link or len(title) < 15:
                continue
            if any(w in title.lower() for w in NAV_WORDS):
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)
            if not link.startswith("http"):
                link = urljoin(url, link)
            articles.append({
                "title": title,
                "link": link,
                "source": name,
                "dt": None,
                "raw_summary": "",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
            if len(articles) >= 15:
                break
    except:
        pass
    return articles

def enrich(articles):
    """翻译标题、算重要性、清理摘要（有缓存的瞬间完成）"""
    for a in articles:
        if not a.get("title_cn"):
            a["title_cn"] = translate_text(a["title"])
        if "importance" not in a:
            a["importance"] = importance_score(a.get("title_cn", "") + a["title"])
        if "summary_clean" not in a:
            a["summary_clean"] = clean_summary(a.get("raw_summary", ""))
    return articles

def merge_articles(existing, fresh):
    """把新抓的文章合并进已有列表，按标题去重，新的排前面"""
    existing_keys = {a["title"].strip()[:50] for a in existing}
    new_only = [a for a in fresh if a["title"].strip()[:50] not in existing_keys]
    return new_only + existing   # 新文章排最前

# ============================================================
# 后台增量更新（在独立线程运行，不阻塞界面）
# ============================================================
def _bg_update(store_path, rss_dict, scrape_dict, state_key):
    """后台线程：抓取 → 合并 → 写磁盘"""
    try:
        fresh = []
        for name, url in rss_dict.items():
            fresh.extend(load_rss(name, url))
        for name, (url, selector) in scrape_dict.items():
            fresh.extend(scrape_site(name, url, selector))
        fresh = enrich(fresh)
        existing = store_read(store_path)
        merged = merge_articles(existing, fresh)
        # 最多保留 500 条，防止文件无限增长
        store_write(store_path, merged[:500])
        set_update_state(state_key, datetime.now(timezone.utc).isoformat())
    except:
        pass

def trigger_bg_update(store_path, rss_dict, scrape_dict, state_key, interval_minutes=30):
    """
    检查距上次更新是否超过 interval_minutes，
    如果是则启动后台线程更新，不等待结果
    """
    state = get_update_state()
    last = state.get(state_key)
    if last:
        diff = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        if diff < interval_minutes * 60:
            return False   # 还没到时间，不更新
    t = threading.Thread(
        target=_bg_update,
        args=(store_path, rss_dict, scrape_dict, state_key),
        daemon=True
    )
    t.start()
    return True   # 已触发更新

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

def sort_articles(articles, mode):
    def key(a):
        dt_str = a.get('dt')
        ts = 0
        if dt_str:
            try:
                ts = datetime.fromisoformat(dt_str).timestamp()
            except:
                pass
        imp = a.get('importance', 0)
        if mode == "时间优先":
            return (-ts, -imp)
        elif mode == "重要性优先":
            return (-imp, -ts)
        else:
            return (-(ts / 1e9 * 0.6 + imp * 0.4))
    return sorted(articles, key=key)

# ============================================================
# 渲染（加载更多，每次+20条）
# ============================================================
PAGE_SIZE = 20

def render_articles(articles, page_key, enable_ai):
    if not articles:
        st.info("暂无数据")
        return
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    page = st.session_state[page_key]
    visible = articles[:page * PAGE_SIZE]

    for a in visible:
        title_cn = a.get('title_cn') or a['title']
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

            if enable_ai:
                with st.spinner(""):
                    summary = get_ai_summary(a['title'], a.get('raw_summary', ''), a['source'])
            else:
                summary = a.get('summary_clean', '')
                if summary:
                    summary = translate_text(summary)

            if summary:
                st.caption(summary)

    total = len(articles)
    shown = len(visible)
    if shown < total:
        st.caption(f"已显示 {shown} / {total} 条")
        if st.button(f"加载更多（还有 {total - shown} 条）", key=f"more_{page_key}", use_container_width=True):
            st.session_state[page_key] = page + 1
            st.rerun()
    else:
        st.caption(f"已显示全部 {total} 条")

# ============================================================
# 主流程
# ============================================================
st.title("🛰 行业情报系统")
st.caption("KITCHEN · BATH · REFORM · SUPPLY · DESIGN INTELLIGENCE")
st.divider()

col_sort, col_ai, col_refresh = st.columns([2, 3, 1])
with col_sort:
    sort_mode = st.selectbox("排序", ["时间优先", "重要性优先", "综合排序"], label_visibility="collapsed")
with col_ai:
    enable_ai = st.checkbox("启用 AI 深度摘要（需配置 API Key）", value=False)
with col_refresh:
    force_refresh = st.button("🔄 刷新", use_container_width=True)

if force_refresh:
    # 强制刷新：清空更新时间记录，让后台立即重新抓
    set_update_state("media", None)
    set_update_state("assoc", None)
    for k in ["page_media", "page_assoc", "assoc_loaded"]:
        st.session_state.pop(k, None)
    st.rerun()

st.divider()

# ---------- 读取媒体数据（从磁盘，毫秒级）----------
media_articles = store_read(MEDIA_STORE)

if not media_articles:
    # 磁盘没有数据（第一次运行），同步等待加载完
    with st.spinner("首次加载媒体数据，请稍候..."):
        fresh = []
        for name, url in MEDIA_RSS.items():
            fresh.extend(load_rss(name, url))
        for name, (url, selector) in MEDIA_SCRAPE.items():
            fresh.extend(scrape_site(name, url, selector))
        fresh = enrich(fresh)
        store_write(MEDIA_STORE, fresh[:500])
        set_update_state("media", datetime.now(timezone.utc).isoformat())
        media_articles = fresh
    bg_triggered = False
else:
    # 有缓存，直接用，后台静默检查是否需要更新
    bg_triggered = trigger_bg_update(MEDIA_STORE, MEDIA_RSS, MEDIA_SCRAPE, "media", interval_minutes=30)

media_articles = enrich(media_articles)
media_articles = sort_articles(media_articles, sort_mode)

# 更新时间提示
state = get_update_state()
last_media = state.get("media")
if last_media:
    try:
        last_dt = datetime.fromisoformat(last_media)
        last_str = last_dt.strftime("%m-%d %H:%M")
    except:
        last_str = "未知"
else:
    last_str = "未知"

c1, c2, c3 = st.columns(3)
c1.metric("媒体情报", len(media_articles))
c2.metric("监控源", len(MEDIA_RSS) + len(MEDIA_SCRAPE) + len(ASSOC_RSS) + len(ASSOC_SCRAPE))
c3.metric("上次更新", last_str)

if bg_triggered:
    st.caption("⟳ 后台正在静默更新数据，刷新页面可看到新内容")

st.divider()

tab_media, tab_assoc = st.tabs([
    f"📰 行业媒体（{len(media_articles)} 条）",
    "🏛 行业协会",
])

with tab_media:
    render_articles(media_articles, "page_media", enable_ai)

with tab_assoc:
    if not st.session_state.get("assoc_loaded"):
        assoc_articles = store_read(ASSOC_STORE)

        if not assoc_articles:
            with st.spinner("首次加载协会数据，请稍候..."):
                fresh = []
                for name, url in ASSOC_RSS.items():
                    fresh.extend(load_rss(name, url))
                for name, (url, selector) in ASSOC_SCRAPE.items():
                    fresh.extend(scrape_site(name, url, selector))
                fresh = enrich(fresh)
                store_write(ASSOC_STORE, fresh[:500])
                set_update_state("assoc", datetime.now(timezone.utc).isoformat())
                assoc_articles = fresh
        else:
            trigger_bg_update(ASSOC_STORE, ASSOC_RSS, ASSOC_SCRAPE, "assoc", interval_minutes=30)

        assoc_articles = enrich(assoc_articles)
        st.session_state["assoc_articles"] = sort_articles(assoc_articles, sort_mode)
        st.session_state["assoc_loaded"] = True

    assoc_articles = st.session_state.get("assoc_articles", [])
    render_articles(assoc_articles, "page_assoc", enable_ai)
