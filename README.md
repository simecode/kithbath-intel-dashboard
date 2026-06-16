# 🛰 行业情报系统 v2.0

一个现代化、高性能的行业信息流聚合平台，专注于建筑、卫浴、厨房、装修行业的全球资讯。

## ✨ 主要特性

### 设计与体验
- **现代化 UI 设计**: 采用扁平化设计风格，卡片式布局，专业清爽的视觉感受
- **响应式布局**: 完美适配桌面、平板、手机等各种设备
- **深色/浅色主题**: 支持主题切换，满足不同用户偏好
- **流畅交互**: 卡片悬停动画、平滑滚动、骨架屏加载等微交互
- **实时反馈**: 后台静默更新提示、加载状态提示、数据统计显示

### 功能特性
- **多源聚合**: 支持 RSS 和自定义网页爬虫，聚合全球 20+ 数据源
- **智能翻译**: 自动翻译非中文标题，支持缓存加速
- **重要性评分**: 基于关键词的智能重要性评分
- **灵活排序**: 支持时间优先、重要性优先、综合排序三种模式
- **数据持久化**: 本地 JSON 存储，支持离线浏览
- **后台更新**: 独立线程后台更新，不阻塞主界面

### 架构优化
- **数据源外部化**: 配置文件管理数据源，易于扩展
- **缓存机制**: 多层缓存策略，减少重复计算和 API 调用
- **性能优化**: 分页加载、增量更新、高效去重
- **模块化设计**: 清晰的函数划分，易于维护和扩展

## 🚀 快速开始

### 本地运行

#### 1. 克隆或下载项目
```bash
cd vibecoding_v2
```

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 运行应用
```bash
streamlit run app.py
```

应用将在 `http://localhost:8501` 启动。

### 部署到 Streamlit Cloud

#### 1. 推送到 GitHub

```bash
# 初始化 Git 仓库（如果还没有）
git init
git add .
git commit -m "Initial commit: Industry Intelligence System v2.0"

# 创建 GitHub 仓库并推送
git remote add origin https://github.com/YOUR_USERNAME/vibecoding_v2.git
git branch -M main
git push -u origin main
```

#### 2. 在 Streamlit Cloud 部署

1. 访问 [Streamlit Cloud](https://streamlit.io/cloud)
2. 点击 "New app"
3. 选择你的 GitHub 仓库和分支
4. 选择 `app.py` 作为主文件
5. 点击 "Deploy"

#### 3. 配置环境变量（如需要）

如果使用 AI 摘要功能，需要配置 API Key：
- 在 Streamlit Cloud 中，进入 "Settings" → "Secrets"
- 添加必要的环境变量（例如 Anthropic API Key）

## 📋 配置说明

### config.json 结构

```json
{
  "media_rss": {
    "来源名称": "RSS URL"
  },
  "media_scrape": {
    "来源名称": ["网页 URL", "CSS 选择器"]
  },
  "assoc_rss": {
    "来源名称": "RSS URL"
  },
  "assoc_scrape": {
    "来源名称": ["网页 URL", "CSS 选择器"]
  }
}
```

### 添加新的数据源

#### 添加 RSS 源

在 `config.json` 中的对应类别下添加：
```json
"新来源名称": "https://example.com/feed.xml"
```

#### 添加网页爬虫源

在 `config.json` 中的对应类别下添加：
```json
"新来源名称": ["https://example.com/news", "h2 a, h3 a"]
```

其中第二个参数是 CSS 选择器，用于定位文章链接。

## 🎨 自定义样式

### 修改主题颜色

编辑 `.streamlit/config.toml`：
```toml
[theme]
primaryColor = "#2563eb"  # 主色调
backgroundColor = "#f5f7fa"  # 背景色
textColor = "#1f2937"  # 文字色
```

### 修改 CSS 样式

编辑 `app.py` 中的 `modern_css` 变量，自定义卡片样式、颜色、动画等。

## 📊 数据存储

应用数据存储在以下目录：

```
vibecoding_v2/
├── .intel_store/          # 文章数据存储
│   ├── media.json         # 媒体文章
│   ├── assoc.json         # 协会文章
│   └── update_state.json  # 更新状态
├── .intel_cache/          # 缓存数据
│   └── *.json             # 翻译和 AI 摘要缓存
```

## 🔧 故障排除

### 问题：页面加载缓慢

**解决方案**：
- 检查网络连接
- 清除浏览器缓存
- 在 Streamlit Cloud 中增加资源配置
- 减少数据源数量或增加更新间隔

### 问题：某些数据源无法爬取

**解决方案**：
- 检查网站是否改变了 HTML 结构，更新 CSS 选择器
- 检查网站是否有反爬虫机制，考虑添加延迟或更改 User-Agent
- 测试 URL 是否仍然有效

### 问题：翻译功能不工作

**解决方案**：
- 检查网络连接
- 检查 `deep-translator` 库是否正确安装
- 尝试手动清除缓存文件（`.intel_cache/` 目录）

## 📈 性能优化建议

### 1. 缓存优化
- 定期清理 `.intel_cache/` 目录中的过期缓存
- 增加翻译缓存的 TTL（生存时间）

### 2. 数据源优化
- 定期检查数据源的有效性
- 移除响应缓慢或经常失败的数据源
- 为不同类型的数据源设置不同的更新间隔

### 3. 部署优化
- 在 Streamlit Cloud 中使用 "Advanced settings" 增加超时时间
- 考虑使用 CDN 加速静态资源
- 定期备份 `.intel_store/` 目录中的数据

## 🔐 安全建议

1. **API Key 管理**: 如使用 AI 摘要功能，将 API Key 存储在环境变量中，不要提交到代码仓库
2. **数据隐私**: 定期检查存储的文章数据，确保不包含敏感信息
3. **依赖更新**: 定期更新 `requirements.txt` 中的依赖，修复安全漏洞

## 📝 文件结构

```
vibecoding_v2/
├── app.py                 # 主应用文件
├── config.json            # 数据源配置
├── requirements.txt       # Python 依赖
├── README.md              # 本文档
├── .streamlit/
│   └── config.toml        # Streamlit 配置
├── .intel_store/          # 数据存储（自动创建）
└── .intel_cache/          # 缓存存储（自动创建）
```

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 改进方向

- [ ] 添加更多数据源
- [ ] 支持自定义关键词过滤
- [ ] 实现用户偏好保存
- [ ] 添加数据导出功能
- [ ] 支持邮件订阅
- [ ] 集成更多 AI 模型

## 📄 许可证

本项目采用 MIT 许可证。

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：
- 提交 GitHub Issue
- 发送邮件至 [adala7@sina.com]

---

**最后更新**: 2024 年 6 月
**版本**: 2.0.0
