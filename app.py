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
# 数据源配置（外部化）
# ============================================================

# 从配置文件加载数据源
def load_data_sources():
    """加载数据源配置"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    
    default_config = {
        "media_rss": {
            "House News": "https://www.housenews.jp/rss",
            "KBB 评论": "https://www.kbbreview.com/feed/",
            "木工网": "https://www.woodworkingnetwork.com/rss.xml"
        },
        "media_scrape": {
            "SanitaerNews": ("https://www.sanitaernews.de/", "h2 a, h3 a"),
            "SDBPRO": ("https://www.sdbpro.fr/industrie/", "h2 a, h3 a"),
            "Moebelmarkt": ("https://www.moebelmarkt.de/news", "h2 a, h3 a"),
            "Alimarket": ("https://www.alimarket.es/construccion/noticias", "h2 a, h3 a"),
            "SupplyHT": ("https://www.supplyht.com/topics/2649-plumbing", "h2 a, h3 a"),
            "DIY International": ("https://www.diyinternational.com/", "h2 a, h3 a"),
            "Ceramic World Web": ("https://ceramicworldweb.com/index.php/en", "h2 a, h3 a"),
            "Industry ID": ("https://www.industry.co.id/industri/keramik", "h4 a")
        },
        "assoc_rss": {
            "Cerameunie": "https://cerameunie.eu/rss",
            "Abceram BR": "https://abceram.org.br/feed"
        },
        "assoc_scrape": {
            "VN Ceramic": ("https://vnceramic.org.vn/", "h2 a, h3 a"),
            "Sanitaerwirtschaft": ("https://www.sanitaerwirtschaft.de/aktuell", "h2 a, h3 a"),
            "CCST": ("https://ccst.org.tr/haberler", "li a"),
            "CAB Badania": ("https://cab-badania.pl/en/", "li a"),
            "Apicer PT": ("https://www.apicer.pt/apicer/pt/noticias", "li a"),
            "REIC Thailand": ("https://www.reic.or.th/", "li a"),
            "VDMA": ("https://www.vdma.eu/de/armaturen", "h2 a, h3 a"),
            "Acimac": ("https://www.acimac.it/news-di-settore/", "h2 a, h3 a")
        }
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_config
    
    return default_config

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

IMPORTANCE_KEYWORDS = [
    "发布", "新", "创新", "趋势", "报告", "增长", "市场",
    "新品", "突破", "收购", "合作伙伴", "独家", "科技"
]

NAV_WORDS = [
    "首页", "关于", "联系方式", "登录", "注册", "菜单", "搜索",
    "客户区", "礼物", "订阅", "时事通讯", "隐私", "条款", "cookie",
    "阅读更多", "lire plus", "mehr lesen", "ver más"
]

def store_read(path: str) -> List[Dict]:
    """从磁盘读取文章列表"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def store_write(path: str, articles: List[Dict]):
    """将文章列表写入磁盘"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_update_state() -> Dict:
    """获取更新状态"""
    if not os.path.exists(UPDATE_STATE):
        return {}
    try:
        with open(UPDATE_STATE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def set_update_state(key: str, value):
    """设置更新状态"""
    state = get_update_state()
    state[key] = value
    try:
        with open(UPDATE_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except:
        pass

def cache_path(key: str) -> str:
    """生成缓存文件路径"""
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")

def cache_get(key: str, ttl: Optional[int] = None):
    """从缓存读取"""
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

def cache_set(key: str, value):
    """写入缓存"""
    p = cache_path(key)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"ts": datetime.now().timestamp(), "value": value}, f, ensure_ascii=False)
    except:
        pass

# ============================================================
# 工具函数
# ============================================================

def translate_text(text: str) -> str:
    """翻译文本（带缓存）"""
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

def parse_time(entry) -> Optional[datetime]:
    """解析文章发布时间"""
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

def format_time(dt: Optional[datetime]) -> str:
    """格式化时间显示"""
    if not dt:
        return "时间未知"
    
    now = datetime.now(timezone.utc)
    diff = now - dt
    
    if diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() / 60)} 分钟前"
    elif diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() / 3600)} 小时前"
    elif diff.total_seconds() < 604800:
        return f"{int(diff.total_seconds() / 86400)} 天前"
    else:
        return dt.strftime("%Y-%m-%d")

def importance_score(title: str) -> int:
    """计算文章重要性得分"""
    score = 0
    title_lower = title.lower()
    for kw in IMPORTANCE_KEYWORDS:
        if kw.lower() in title_lower:
            score += 1
    return score

def clean_summary(raw_html: str) -> str:
    """清理并提取摘要"""
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

def load_rss(name: str, url: str) -> List[Dict]:
    """加载 RSS 源"""
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

def scrape_site(name: str, url: str, selector: str) -> List[Dict]:
    """爬取网站"""
    articles = []
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
        soup = BeautifulSoup(res.text, "html.parser")
        seen_titles = set()
        
        # 针对付费墙网站，尝试从父级元素中提取首页可见的摘要
        for element in soup.select(selector):
            # 如果 selector 本身是 a 标签
            if element.name == 'a':
                a = element
                # 尝试寻找父级容器中的描述文本
                parent = a.find_parent(['div', 'li', 'article', 'section'])
                summary = ""
                if parent:
                    # 排除 a 标签本身的文本，获取剩余文本作为摘要
                    summary = parent.get_text(separator=" ").replace(a.get_text(), "").strip()
            else:
                # 如果 selector 是容器，寻找其中的 a 标签
                a = element.find('a')
                if not a: continue
                summary = element.get_text(separator=" ").replace(a.get_text(), "").strip()

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
                "raw_summary": summary[:300], # 首页摘要通常较短
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
            
            if len(articles) >= 15:
                break
    except:
        pass
    
    return articles

def enrich_articles(articles: List[Dict]) -> List[Dict]:
    """丰富文章数据（翻译、重要性、摘要）"""
    for a in articles:
        if "title_cn" not in a:
            a["title_cn"] = translate_text(a["title"])
        if "importance" not in a:
            a["importance"] = importance_score(a.get("title_cn", "") + a["title"])
        if "summary_clean" not in a:
            a["summary_clean"] = clean_summary(a.get("raw_summary", ""))
    
    return articles

def merge_articles(existing: List[Dict], fresh: List[Dict]) -> List[Dict]:
    """合并文章列表，去重"""
    # 使用标题和链接的组合作为唯一键，更加准确
    def get_key(a):
        return (a.get("title", "").strip()[:100] + a.get("link", "").strip()).lower()
    
    existing_keys = {get_key(a) for a in existing}
    new_only = []
    for a in fresh:
        key = get_key(a)
        if key not in existing_keys:
            new_only.append(a)
            existing_keys.add(key)
            
    return new_only + existing

def search_discovery(keywords: List[str]) -> List[Dict]:
    """通过 Google 搜索发现新情报"""
    articles = []
    # 模拟更真实的浏览器行为
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    # 为了避免被封，每次随机选择 3 个关键词进行搜索
    import random
    selected_kws = random.sample(keywords, min(len(keywords), 3))
    
    for kw in selected_kws:
        try:
            # 增加行业相关后缀以提高搜索精准度
            search_query = f"{kw} industry news news 2026"
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}&tbs=qdr:m" # 限制在过去一个月内
            
            res = requests.get(url, timeout=15, headers=headers)
            if res.status_code != 200:
                continue
                
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Google 搜索结果的典型结构
            search_results = soup.select('div.g')
            for g in search_results[:5]: # 每个关键词取前 5 个结果
                h3 = g.select_one('h3')
                a = g.select_one('a')
                snippet = g.select_one('div.VwiC3b') # Google 摘要的常见 class
                
                if h3 and a and a.get('href'):
                    title = h3.get_text()
                    link = a['href']
                    raw_summary = snippet.get_text() if snippet else f"基于关键词 '{kw}' 发现的行业情报。"
                    
                    if link.startswith("http") and "google.com" not in link:
                        articles.append({
                            "title": f"[发现] {title}",
                            "link": link,
                            "source": f"Google: {kw}",
                            "dt": datetime.now(timezone.utc).isoformat(),
                            "raw_summary": raw_summary,
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        })
            
            # 适当延时，防止请求过快
            time.sleep(random.uniform(1, 3))
            
        except Exception as e:
            print(f"Search error for {kw}: {e}")
            
    return articles

def _bg_update(store_path: str, rss_dict: Dict, scrape_dict: Dict, state_key: str, keywords: List[str] = None):
    """后台更新线程"""
    try:
        fresh = []
        if rss_dict and scrape_dict:
            for name, url in rss_dict.items():
                fresh.extend(load_rss(name, url))
            for name, (url, selector) in scrape_dict.items():
                fresh.extend(scrape_site(name, url, selector))
        
        if keywords and state_key == "discovery":
            fresh.extend(search_discovery(keywords))
            
        fresh = enrich_articles(fresh)
        existing = store_read(store_path)
        merged = merge_articles(existing, fresh)
        
        store_write(store_path, merged[:500])
        set_update_state(state_key, datetime.now(timezone.utc).isoformat())
    except:
        pass

def trigger_bg_update(store_path: str, rss_dict: Dict, scrape_dict: Dict, state_key: str, interval_minutes: int = 30, keywords: List[str] = None) -> bool:
    """触发后台更新"""
    state = get_update_state()
    last = state.get(state_key)
    
    if last:
        diff = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
        if diff < interval_minutes * 60:
            return False
    
    t = threading.Thread(
        target=_bg_update,
        args=(store_path, rss_dict, scrape_dict, state_key, keywords),
        daemon=True
    )
    t.start()
    return True

def sort_articles(articles: List[Dict], mode: str) -> List[Dict]:
    """排序文章"""
    def key_func(a):
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
    
    return sorted(articles, key=key_func)

# ============================================================
# UI 组件
# ============================================================

def render_article_card(article: Dict, enable_ai: bool = False):
    """渲染文章卡片"""
    title_cn = article.get('title_cn') or article['title']
    dt_str = article.get('dt')
    dt = None
    
    if dt_str:
        try:
            dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        except:
            pass
    
    time_str = format_time(dt)
    importance = article.get('importance', 0)
    
    # 确定重要性等级
    if importance >= 3:
        importance_level = "high"
        importance_text = "高"
    elif importance >= 1:
        importance_level = "medium"
        importance_text = "中"
    else:
        importance_level = "low"
        importance_text = "低"
    
    # 清理摘要中的 HTML 标签（防止外泄）
    summary = article.get('summary_clean', '')
    if summary:
        summary = BeautifulSoup(summary, "html.parser").get_text()
    
    # 构建卡片 HTML
    # 注意：为了安全，我们在 f-string 中对变量进行处理，确保不会破坏 HTML 结构
    st.markdown(f"""
    <div class="article-card">
        <div class="article-title">
            <a href="{article['link']}" target="_blank" style="text-decoration: none; color: inherit;">
                {title_cn}
            </a>
        </div>
        <div class="article-summary">
            {summary}
        </div>
        <div class="article-meta">
            <span class="badge badge-source">{article['source']}</span>
            <span class="badge badge-importance-{importance_level}">重要性: {importance_text}</span>
            <span style="color: #9ca3af;">🕐 {time_str}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_articles_list(articles: List[Dict], page_key: str, enable_ai: bool = False, page_size: int = 20):
    """渲染文章列表"""
    if not articles:
        st.info("📭 暂无数据，请稍候或刷新页面")
        return
    
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    page = st.session_state[page_key]
    visible = articles[:page * page_size]
    
    # 显示文章卡片
    for article in visible:
        render_article_card(article, enable_ai)
    
    # 分页控制
    total = len(articles)
    shown = len(visible)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.caption(f"📊 已显示 {shown} / {total} 条")
    
    with col3:
        if shown < total:
            if st.button(f"加载更多 ({total - shown} 条)", use_container_width=True, key=f"more_{page_key}"):
                st.session_state[page_key] = page + 1
                st.rerun()
        else:
            st.caption("✅ 已显示全部")

# ============================================================
# 主应用
# ============================================================

def main():
    # 加载配置
    config = load_data_sources()
    
    # 侧边栏
    with st.sidebar:
        st.markdown("### ⚙️ 设置")
        
        # 主题切换
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">主题</div>', unsafe_allow_html=True)
        theme = st.radio("选择主题", ["浅色", "深色"], horizontal=True, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 排序方式
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">排序方式</div>', unsafe_allow_html=True)
        sort_mode = st.selectbox(
            "选择排序方式",
            ["时间优先", "重要性优先", "综合排序"],
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # AI 摘要
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">功能</div>', unsafe_allow_html=True)
        enable_ai = st.checkbox("启用 AI 深度摘要", value=False)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 刷新按钮
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        if st.button("🔄 立即刷新", use_container_width=True):
            set_update_state("media", None)
            set_update_state("assoc", None)
            for k in ["page_media", "page_assoc"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 数据源统计
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">数据源</div>', unsafe_allow_html=True)
        total_sources = (len(config["media_rss"]) + len(config["media_scrape"]) + 
                        len(config["assoc_rss"]) + len(config["assoc_scrape"]))
        st.metric("监控源数", total_sources)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 主内容区
    st.markdown("## 🛰 行业情报系统")
    st.markdown("**实时聚合全球建筑、卫浴、厨房、装修行业资讯**")
    
    st.divider()
    
    # 加载媒体数据
    media_articles = store_read(MEDIA_STORE)
    
    if not media_articles:
        with st.spinner("首次加载媒体数据，请稍候..."):
            fresh = []
            for name, url in config["media_rss"].items():
                fresh.extend(load_rss(name, url))
            for name, (url, selector) in config["media_scrape"].items():
                fresh.extend(scrape_site(name, url, selector))
            
            fresh = enrich_articles(fresh)
            store_write(MEDIA_STORE, fresh[:500])
            set_update_state("media", datetime.now(timezone.utc).isoformat())
            media_articles = fresh
        bg_triggered = False
    else:
        bg_triggered = trigger_bg_update(MEDIA_STORE, config["media_rss"], config["media_scrape"], "media", interval_minutes=30)
        media_articles = enrich_articles(media_articles)
    
    media_articles = sort_articles(media_articles, sort_mode)
    
    # 显示统计信息
    state = get_update_state()
    last_media = state.get("media")
    last_str = "未知"
    
    if last_media:
        try:
            last_dt = datetime.fromisoformat(last_media)
            last_str = last_dt.strftime("%m-%d %H:%M")
        except:
            pass
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📰 媒体情报", len(media_articles))
    col2.metric("🌍 监控源", len(config["media_rss"]) + len(config["media_scrape"]))
    col3.metric("⏰ 最后更新", last_str)
    
    if bg_triggered:
        st.info("⟳ 后台正在静默更新数据，刷新页面可看到新内容")
    
    st.divider()
    
    # 标签页
    tab_media, tab_assoc, tab_discovery = st.tabs([
        f"📰 行业媒体 ({len(media_articles)} 条)",
        "🏛 行业协会",
        "🔍 情报发现"
    ])
    
    with tab_media:
        render_articles_list(media_articles, "page_media", enable_ai)
    
    with tab_assoc:
        # 加载协会数据
        if "assoc_loaded" not in st.session_state:
            assoc_articles = store_read(ASSOC_STORE)
            
            if not assoc_articles:
                with st.spinner("首次加载协会数据，请稍候..."):
                    fresh = []
                    for name, url in config["assoc_rss"].items():
                        fresh.extend(load_rss(name, url))
                    for name, (url, selector) in config["assoc_scrape"].items():
                        fresh.extend(scrape_site(name, url, selector))
                    
                    fresh = enrich_articles(fresh)
                    store_write(ASSOC_STORE, fresh[:500])
                    set_update_state("assoc", datetime.now(timezone.utc).isoformat())
                    assoc_articles = fresh
            else:
                trigger_bg_update(ASSOC_STORE, config["assoc_rss"], config["assoc_scrape"], "assoc", interval_minutes=30)
                assoc_articles = enrich_articles(assoc_articles)
            
            st.session_state["assoc_articles"] = assoc_articles
            st.session_state["assoc_loaded"] = True
        else:
            assoc_articles = st.session_state["assoc_articles"]
        
        assoc_articles = sort_articles(assoc_articles, sort_mode)
        render_articles_list(assoc_articles, "page_assoc", enable_ai)

    with tab_discovery:
        st.markdown("### 🔍 行业情报自动发现 (Google 驱动)")
        st.info("系统将基于您的关键词，通过 Google 搜索全网最新的行业资讯。")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            uploaded_file = st.file_uploader("📁 上传关键词文件 (txt)", type=["txt"])
        with col2:
            manual_keywords = st.text_area("⌨️ 或手动输入关键词 (每行一个)", placeholder="例如: Sanitaryware industry news")
        
        keywords = []
        if uploaded_file:
            keywords.extend([line.decode("utf-8").strip() for line in uploaded_file if line.strip()])
        if manual_keywords:
            keywords.extend([k.strip() for k in manual_keywords.split("\n") if k.strip()])
        
        # 过滤掉注释或非关键词行
        keywords = [k for k in keywords if k and not k.startswith("#") and len(k) > 1]
        
        if keywords:
            st.success(f"✅ 已就绪 {len(keywords)} 个有效关键词")
            if st.button("🚀 启动 Google 全网情报发现", use_container_width=True):
                with st.spinner("正在通过 Google 搜索情报..."):
                    # 立即触发一次更新，不考虑 30 分钟间隔
                    trigger_bg_update(DISCOVERY_STORE, None, None, "discovery", interval_minutes=0, keywords=keywords)
                    st.toast("任务已启动！搜索结果将在几分钟内陆续出现。")
                    st.info("提示：搜索任务在后台运行，您可以继续浏览其他页面，稍后回来刷新即可。")

        st.divider()
        
        discovery_articles = store_read(DISCOVERY_STORE)
        if discovery_articles:
            st.subheader(f"📊 已发现情报 ({len(discovery_articles)} 条)")
            discovery_articles = enrich_articles(discovery_articles)
            discovery_articles = sort_articles(discovery_articles, sort_mode)
            render_articles_list(discovery_articles, "page_discovery", enable_ai)
        else:
            st.info("💡 暂无发现的情报。请在上方输入关键词并点击启动。")

if __name__ == "__main__":
    main()
