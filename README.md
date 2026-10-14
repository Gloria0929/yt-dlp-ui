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

## 桌面版

桌面版使用 Electron 承载现有 Vue 界面，并在窗口启动时拉起随应用打包的 Python 下载服务。打开后即可使用，不需要另开终端或浏览器。

首次准备桌面构建环境：

    npm install
    npm run desktop:setup

本机开发运行（自动构建前端并打开桌面窗口）：

    npm run desktop:dev

构建当前平台的安装包：

    npm run desktop:dist

只生成未压缩的应用目录用于本地验证：

    npm run desktop:package

桌面版特性：

- 下载服务只监听 `127.0.0.1` 的随机端口，并用每次启动生成的令牌校验 `/api/` 请求
- 内置 arm64 原生 ffmpeg，无需用户单独安装
- 原生文件夹选择，下载引擎直接写入所选目录，默认是系统下载目录
- 下载完成后可在任务卡片里“在文件夹中显示”，直接跳到访达 / 资源管理器中的文件
- 启动时自动合并系统钥匙串里的证书，代理软件（如 Quantumult X、Surge）的 HTTPS 解密证书无需手动配置
- 关闭窗口时自动结束下载服务及其子进程，临时文件在用户数据目录中清理

桌面版相对网页版的区别：

| 能力 | 网页版 | 桌面版 |
| --- | --- | --- |
| 文件落盘 | 先下到服务端临时目录，再经浏览器中转（需 File System Access API） | 下载引擎直接写入所选本机目录，不经浏览器中转 |
| 保存位置 | 只能拿到文件夹句柄，拿不到真实路径 | 显示并记住绝对路径，可随时更换 |
| 下载后操作 | 无 | 在文件夹中显示 |
| 大文件 | 受浏览器内存与下载管理器影响 | 直接落盘，无中转 |

`npm run desktop:backend` 会把 `server/desktop.py` 打包成 `desktop/build/frame-get-api`，并把 ffmpeg 复制到 `desktop/build/ffmpeg`，两者会作为 Electron 的 extraResources 一起分发。

对已打包的后端做一次真实下载回归（需要联网，会启动冻结后端并走完整下载流程）：

    npm run desktop:backend
    npm run desktop:smoke

应用图标由脚本生成（需要 Pillow，仅打包时用到）：

    python3 desktop/build_icon.py

会写出 `build/icon.icns` 与 `build/icon.png`，electron-builder 在打包时自动取用。

### macOS 首次打开

当前安装包没有 Apple 开发者签名。首次打开时请在 `release/mac-arm64/FRAME GET.app` 上右键选择“打开”，或执行：

    xattr -dr com.apple.quarantine "release/mac-arm64/FRAME GET.app"

否则系统会提示应用已损坏或来自未识别的开发者。也可以执行 `npm run desktop:package` 生成未压缩的应用目录直接运行。

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

Compose 会同时构建两个容器：

- `frame-get`：内置 Nginx，提供 Vue 页面并代理 `/api/`
- `frame-get-api`：FastAPI、原生 `yt_dlp`、Node.js 与 ffmpeg，仅在 Docker 网络内监听

两个容器通过自动创建的 `frame-get-internal-network` 通信，不需要加入服务器原有 Nginx 的 Docker 网络。

构建并启动：

    docker compose up -d --build

访问：

    http://localhost:3000

查看状态与日志：

    docker compose ps
    docker compose logs -f nginx backend

停止服务：

    docker compose down

Compose 默认使用 4 GB 的 tmpfs 作为 yt-dlp 和 ffmpeg 的临时空间，不会把下载结果持久化到镜像或 Docker volume。可以通过环境变量调整：

    APP_PORT=8080 YTDLP_TMPFS_SIZE=8g YTDLP_MAX_WORKERS=2 docker compose up -d --build

- `APP_HOST`：宿主机监听地址，默认 `0.0.0.0`，允许局域网访问
- `APP_PORT`：宿主机监听端口，默认 `3000`
- `YTDLP_TMPFS_SIZE`：所有并发任务共享的临时空间，默认 `4g`
- `YTDLP_MAX_WORKERS`：同时运行的解析/下载进程数，默认 `4`
- `YTDLP_TASK_TTL`：浏览器未领取文件的保留秒数，默认 `3600`

项目内置的 Nginx 发布在宿主机 `3000` 端口，不会占用现有 Nginx 使用的 `80` 端口。Cloudflare Tunnel 可将 `video.blackwing.icu` 的服务地址直接设置为：

    http://localhost:3000

这种方式不需要修改服务器上原有的 Nginx。如果 Cloudflare 流量必须先进入现有 Nginx 的 `80` 端口，可以使用 `deploy/nginx.conf` 替换服务器现有配置；其中已经加入 `video.blackwing.icu -> http://172.17.0.1:3000`。`172.17.0.1` 是现有 Nginx 容器访问宿主机发布端口所使用的 Docker 网关地址。配置同时关闭了 SSE 和下载响应的代理缓冲。替换后先检查再重载：

    docker cp nginx:/etc/nginx/nginx.conf ./nginx.conf.backup
    docker cp deploy/nginx.conf nginx:/etc/nginx/nginx.conf
    docker exec nginx nginx -t
    docker exec nginx nginx -s reload

项目内置 Nginx 继续负责静态页面和 API 转发，服务器原有 Nginx 只负责按照子域名将请求转发到项目的 `3000` 端口。

局域网内也可以直接访问 `http://服务器内网地址:3000`，例如 `http://192.168.2.100:3000`。如果只允许本机和 Nginx 访问，可以设置 `APP_HOST=127.0.0.1` 后重新创建容器。

当前任务文件索引保存在单个 FastAPI 进程内，因此容器内不要启动多个 Uvicorn worker。需要横向扩容时，应把任务索引和文件存储改为 Redis 与共享对象存储。

## 测试

    npm test

测试覆盖任务文件隔离与清理、URL 与设置校验、画质选择、音频后处理、命令转义和分享文案链接解析。

## 后端结构

- server/app.py：FastAPI 路由、SSE 流和任务生命周期
- server/downloader.py：原生 yt_dlp.YoutubeDL 集成、进度钩子与错误提示
- server/models.py：请求模型与输入校验
- server/task_files.py：临时任务文件、一次性下载地址与超时清理，以及直写模式下的目录快照
- server/certs.py：合并 certifi 与 macOS 钥匙串证书，供 yt-dlp 与代理软件共存
- server/desktop.py：冻结后端入口，读取 PORT 后启动同一套 FastAPI 应用

每个解析或下载任务在独立 Python 进程中运行。浏览器取消请求或断开连接时，FastAPI 会终止对应任务及其 ffmpeg 子进程并删除临时目录。文件 URL 使用不可预测的任务令牌，文件传输完成后立即失效。
