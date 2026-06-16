# 部署指南

本文档详细说明如何将行业情报系统部署到 Streamlit Cloud。

## 前置条件

- GitHub 账号
- Streamlit Cloud 账号（免费注册）
- 本地已安装 Git

## 部署步骤

### 第 1 步：准备 GitHub 仓库

#### 1.1 创建 GitHub 仓库

1. 登录 [GitHub](https://github.com)
2. 点击右上角 "+" → "New repository"
3. 填写仓库信息：
   - **Repository name**: `vibecoding_v2`
   - **Description**: Industry Intelligence System v2.0
   - **Visibility**: Public（Streamlit Cloud 需要公开仓库）
4. 点击 "Create repository"

#### 1.2 本地初始化 Git 仓库

```bash
cd /path/to/vibecoding_v2

# 初始化 Git
git init

# 添加所有文件
git add .

# 首次提交
git commit -m "Initial commit: Industry Intelligence System v2.0"

# 添加远程仓库
git remote add origin https://github.com/YOUR_USERNAME/vibecoding_v2.git

# 重命名分支为 main（如果需要）
git branch -M main

# 推送到 GitHub
git push -u origin main
```

#### 1.3 验证推送成功

访问 `https://github.com/YOUR_USERNAME/vibecoding_v2`，确认所有文件已上传。

### 第 2 步：在 Streamlit Cloud 部署

#### 2.1 访问 Streamlit Cloud

1. 访问 [Streamlit Cloud](https://streamlit.io/cloud)
2. 点击 "Sign in with GitHub"
3. 授权 Streamlit Cloud 访问你的 GitHub 账号

#### 2.2 创建新应用

1. 点击 "New app"
2. 在弹出的对话框中填写：
   - **Repository**: `YOUR_USERNAME/vibecoding_v2`
   - **Branch**: `main`
   - **Main file path**: `app.py`
3. 点击 "Deploy"

#### 2.3 等待部署完成

Streamlit Cloud 将自动：
- 克隆你的仓库
- 安装 `requirements.txt` 中的依赖
- 启动应用

部署通常需要 2-5 分钟。完成后，你将获得一个公开的 URL，例如：
```
https://vibecoding-v2.streamlit.app
```

### 第 3 步：配置环境变量（可选）

如果你的应用需要 API Key 或其他敏感信息，可以通过 Streamlit Cloud 的 Secrets 功能安全地配置：

#### 3.1 访问 Secrets 设置

1. 在应用页面，点击右上角 "⋮" → "Settings"
2. 选择 "Secrets"

#### 3.2 添加密钥

在 Secrets 编辑器中添加环境变量，格式如下：

```toml
# Anthropic API Key（用于 AI 摘要功能）
ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxxx"

# 其他配置
DEBUG = "false"
```

#### 3.3 在应用中使用

在 `app.py` 中通过以下方式访问：

```python
import streamlit as st
import os

api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
```

## 更新应用

当你在本地修改代码后，只需推送到 GitHub，Streamlit Cloud 将自动重新部署：

```bash
# 修改代码后
git add .
git commit -m "Update: Add new features"
git push origin main
```

Streamlit Cloud 会自动检测到新的提交，并重新部署应用。

## 监控与维护

### 查看日志

1. 在应用页面，点击右上角 "⋮" → "View logs"
2. 查看实时日志输出

### 管理资源

1. 点击 "Settings" → "Advanced settings"
2. 可以调整：
   - **Client max message size**: 上传文件大小限制
   - **Timeout**: 请求超时时间
   - **Server address**: 自定义域名（付费功能）

### 性能监控

Streamlit Cloud 提供基本的性能指标：
- 应用加载时间
- 内存使用情况
- 并发用户数

## 故障排除

### 问题：部署失败

**错误信息**: `ModuleNotFoundError: No module named 'xxx'`

**解决方案**:
1. 检查 `requirements.txt` 是否包含所有依赖
2. 确保依赖名称拼写正确
3. 更新 `requirements.txt` 并推送到 GitHub

### 问题：应用启动缓慢

**原因**: 
- 依赖安装时间长
- 数据加载时间长
- 网络连接慢

**解决方案**:
1. 优化数据加载逻辑
2. 使用 `@st.cache_data` 缓存计算结果
3. 在 Streamlit Cloud 中增加超时时间

### 问题：数据源无法访问

**原因**:
- 网站被墙或地域限制
- 网站反爬虫机制
- 网络连接问题

**解决方案**:
1. 检查 `config.json` 中的 URL 是否有效
2. 更新 CSS 选择器以适应网站变化
3. 添加重试机制和延迟

## 高级配置

### 自定义域名

Streamlit Cloud 的付费计划支持自定义域名。配置步骤：

1. 在 "Settings" → "Custom domain" 中添加你的域名
2. 按照 DNS 配置说明更新 CNAME 记录
3. 等待 DNS 生效（通常 24 小时）

### 集成 CI/CD

如果你想在推送代码时自动运行测试，可以使用 GitHub Actions：

创建 `.github/workflows/test.yml`:

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/
```

## 备份与恢复

### 备份数据

Streamlit Cloud 上的应用数据（`.intel_store/` 目录）存储在临时文件系统中，应用重启后会丢失。

**解决方案**: 使用云存储服务（如 AWS S3、Google Cloud Storage）定期备份数据：

```python
import json
import boto3

def backup_to_s3(local_path, s3_key):
    s3 = boto3.client('s3')
    with open(local_path, 'rb') as f:
        s3.upload_fileobj(f, 'your-bucket', s3_key)
```

### 恢复数据

从云存储恢复数据：

```python
def restore_from_s3(s3_key, local_path):
    s3 = boto3.client('s3')
    with open(local_path, 'wb') as f:
        s3.download_fileobj('your-bucket', s3_key, f)
```

## 性能优化建议

### 1. 使用缓存

```python
@st.cache_data(ttl=3600)
def load_articles():
    # 加载文章数据
    return articles
```

### 2. 优化数据源

- 减少数据源数量
- 增加更新间隔
- 移除响应缓慢的源

### 3. 前端优化

- 使用分页加载而不是一次性加载所有数据
- 优化 CSS 和 JavaScript
- 压缩图片和资源

## 成本估算

Streamlit Cloud 的免费计划包括：
- 3 个应用
- 1 GB 存储
- 基本支持

如需更多资源，可升级到付费计划。

## 获取帮助

- [Streamlit 文档](https://docs.streamlit.io)
- [Streamlit 社区论坛](https://discuss.streamlit.io)
- [GitHub Issues](https://github.com/streamlit/streamlit/issues)

---

**最后更新**: 2024 年 6 月
