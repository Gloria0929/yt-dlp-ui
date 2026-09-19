/** Parse SSE across arbitrary network / UTF-8 boundaries, including a final partial frame. */
export async function consumeEvents(body, onEvent) {
  if (!body) throw new Error('服务端未返回下载数据流');
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminal = false;
  async function dispatch(frame) {
    const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).trimStart()).join('\n');
    if (!data) return;
    const event = JSON.parse(data);
    if (event.type === 'done' || event.type === 'error') terminal = true;
    await onEvent(event);
  }
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop();
      for (const frame of frames) await dispatch(frame);
      if (done) break;
    }
    if (buffer.trim()) await dispatch(buffer);
    if (!terminal) throw new Error('下载连接意外中断，请重试；已下载的部分可继续下载');
  } finally { reader.releaseLock(); }
}
