import test from "node:test";
import assert from "node:assert/strict";

import { consumeEvents } from "./stream.js";

test("consumeEvents awaits asynchronous terminal handlers", async () => {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('data: {"type":"progress"}\n\n'));
      controller.enqueue(encoder.encode('data: {"type":"done","files":[]}\n\n'));
      controller.close();
    },
  });
  const handled = [];
  await consumeEvents(body, async (event) => {
    await Promise.resolve();
    handled.push(event.type);
  });
  assert.deepEqual(handled, ["progress", "done"]);
});
