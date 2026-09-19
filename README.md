# FRAME/GET

一个面向日常使用的 yt-dlp 网页界面。前端使用 Vue 3，后端使用 FastAPI，并通过 Python 的 import yt_dlp 直接解析和下载媒体。

界面只保留常用设置：

- 视频或音频下载
- 最佳、4K、1080p、720p、480p 画质
- MP4 / MKV 封装和 MP3 / M4A / FLAC / WAV / Opus 音频
- 人工字幕、自动字幕和字幕语言
- 自定义文件名规则和已有文件覆盖策略
- 播放列表范围、最大文件大小和下载限速
- 封面保存/嵌入、媒体信息和信息 JSON
- 并发分片与失败重试
- 从本机浏览器读取登录状态
- HTTP / HTTPS / SOCKS 代理
- 多链接顺序下载、实时进度、日志和取消任务

## 安装

需要 Node.js 18+、Python 3.11+ 和 ffmpeg。音频提取、音视频合并、字幕嵌入和媒体信息写入依赖 ffmpeg。

    python3 -m pip install -r requirements.txt
    npm install
    npm install --prefix client

## 开发运行

    npm run dev

- 前端：http://localhost:5173
- FastAPI：http://127.0.0.1:3000
- API 文档：http://127.0.0.1:3000/docs

Vite 会把 /api 请求代理到 FastAPI。

## 生产运行

    npm run build
    npm run server

构建完成后 FastAPI 会在 http://127.0.0.1:3000 同时提供前端页面和 API。

下载任务在服务端的独立临时目录中完成，随后由浏览器保存到访问者自己的电脑。Chrome、Edge 等支持 File System Access API 的浏览器可以在页面中选择本机文件夹；其他浏览器会使用默认下载目录或浏览器的保存对话框。成功传输的临时文件会立即删除，未领取文件默认一小时后清理。

## Docker 部署

构建并启动：

    docker compose up -d --build

访问：

    http://localhost:3000

查看状态与日志：

    docker compose ps
    docker compose logs -f yt-dlp-ui

停止服务：

    docker compose down

Compose 默认使用 4 GB 的 tmpfs 作为 yt-dlp 和 ffmpeg 的临时空间，不会把下载结果持久化到镜像或 Docker volume。可以通过环境变量调整：

    APP_PORT=8080 YTDLP_TMPFS_SIZE=8g YTDLP_MAX_WORKERS=2 docker compose up -d --build

- `APP_PORT`：仅绑定宿主机回环地址的调试端口，默认 `3000`
- `YTDLP_TMPFS_SIZE`：所有并发任务共享的临时空间，默认 `4g`
- `YTDLP_MAX_WORKERS`：同时运行的解析/下载进程数，默认 `4`
- `YTDLP_TASK_TTL`：浏览器未领取文件的保留秒数，默认 `3600`

### 接入已有的 Nginx 与 Cloudflare

如果服务器已有 Nginx 占用宿主机的 `80` 端口，不要让本项目再次绑定 `80`。首次部署先创建共用网络，把现有 Nginx 容器接入该网络，再启动本项目：

    docker network create frame-get-network
    docker network connect frame-get-network nginx
    docker compose up -d --build

网络只需创建和连接一次；如果命令提示网络已存在或 Nginx 已连接，可以忽略。将 `deploy/nginx-frame-get.conf.example` 复制到现有 Nginx 的 `/etc/nginx/conf.d/`，把示例域名改成 Cloudflare 中使用的域名，然后检查并重载：

    docker exec nginx nginx -t
    docker exec nginx nginx -s reload

配置中的上游地址是 `frame-get:3000`，流量路径为 `Cloudflare -> Nginx:80 -> frame-get:3000`。Cloudflare 对外提供 HTTPS，所以浏览器可以使用本机文件夹选择功能；不支持该 API 的浏览器会自动回退到标准文件下载。Nginx 容器被重新创建后，需要确认它仍连接在 `frame-get-network` 网络中。

当前任务文件索引保存在单个 FastAPI 进程内，因此容器内不要启动多个 Uvicorn worker。需要横向扩容时，应把任务索引和文件存储改为 Redis 与共享对象存储。

## 测试

    npm test

测试覆盖任务文件隔离与清理、URL 与设置校验、画质选择、音频后处理、命令转义和分享文案链接解析。

## 后端结构

- server/app.py：FastAPI 路由、SSE 流和任务生命周期
- server/downloader.py：原生 yt_dlp.YoutubeDL 集成、进度钩子与错误提示
- server/models.py：请求模型与输入校验
- server/task_files.py：临时任务文件、一次性下载地址与超时清理

每个解析或下载任务在独立 Python 进程中运行。浏览器取消请求或断开连接时，FastAPI 会终止对应任务及其 ffmpeg 子进程并删除临时目录。文件 URL 使用不可预测的任务令牌，文件传输完成后立即失效。
