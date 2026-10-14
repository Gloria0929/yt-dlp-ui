const { app, BrowserWindow, dialog, ipcMain, session, shell } = require('electron');
const { spawn } = require('node:child_process');
const { createServer } = require('node:net');
const { createWriteStream, existsSync } = require('node:fs');
const { promises: fs } = require('node:fs');
const path = require('node:path');
const { pipeline } = require('node:stream/promises');
const { Readable } = require('node:stream');
const { randomBytes } = require('node:crypto');

const projectRoot = path.join(__dirname, '..');
const isPackaged = app.isPackaged;
let backend;
let window;
let backendPort;
let backendToken;
let saveDirectory;
let shuttingDown = false;

function backendExecutable() {
  if (isPackaged) return path.join(process.resourcesPath, 'backend', process.platform === 'win32' ? 'frame-get-api.exe' : 'frame-get-api');
  const virtualenv = path.join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  return existsSync(virtualenv) ? virtualenv : (process.platform === 'win32' ? 'python' : 'python3');
}

function reservePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      server.close((error) => error ? reject(error) : resolve(address.port));
    });
  });
}

function stopBackend() {
  if (!backend || backend.exitCode !== null || backend.killed) return;
  // The API cleans up worker process groups in its shutdown handler.
  backend.kill('SIGTERM');
  const processToStop = backend;
  const timer = setTimeout(() => {
    if (processToStop.exitCode === null) processToStop.kill('SIGKILL');
  }, 5000);
  timer.unref();
}

async function waitForBackend(child, url) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (child.exitCode !== null) throw new Error('下载服务启动失败，请检查 Python 环境与依赖。');
    try {
      const response = await fetch(url, { headers: { 'X-Desktop-Token': backendToken }, signal: AbortSignal.timeout(500) });
      if (response.ok && (await response.json()).ok) return;
    } catch { /* Wait until FastAPI accepts requests. */ }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('下载服务启动超时，请重新打开应用。');
}

function createWindow() {
  window = new BrowserWindow({
    width: 1320, height: 860, minWidth: 820, minHeight: 600,
    title: 'FRAME/GET', backgroundColor: '#f1ede3',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true, nodeIntegration: false, sandbox: true,
    },
  });
  window.once('ready-to-show', () => window.show());
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
  window.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(`http://127.0.0.1:` + backendPort + '/')) event.preventDefault();
  });
  window.loadURL(`http://127.0.0.1:` + backendPort + '/');
}

function safeParts(relativePath) {
  const parts = String(relativePath || '').split(/[\\/]+/);
  if (!parts.length || parts.some((part) => !part || part === '.' || part === '..' || part.includes(':') || part.includes('\0'))) {
    throw new Error('下载文件名无效');
  }
  return parts;
}

function targetPath(file) {
  const parts = safeParts(file.relativePath || file.name);
  return path.join(saveDirectory, ...parts);
}

async function saveFile(file, overwriteMode) {
  if (!/^\/api\/files\/[A-Za-z0-9_-]+\/[A-Za-z0-9_-]+$/.test(file.downloadUrl)) {
    throw new Error('下载地址无效');
  }
  const destination = targetPath(file);
  if (overwriteMode === 'skip' && existsSync(destination)) {
    await fetch(`http://127.0.0.1:` + backendPort + file.downloadUrl, {
      method: 'DELETE', headers: { 'X-Desktop-Token': backendToken },
    });
    return { skipped: true, relativePath: file.relativePath };
  }
  await fs.mkdir(path.dirname(destination), { recursive: true });
  const url = `http://127.0.0.1:` + backendPort + file.downloadUrl;
  const response = await fetch(url, { headers: { 'X-Desktop-Token': backendToken } });
  if (!response.ok || !response.body) throw new Error('文件传输失败，请重新创建任务');
  const temporary = destination + '.frame-get-' + randomBytes(6).toString('hex') + '.tmp';
  try {
    await pipeline(Readable.fromWeb(response.body), createWriteStream(temporary, { flags: 'wx' }));
    await fs.rename(temporary, destination);
  } catch (error) {
    await fs.rm(temporary, { force: true });
    throw error;
  }
  return { skipped: false, relativePath: file.relativePath };
}

ipcMain.handle('desktop:choose-directory', async () => {
  const selected = await dialog.showOpenDialog(window, {
    title: '选择下载文件夹', defaultPath: saveDirectory,
    properties: ['openDirectory', 'createDirectory'],
  });
  if (!selected.canceled && selected.filePaths[0]) saveDirectory = selected.filePaths[0];
  return saveDirectory;
});
ipcMain.handle('desktop:save-files', async (_event, files, overwriteMode) => {
  if (!Array.isArray(files) || files.length > 200) throw new Error('文件数量无效');
  const results = [];
  for (const file of files) results.push(await saveFile(file, overwriteMode));
  return { directory: saveDirectory, results };
});
ipcMain.handle('desktop:save-directory', () => saveDirectory);
ipcMain.handle('desktop:reveal-file', (_event, absolutePath) => {
  // 只允许定位到用户自己选定目录里的文件，避免被前端引导到任意路径。
  const resolved = path.resolve(String(absolutePath || ''));
  const root = path.resolve(saveDirectory);
  if (resolved !== root && !resolved.startsWith(root + path.sep)) throw new Error('路径不在当前保存目录内');
  if (!existsSync(resolved)) throw new Error('文件已被移动或删除');
  shell.showItemInFolder(resolved);
  return true;
});

app.on('before-quit', () => { shuttingDown = true; stopBackend(); });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => {
  if (!shuttingDown && BrowserWindow.getAllWindows().length === 0 && backend) createWindow();
});

app.whenReady().then(async () => {
  saveDirectory = app.getPath('downloads');
  try {
    backendPort = await reservePort();
    backendToken = randomBytes(32).toString('hex');
    const frontendDir = isPackaged ? path.join(process.resourcesPath, 'frontend') : path.join(projectRoot, 'client', 'dist');
    const ffmpegDir = path.join(process.resourcesPath, 'ffmpeg');
    const env = {
      ...process.env, PORT: String(backendPort), YTDLP_DESKTOP_TOKEN: backendToken,
      YTDLP_FRONTEND_DIR: frontendDir,
      YTDLP_TEMP_DIR: path.join(app.getPath('userData'), 'tasks'),
      PATH: (isPackaged ? ffmpegDir + path.delimiter : '') + (process.env.PATH || ''),
    };
    const command = backendExecutable();
    backend = spawn(command, isPackaged ? [] : ['-m', 'server.desktop'], {
      cwd: isPackaged ? path.dirname(command) : projectRoot,
      env, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
    });
    backend.stderr.on('data', (data) => console.error('[backend]', String(data)));
    backend.on('error', (error) => console.error('[backend]', error));
    backend.on('exit', () => {
      if (!shuttingDown && window && !window.isDestroyed()) {
        dialog.showErrorBox('下载服务已停止', '下载服务意外退出。请重新启动 FRAME/GET。');
        app.quit();
      }
    });
    session.defaultSession.webRequest.onBeforeSendHeaders({ urls: [`http://127.0.0.1:` + backendPort + '/api/*'] }, (details, callback) => {
      details.requestHeaders['X-Desktop-Token'] = backendToken;
      callback({ requestHeaders: details.requestHeaders });
    });
    await waitForBackend(backend, `http://127.0.0.1:` + backendPort + '/api/health');
    createWindow();
  } catch (error) {
    stopBackend();
    dialog.showErrorBox('无法启动 FRAME/GET', String(error.message || error));
    app.quit();
  }
});
