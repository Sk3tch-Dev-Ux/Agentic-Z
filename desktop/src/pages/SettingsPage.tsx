// Settings page — Anthropic API key, Voyage API key, author handle.

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Key, CheckCircle2, XCircle, Loader2, Eye, EyeOff } from "lucide-react";
import { SettingsApi } from "../api/settings";

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: SettingsApi.get });
  const queryClient = useQueryClient();

  const [anthropicKey, setAnthropicKey] = useState("");
  const [voyageKey, setVoyageKey] = useState("");
  const [author, setAuthor] = useState("");
  const [showAnthropic, setShowAnthropic] = useState(false);
  const [showVoyage, setShowVoyage] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const saveMut = useMutation({
    mutationFn: () => SettingsApi.update({
      anthropic_key: anthropicKey || undefined,
      voyage_key: voyageKey || undefined,
      author: author || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setAnthropicKey(""); setVoyageKey(""); setAuthor("");
    },
  });

  const testMut = useMutation({
    mutationFn: SettingsApi.testAnthropic,
    onSuccess: (r) => {
      if (r.ok) {
        setTestResult({ ok: true, msg: `OK · ${r.model} · ${r.latency_ms}ms` });
      } else {
        setTestResult({ ok: false, msg: r.error || "unknown error" });
      }
    },
    onError: (e) => setTestResult({ ok: false, msg: (e as Error).message }),
  });

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Key className="w-5 h-5 text-accent-bright" /> Settings
        </h1>
        <p className="text-muted text-sm mt-1">
          API keys are written to <code>{settings.data?.env_path || ".env"}</code> at
          the repo root (gitignored). The sidecar reads from there at startup.
        </p>
      </div>

      {/* Anthropic */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="font-medium">Anthropic API key</span>
          {settings.data?.anthropic_key_set ? (
            <span className="pill-ok flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> set ({settings.data.anthropic_key_masked})
            </span>
          ) : (
            <span className="pill-warn flex items-center gap-1">
              <XCircle className="w-3 h-3" /> not set
            </span>
          )}
        </div>
        <p className="text-xs text-muted">
          Used by the Mod Creator and (in D6+) the Audit / Ship It buttons.
          Get one at{" "}
          <a href="https://console.anthropic.com/" className="text-accent-bright underline" target="_blank">
            console.anthropic.com
          </a>. Costs are pay-as-you-go on your account; the app never sees your dollars.
        </p>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type={showAnthropic ? "text" : "password"}
              value={anthropicKey}
              onChange={(e) => setAnthropicKey(e.target.value)}
              placeholder="sk-ant-…"
              className="w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent pr-10"
            />
            <button
              onClick={() => setShowAnthropic((s) => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white"
            >
              {showAnthropic ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <button
            onClick={() => saveMut.mutate()}
            disabled={!anthropicKey || saveMut.isPending}
            className="btn-accent"
          >
            {saveMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save"}
          </button>
          <button
            onClick={() => testMut.mutate()}
            disabled={!settings.data?.anthropic_key_set || testMut.isPending}
            className="btn flex items-center gap-2"
          >
            {testMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />} Test
          </button>
        </div>
        {testResult && (
          <div className={"text-xs flex items-center gap-2 " + (testResult.ok ? "text-ok" : "text-err")}>
            {testResult.ok ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
            {testResult.msg}
          </div>
        )}
      </div>

      {/* Voyage */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="font-medium">Voyage AI API key</span>
          {settings.data?.voyage_key_set ? (
            <span className="pill-ok flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> set ({settings.data.voyage_key_masked})
            </span>
          ) : (
            <span className="pill-warn flex items-center gap-1">
              <XCircle className="w-3 h-3" /> not set
            </span>
          )}
        </div>
        <p className="text-xs text-muted">
          Used by RAG search (vanilla / wiki / workspace). Free tier 200M tokens.
          Get one at{" "}
          <a href="https://dash.voyageai.com" className="text-accent-bright underline" target="_blank">
            dash.voyageai.com
          </a>.
        </p>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <input
              type={showVoyage ? "text" : "password"}
              value={voyageKey}
              onChange={(e) => setVoyageKey(e.target.value)}
              placeholder="pa-…"
              className="w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent pr-10"
            />
            <button
              onClick={() => setShowVoyage((s) => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white"
            >
              {showVoyage ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <button
            onClick={() => saveMut.mutate()}
            disabled={!voyageKey || saveMut.isPending}
            className="btn-accent"
          >
            Save
          </button>
        </div>
      </div>

      {/* Author handle */}
      <div className="panel p-4 space-y-3">
        <div className="font-medium">Author handle</div>
        <p className="text-xs text-muted">
          Written to <code>config.cpp</code> as the mod author. Cached at{" "}
          <code>.claude/local-memory/dayz-author.txt</code>.
          Currently:{" "}
          <span className="font-mono">{settings.data?.author || "(not set)"}</span>
        </p>
        <div className="flex gap-2">
          <input
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            placeholder="YourHandle"
            className="flex-1 bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
          />
          <button
            onClick={() => saveMut.mutate()}
            disabled={!author || saveMut.isPending}
            className="btn-accent"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
