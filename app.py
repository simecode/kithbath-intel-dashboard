import streamlit as st
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from datetime import datetime, timezone, timedelta
import email.utils
import json
import os
import hashlib
import threading
from urllib.parse import urljoin
from typing import List, Dict, Optional
import time

# ============================================================
# 页面配置与样式
# ============================================================

st.set_page_config(
    page_title="行业情报系统 | Industry Intelligence",
    page_icon="🛰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 现代化样式注入
modern_css = """
<style>
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    /* 隐藏默认菜单 */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    header { visibility: hidden; }
    
    /* 主容器样式 */
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        min-height: 100vh;
    }
    
    /* 深色主题 */
    [data-theme="dark"] .main {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    
    /* 文章卡片样式 */
    .article-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        border-left: 4px solid #2563eb;
    }
    
    .article-card:hover {
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        transform: translateY(-4px);
    }
    
    [data-theme="dark"] .article-card {
        background: #2d2d44;
        color: #e0e0e0;
    }
    
    /* 标题样式 */
    .article-title {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 12px;
        color: #1f2937;
        line-height: 1.5;
    }
    
    [data-theme="dark"] .article-title {
        color: #f0f0f0;
    }
    
    /* 摘要样式 */
    .article-summary {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 12px;
        line-height: 1.6;
    }
    
    [data-theme="dark"] .article-summary {
        color: #b0b0b0;
    }
    
    /* 元数据行 */
    .article-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
        font-size: 12px;
        color: #9ca3af;
        border-top: 1px solid #e5e7eb;
        padding-top: 12px;
    }
    
    [data-theme="dark"] .article-meta {
        border-top-color: #444;
        color: #888;
    }
    
    /* 标签样式 */
    .badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }
    
    .badge-source {
        background: #dbeafe;
        color: #1e40af;
    }
    
    .badge-importance-high {
        background: #fee2e2;
        color: #991b1b;
    }
    
    .badge-importance-medium {
        background: #fef3c7;
        color: #92400e;
    }
    
    .badge-importance-low {
        background: #dbeafe;
        color: #1e40af;
    }
    
    [data-theme="dark"] .badge-source {
        background: #1e3a8a;
        color: #93c5fd;
    }
    
    /* 加载动画 */
    .loading-skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
    }
    
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    
    /* 响应式设计 */
    @media (max-width: 768px) {
        .article-card {
            padding: 16px;
        }
        
        .article-title {
            font-size: 16px;
        }
        
        .article-meta {
            flex-direction: column;
            align-items: flex-start;
        }
    }
    
    /* 平滑滚动 */
    html {
        scroll-behavior: smooth;
    }
    
    /* 侧边栏样式 */
    .sidebar-section {
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid #e5e7eb;
    }
    
    [data-theme="dark"] .sidebar-section {
        border-bottom-color: #444;
    }
    
    .sidebar-title {
        font-weight: 700;
        font-size: 14px;
        text-transform: uppercase;
        color: #6b7280;
        margin-bottom: 12px;
        letter-spacing: 0.5px;
    }
    
    [data-theme="dark"] .sidebar-title {
        color: #a0a0a0;
    }
</style>
"""

st.markdown(modern_css, unsafe_allow_html=True)

# ============================================================
# 数据源配置
# ============================================================

def load_data_sources():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

# ============================================================
# 存储与缓存管理
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(BASE_DIR, ".intel_store")
CACHE_DIR = os.path.join(BASE_DIR, ".intel_cache")
os.makedirs(STORE_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

MEDIA_STORE = os.path.join(STORE_DIR, "media.json")
ASSOC_STORE = os.path.join(STORE_DIR, "assoc.json")
DISCOVERY_STORE = os.path.join(STORE_DIR, "discovery.json")
UPDATE_STATE = os.path.join(STORE_DIR, "update_state.json")

IMPORTANCE_KEYWORDS = ["发布", "新", "创新", "趋势", "报告", "增长", "市场", "收购", "合作", "科技", "突破"]

def store_read(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def store_write(path: str, articles: List[Dict]):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
    except: pass

def get_update_state() -> Dict:
    if not os.path.exists(UPDATE_STATE): return {}
    try:
        with open(UPDATE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def set_update_state(key: str, value):
    state = get_update_state()
    state[key] = value
    try:
        with open(UPDATE_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except: pass

def clean_text(text: str) -> str:
    if not text: return ""
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()
    return " ".join(text.split())

# ============================================================
# 抓取引擎
# ============================================================

def load_rss(name: str, url: str) -> List[Dict]:
    articles = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            dt = None
            for f in ['published_parsed', 'updated_parsed']:
                if hasattr(entry, f) and getattr(entry, f):
                    dt = datetime(*getattr(entry, f)[:6], tzinfo=timezone.utc).isoformat()
                    break
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "source": name,
                "dt": dt or datetime.now(timezone.utc).isoformat(),
                "raw_summary": clean_text(getattr(entry, 'summary', '')),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except: pass
    return articles

def scrape_site(name: str, config_data) -> List[Dict]:
    articles = []
    try:
        if isinstance(config_data, list):
            url, selector = config_data[0], config_data[1]
            is_structured = False
        else:
            url = config_data.get("url")
            is_structured = True

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        res = requests.get(url, timeout=15, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        seen_titles = set()
        
        if not is_structured:
            for element in soup.select(selector):
                a = element if element.name == 'a' else element.find('a')
                if not a: continue
                title = a.get_text().strip()
                link = urljoin(url, a.get("href", ""))
                if not title or len(title) < 10: continue
                key = f"{title[:50]}_{link}"
                if key not in seen_titles:
                    articles.append({
                        "title": title, "link": link, "source": name,
                        "dt": datetime.now(timezone.utc).isoformat(),
                        "raw_summary": "", "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    seen_titles.add(key)
        else:
            # 结构化首页提取 (精准提取箭头所指内容)
            item_sel = config_data.get("item")
            title_sel = config_data.get("title")
            sum_sel = config_data.get("summary")
            date_sel = config_data.get("date")
            
            for item in soup.select(item_sel):
                t_el = item.select_one(title_sel)
                if not t_el: continue
                title = t_el.get_text(strip=True)
                link = urljoin(url, t_el.get("href", ""))
                
                summary = ""
                if sum_sel:
                    s_el = item.select_one(sum_sel)
                    summary = s_el.get_text(strip=True) if s_el else ""
                
                key = f"{title[:50]}_{link}"
                if key not in seen_titles:
                    articles.append({
                        "title": title, "link": link, "source": name,
                        "dt": datetime.now(timezone.utc).isoformat(),
                        "raw_summary": clean_text(summary),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    seen_titles.add(key)
    except Exception as e:
        print(f"Scrape error {name}: {e}")
    return articles

def search_discovery(keywords: List[str]) -> List[Dict]:
    """多引擎行业情报搜索引擎 (强化相关性过滤)"""
    articles = []
    import random
    
    # 每次搜索随机选择 3 个关键词
    selected_kws = random.sample(keywords, min(len(keywords), 3))
    
    # 行业核心约束词
    industry_context = "bathroom sanitary plumbing ceramic faucet"
    
    for kw in selected_kws:
        # 策略 1: DuckDuckGo News (强制锁定新闻和时间)
        try:
            # 强化搜索词，确保相关性
            search_query = f'"{kw}" {industry_context} news'
            url = f"https://html.duckduckgo.com/html/?q={search_query.replace(' ', '+')}&df=w"
            res = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for r in soup.select('.result')[:8]:
                    a = r.select_one('.result__a')
                    snippet = r.select_one('.result__snippet')
                    if a and a.get('href'):
                        title = a.get_text(strip=True)
                        snip_text = snippet.get_text().lower() if snippet else ""
                        # 二次过滤：标题或摘要必须包含关键词或行业词
                        if any(x.lower() in title.lower() or x.lower() in snip_text for x in [kw] + industry_context.split()):
                            articles.append({
                                "title": f"✨ {title}",
                                "link": a['href'],
                                "source": f"最新发现: {kw}",
                                "dt": datetime.now(timezone.utc).isoformat(),
                                "raw_summary": snippet.get_text(strip=True) if snippet else "",
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                            })
        except: pass

        # 策略 2: Bing News
        try:
            search_query = f'"{kw}" {industry_context}'
            url = f"https://www.bing.com/news/search?q={search_query.replace(' ', '+')}&qft=interval%3d\"7\""
            res = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for item in soup.select('.news-card')[:5]:
                    t_el = item.select_one('.title')
                    s_el = item.select_one('.snippet')
                    if t_el and t_el.get('href'):
                        title = t_el.get_text(strip=True)
                        articles.append({
                            "title": f"🌐 {title}",
                            "link": t_el['href'],
                            "source": f"Bing新闻: {kw}",
                            "dt": datetime.now(timezone.utc).isoformat(),
                            "raw_summary": s_el.get_text(strip=True) if s_el else "",
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        })
        except: pass
    return articles

# ============================================================
# 后台更新逻辑
# ============================================================

def merge_articles(existing: List[Dict], fresh: List[Dict]) -> List[Dict]:
    seen = {f"{a['title'][:50]}_{a['link']}" for a in existing}
    new_only = [a for a in fresh if f"{a['title'][:50]}_{a['link']}" not in seen]
    return new_only + existing

def _bg_update(store_path: str, rss_dict: Dict, scrape_dict: Dict, state_key: str, keywords: List[str] = None):
    try:
        fresh = []
        if rss_dict:
            for name, url in rss_dict.items(): fresh.extend(load_rss(name, url))
        if scrape_dict:
            for name, config in scrape_dict.items(): fresh.extend(scrape_site(name, config))
        if keywords and state_key == "discovery":
            fresh.extend(search_discovery(keywords))
        
        existing = store_read(store_path)
        merged = merge_articles(existing, fresh)
        store_write(store_path, merged[:500])
        set_update_state(state_key, datetime.now(timezone.utc).isoformat())
    except: pass

def trigger_bg_update(store_path: str, rss_dict: Dict, scrape_dict: Dict, state_key: str, interval_minutes: int = 30, keywords: List[str] = None):
    state = get_update_state()
    last = state.get(state_key)
    if last:
        diff = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        if diff < interval_minutes * 60: return
    threading.Thread(target=_bg_update, args=(store_path, rss_dict, scrape_dict, state_key, keywords)).start()

# ============================================================
# UI 渲染
# ============================================================

def main():
    config = load_data_sources()
    
    st.sidebar.title("🛰 行业情报系统 v2.5")
    st.sidebar.caption("实时监控全球卫浴行业动态")
    
    with st.sidebar:
        st.divider()
        enable_ai = st.checkbox("启用 AI 智能翻译", value=True)
        sort_mode = st.selectbox("排序方式", ["时间 (最新)", "重要性 (最高)", "综合推荐"])
        if st.button("🔄 立即强制刷新所有数据", use_container_width=True):
            trigger_bg_update(MEDIA_STORE, config.get("media_rss"), config.get("media_scrape"), "media", interval_minutes=0)
            trigger_bg_update(ASSOC_STORE, config.get("assoc_rss"), config.get("assoc_scrape"), "assoc", interval_minutes=0)
            st.toast("后台更新已启动...")

    tab_media, tab_assoc, tab_discovery = st.tabs(["📰 行业媒体", "🏛 行业协会", "🔍 情报发现"])

    with tab_media:
        trigger_bg_update(MEDIA_STORE, config.get("media_rss"), config.get("media_scrape"), "media")
        articles = store_read(MEDIA_STORE)
        render_list(articles, enable_ai, sort_mode)

    with tab_assoc:
        trigger_bg_update(ASSOC_STORE, config.get("assoc_rss"), config.get("assoc_scrape"), "assoc")
        articles = store_read(ASSOC_STORE)
        render_list(articles, enable_ai, sort_mode)

    with tab_discovery:
        keywords = config.get("keywords", [])
        if st.button("🚀 启动全网情报发现", use_container_width=True):
            trigger_bg_update(DISCOVERY_STORE, None, None, "discovery", interval_minutes=0, keywords=keywords)
        articles = store_read(DISCOVERY_STORE)
        render_list(articles, enable_ai, sort_mode)

def render_list(articles, enable_ai, sort_mode):
    if not articles:
        st.info("正在加载情报数据，请稍后...")
        return
    
    # 简单排序
    if sort_mode == "时间 (最新)":
        articles.sort(key=lambda x: x.get('dt', ''), reverse=True)
    
    for a in articles[:50]:
        title = a['title']
        summary = a.get('raw_summary', '')
        if enable_ai:
            title = GoogleTranslator(source='auto', target='zh-CN').translate(title)
            if summary: summary = GoogleTranslator(source='auto', target='zh-CN').translate(summary)
            
        st.markdown(f"""
        <div class="article-card">
            <div class="article-title"><a href="{a['link']}" target="_blank" style="text-decoration:none; color:inherit;">{title}</a></div>
            <div class="article-summary">{summary}</div>
            <div class="article-meta">
                <span>📍 {a['source']}</span>
                <span>🕒 {a.get('dt', '')[:10]}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
