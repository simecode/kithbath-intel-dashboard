# 🛰 KitchBath Intel — 行业情报系统 v3.5

> 全球卫浴、厨房、建材行业实时信息聚合与 AI 分析平台

**在线访问：** [kitchbathintel.streamlit.app](https://kitchbathintel.streamlit.app)
**代码仓库：** [github.com/simecode/kithbath-intel-dashboard](https://github.com/simecode/kithbath-intel-dashboard)

---

## 功能概览

| 模块 | 说明 |
|------|------|
| 📰 行业媒体 | 聚合全球 10+ 专业媒体 RSS 与网页，自动翻译、分页浏览 |
| 🏛 行业协会 | 抓取欧美亚各地行业协会新闻发布页，直达一手政策动态 |
| 🔍 情报发现 | 基于关键词的全网实时搜索，覆盖 DuckDuckGo 等引擎 |
| 📡 舆情监督 | 按主题（人事/并购/新品/财务）自动分类，支持自定义关键词追踪 |
| 🤖 AI 分析报告 | 接入主流大模型（含免费方案），生成结构化行业洞察报告 |

---

## 快速开始

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/simecode/kithbath-intel-dashboard.git
cd kithbath-intel-dashboard

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
streamlit run app.py
# 访问 http://localhost:8501
```

### 部署到 Streamlit Cloud（免费）

1. 将代码 push 到 GitHub
2. 访问 [streamlit.io/cloud](https://streamlit.io/cloud)，点击 **New app**
3. 选择仓库 → 选择 `app.py` → 点击 **Deploy**
4. 部署完成后自动获得公开访问链接

---

## 功能详解

### 📰 行业媒体 / 🏛 行业协会

- **自动抓取**：启动后后台静默更新，每 30 分钟刷新一次（可手动强制刷新）
- **时间过滤**：支持按 7天 / 30天 / 3个月 / 一年 / 全部 筛选
- **自动翻译**：开启后将非中文标题/摘要自动译为中文（使用 Google Translate，无需 Key）
- **排序方式**：时间最新 / 重要性最高 / 综合推荐
- **分页浏览**：每页 20 条，支持上一页/下一页翻页


### 🔍 情报发现

点击「启动全网情报发现」后，系统自动以 `config.json` 中的 `keywords` 关键词组合搜索全网最新资讯，结合行业语境过滤无关内容后聚合显示。

### 📡 舆情监督

**四大预设主题：**

- 👔 **高管人事变动** — 追踪 resign、appoint、CEO、离职、任命等信号词
- 🤝 **并购与战略合作** — 追踪 acquire、merger、收购、合并等关键词
- 🚀 **新品与技术发布** — 追踪 launch、new product、发布、创新等词
- 📈 **财务与市场变化** — 追踪 revenue、layoff、裁员、重组等词

**使用方法：**
1. 选择统计时间段（近7天 / 1个月 / 3个月 / 6个月）
2. 顶部数字卡片一目了然地展示各主题命中数量
3. 展开对应主题查看具体文章列表
4. 可在「自定义监督关键词」输入框中输入自己关注的词（如 `Kohler CEO, Hansgrohe resign`），进行专项追踪

### 🤖 AI 分析报告

**支持的 AI 提供商：**

| 提供商 | 费用 | 获取 Key |
|--------|------|---------|
| 🆓 OpenRouter 免费模型 | 每日免费额度 | [openrouter.ai](https://openrouter.ai) 注册即可 |
| DeepSeek | 极低价格 | [platform.deepseek.com](https://platform.deepseek.com) |
| OpenAI GPT-4o mini | 按量计费 | [platform.openai.com](https://platform.openai.com) |
| Anthropic Claude | 按量计费 | [console.anthropic.com](https://console.anthropic.com) |
| 通义千问 | 有免费额度 | [dashscope.aliyun.com](https://dashscope.aliyun.com) |

> API Key 仅存在于当前浏览器会话内存中，页面关闭即清除，不会上传或持久化存储。

**报告结构（示例）：**
1. 主要趋势归纳（4-6个核心趋势）
2. 企业动态追踪（人事/并购/新品/财务，自动排除媒体平台名称）
3. 地区市场热度分析
4. 风险与机会信号识别
5. 分析师综合点评 + 下季度前瞻

**时间段选项：** 近 3 / 6 / 9 / 12 个月（默认 6 个月）

---

## 数据源配置

所有数据源在 `config.json` 中管理，无需修改 Python 代码即可扩展：

```jsonc
{
  "keywords": ["Kohler", "Hansgrohe", ...],   // 情报发现关键词

  "media_rss": {
    "来源名称": "https://example.com/feed.xml"  // RSS 格式
  },

  "media_scrape": {
    "来源名称": {
      "url": "首页 URL",
      "news_url": "新闻列表页 URL（推荐直接指向新闻页）",
      "item": "文章容器 CSS 选择器",
      "title": "标题链接 CSS 选择器",
      "summary": "摘要 CSS 选择器（可选）"
    }
  },

  "assoc_rss": { ... },   // 协会 RSS 源
  "assoc_scrape": { ... } // 协会网页抓取源
}
```

**添加新来源示例：**

```json
"media_rss": {
  "新媒体名称": "https://example.com/news.rss"
},
"media_scrape": {
  "某行业网站": {
    "url": "https://example.com",
    "news_url": "https://example.com/news/",
    "item": "article",
    "title": "h2 a",
    "summary": "p.excerpt"
  }
}
```

---

## 项目结构

```
kithbath-intel-dashboard/
├── app.py                  # 主应用（Streamlit）
├── config.json             # 数据源与关键词配置
├── requirements.txt        # Python 依赖
├── README.md               # 本文档
├── .streamlit/
│   └── config.toml         # Streamlit 主题配置
└── .intel_store/           # 运行时自动创建
    ├── media.json          # 媒体文章缓存
    ├── assoc.json          # 协会文章缓存
    ├── discovery.json      # 情报发现缓存
    └── update_state.json   # 更新时间记录
```

---

## 常见问题

**Q：页面数据很旧，怎么刷新？**
点击左侧侧边栏的「🔄 强制刷新所有数据」，约 1-2 分钟后再刷新页面。

**Q：某些来源抓取为空？**
该网站可能改版了 HTML 结构，需更新 `config.json` 中对应的 CSS 选择器。可用浏览器「检查元素」定位正确选择器后修改。

**Q：翻译失败？**
自动翻译依赖 Google Translate 的免费接口，在 Streamlit Cloud 上偶尔会被限速。可关闭「启用自动翻译」开关，直接查看原文。

**Q：AI 分析报告里出现了媒体名称当作企业？**
已在 v3.5 修复：系统会自动将所有来源平台名称传入 AI 提示词，明确告知模型哪些是媒体平台而非行业企业。

**Q：OpenRouter 免费额度不够用？**
可切换到 DeepSeek（价格极低）或注册多个 OpenRouter 账号轮换使用。

---

## 版本历史

| 版本 | 更新内容 |
|------|---------|
| v3.5 | 新增舆情监督模块；修复 AI 分析将媒体名当企业的问题；分析时间段可选（3/6/9/12个月）；HTML 渲染 bug 修复 |
| v3.0 | 新增 AI 分析报告；支持 OpenRouter 免费模型；分页功能 |
| v2.5 | 新增情报发现 Tab；多源搜索引擎整合 |
| v2.0 | 现代化 UI；RSS + 网页双抓取；自动翻译；后台更新 |

---

## License

MIT License — 欢迎 Fork 和二次开发
交流联系adala7@sina.com
