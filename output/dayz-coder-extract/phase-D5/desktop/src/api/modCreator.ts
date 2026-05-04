// D5 — Mod Creator SSE consumer.

import { sidecarBaseUrl } from "./client";

export interface ModCreatorEvent {
  // 'control' events
  event?: "started" | "done" | "client_disconnected" | "replay_complete";
  mod?: string;
  model?: string;
  files?: string[];
  summary?: string;
  iterations?: number;

  // file_written
  path?: string;
  bytes?: number;

  // thought
  text?: string;

  // error
  error?: string;
}

export type ModCreatorEventType = "thought" | "file_written" | "control" | "error";

export interface ModCreatorMessage {
  type: ModCreatorEventType;
  data: ModCreatorEvent;
  receivedAt: number;
}

export interface ModCreatorPitch {
  name: string;
  pitch: string;
  author?: string;
}

/** Stream the Mod Creator. Calls onEvent for each SSE message. Returns a
 * cancel() function the caller can invoke to abort. */
export async function streamModCreator(
  pitch: ModCreatorPitch,
  onEvent: (msg: ModCreatorMessage) => void,
): Promise<{ cancel: () => void; promise: Promise<void> }> {
  const base = await sidecarBaseUrl();
  const controller = new AbortController();

  async function run() {
    const res = await fetch(`${base}/api/mod-creator`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pitch),
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = await res.text().catch(() => "");
      throw new Error(`/api/mod-creator failed: ${res.status} ${err}`);
    }
    const reader = res.body?.getReader();
    if (!reader) throw new Error("no readable stream");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE framing: messages separated by \n\n
      let idx;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const evt = parseSseFrame(raw);
        if (evt) onEvent({ ...evt, receivedAt: Date.now() });
      }
    }
  }

  return {
    cancel: () => controller.abort(),
    promise: run(),
  };
}

function parseSseFrame(raw: string): { type: ModCreatorEventType; data: ModCreatorEvent } | null {
  const lines = raw.split("\n");
  let event: string | null = null;
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  let data: ModCreatorEvent;
  try { data = JSON.parse(dataLines.join("\n")); }
  catch { return null; }
  const type = (event === "file_written" || event === "thought" || event === "error" || event === "control")
    ? event : "control";
  return { type, data };
}
