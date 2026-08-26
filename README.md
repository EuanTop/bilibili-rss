# Bilibili RSS

一个轻量、可自托管的 Bilibili UP 主公开视频 RSS 服务。订阅地址可直接加入 RSS 阅读器，也可在浏览器中查看。

支持：

- 按 UP 主 UID 生成 RSS 2.0；
- 展示封面、简介及播放、评论、点赞等数据；
- 提供 JSON API 和健康检查；
- 自动识别完整 cURL、Cookie 请求头、浏览器表格、JSON、Netscape 等 Cookie 格式。

## 快速开始

需要 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run bilibili-rss cookie set --clipboard
uv run bilibili-rss cookie verify
uv run bilibili-rss serve
```

打开以下地址，将 `<uid>` 替换为 UP 主 UID：

```text
http://127.0.0.1:8765/rss/<uid>
```

Cookie 所属账号与订阅对象无关，可以订阅任意公开 UP 主。

## 获取 Cookie

1. 在浏览器登录 Bilibili。
2. 打开开发者工具的 Network（网络）面板并刷新页面。
3. 右键任意发往 `bilibili.com` 的请求，选择 Copy as cURL（复制为 cURL）。
4. 运行 `uv run bilibili-rss cookie set --clipboard`。

程序会从剪贴板内容中提取 Cookie，不会输出 Cookie 值。Cookie 仅保存在 `data/bilibili.cookie`，不会进入 Git；过期后重新执行上述命令即可。

也可交互粘贴或从标准输入读取：

```bash
uv run bilibili-rss cookie set
uv run bilibili-rss cookie set --stdin
```

## Docker Compose

先按上面的方式写入 Cookie，然后启动：

```bash
docker compose up -d --build
```

默认只监听 `127.0.0.1:8765`。如需允许其他设备访问，在 `.env` 中设置 `BILIBILI_RSS_BIND=0.0.0.0`，并自行配置可信的反向代理和访问控制。

## 接口

```text
GET /                         服务信息
GET /rss/<uid>                RSS 订阅与浏览页面
GET /api/users/<uid>/videos   JSON 视频数据
GET /health                   健康检查
GET /api/health               兼容健康检查
```

RSS 默认补查最近 5 条视频的详细指标。使用 `/rss/<uid>?detail_limit=0` 可关闭补查。

## 配置与开发

复制 `.env.example` 为 `.env` 可调整端口、缓存、请求限速和数据目录。Cookie 只从 `BILIBILI_COOKIE_FILE` 指定的文件读取，不支持通过环境变量直接传入。

```bash
uv run bilibili-rss config check
uv run pytest
uv run ruff check bilibili_rss_service tests
```

## 免责声明

本项目仅供学习和技术研究使用，与 Bilibili 官方无关。请勿用于违反平台规则或法律法规的用途。

## License

[MIT](./LICENSE)
