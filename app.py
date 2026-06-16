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
        if key not in existing_keys:            new_only.app
(Content truncated due to size limit. Use line ranges to read remaining content)
