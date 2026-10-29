// First-run onboarding wizard. Auto-shows when no API keys are set, dismissable
// via "Skip for now" → localStorage flag prevents re-showing.

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  X, ChevronRight, ChevronLeft, CheckCircle2, AlertTriangle, Eye, EyeOff, ExternalLink,
  Wand2, Search, Activity, Loader2, Rocket,
} from "lucide-react";
import { SettingsApi } from "../api/settings";
import { Api } from "../api/client";

const SKIP_FLAG = "agentic-z-onboarding-skipped";
const STEPS = ["welcome", "anthropic", "voyage", "author", "done"] as const;
type Step = typeof STEPS[number];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function OnboardingWizard({ open, onClose }: Props) {
  const [step, setStep] = useState<Step>("welcome");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [voyageKey, setVoyageKey] = useState("");
  const [author, setAuthor] = useState("");
  const [showAnthropic, setShowAnthropic] = useState(false);
  const [showVoyage, setShowVoyage] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const settings = useQuery({ queryKey: ["settings"], queryFn: SettingsApi.get, enabled: open });
  const preflight = useQuery({ queryKey: ["preflight"], queryFn: Api.preflight, enabled: open });
  const queryClient = useQueryClient();

  const saveMut = useMutation({
    mutationFn: SettingsApi.update,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });
  const testMut = useMutation({
    mutationFn: SettingsApi.testAnthropic,
    onSuccess: (r) => setTestResult(r.ok
      ? { ok: true,  msg: `OK · ${r.model} · ${r.latency_ms}ms` }
      : { ok: false, msg: r.error || "unknown error" }),
    onError: (e) => setTestResult({ ok: false, msg: (e as Error).message }),
  });

  // Pre-fill author from settings if present
  useEffect(() => {
    if (settings.data?.author) setAuthor(settings.data.author);
  }, [settings.data?.author]);

  if (!open) return null;

  const stepIndex = STEPS.indexOf(step);

  function next() {
    const i = STEPS.indexOf(step);
    if (i < STEPS.length - 1) setStep(STEPS[i + 1]);
  }
  function back() {
    const i = STEPS.indexOf(step);
    if (i > 0) setStep(STEPS[i - 1]);
  }
  function skipAll() {
    localStorage.setItem(SKIP_FLAG, "1");
    onClose();
  }
  function finish() {
    localStorage.setItem(SKIP_FLAG, "1");
    onClose();
  }

  async function saveAnthropicAndAdvance() {
    if (anthropicKey) {
      await saveMut.mutateAsync({ anthropic_key: anthropicKey });
      setAnthropicKey("");
    }
    next();
  }
  async function saveVoyageAndAdvance() {
    if (voyageKey) {
      await saveMut.mutateAsync({ voyage_key: voyageKey });
      setVoyageKey("");
    }
    next();
  }
  async function saveAuthorAndAdvance() {
    if (author.trim()) {
      await saveMut.mutateAsync({ author: author.trim() });
    }
    next();
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
      <div className="panel w-full max-w-2xl flex flex-col max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center px-5 py-3 border-b border-bg-elevated">
          <div className="flex items-center gap-2 font-semibold">
            <span className="text-accent-bright text-lg">⌘</span>
            Agentic-Z
            <span className="text-xs text-muted ml-2">first-run setup</span>
          </div>
          <button onClick={skipAll} className="ml-auto text-muted hover:text-white text-xs">
            Skip for now
          </button>
          <button onClick={skipAll} className="ml-3 text-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress dots */}
        <div className="px-5 py-3 border-b border-bg-elevated flex items-center gap-2">
          {STEPS.map((s, i) => (
            <div
              key={s}
              className={"h-1.5 flex-1 rounded-full " + (
                i < stepIndex ? "bg-accent" :
                i === stepIndex ? "bg-accent-bright" :
                "bg-bg-elevated"
              )}
            />
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {step === "welcome" && <WelcomeStep />}
          {step === "anthropic" && (
            <AnthropicStep
              value={anthropicKey} onChange={setAnthropicKey}
              show={showAnthropic} onToggleShow={() => setShowAnthropic((s) => !s)}
              currentlySet={settings.data?.anthropic_key_set || false}
              currentMasked={settings.data?.anthropic_key_masked || ""}
              testResult={testResult}
              onTest={() => testMut.mutate()}
              testPending={testMut.isPending}
            />
          )}
          {step === "voyage" && (
            <VoyageStep
              value={voyageKey} onChange={setVoyageKey}
              show={showVoyage} onToggleShow={() => setShowVoyage((s) => !s)}
              currentlySet={settings.data?.voyage_key_set || false}
              currentMasked={settings.data?.voyage_key_masked || ""}
            />
          )}
          {step === "author" && (
            <AuthorStep value={author} onChange={setAuthor} />
          )}
          {step === "done" && (
            <DoneStep
              hasAnthropicKey={settings.data?.anthropic_key_set || false}
              hasVoyageKey={settings.data?.voyage_key_set || false}
              author={settings.data?.author || ""}
              preflightOk={preflight.data?.overall_ok || false}
              preflightErrors={preflight.data?.errors || []}
              preflightWarnings={preflight.data?.warnings || []}
            />
          )}
        </div>

        <div className="px-5 py-3 border-t border-bg-elevated flex items-center gap-2">
          <button
            onClick={back}
            disabled={stepIndex === 0}
            className="btn flex items-center gap-1 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" /> Back
          </button>

          <span className="text-xs text-muted ml-2">
            Step {stepIndex + 1} of {STEPS.length}
          </span>

          <div className="ml-auto flex items-center gap-2">
            {step === "welcome" && (
              <button onClick={next} className="btn-accent flex items-center gap-2">
                Get started <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {step === "anthropic" && (
              <button
                onClick={saveAnthropicAndAdvance}
                className="btn-accent flex items-center gap-2"
                disabled={saveMut.isPending}
              >
                {saveMut.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                {anthropicKey ? "Save & continue" : "Skip"} <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {step === "voyage" && (
              <button
                onClick={saveVoyageAndAdvance}
                className="btn-accent flex items-center gap-2"
                disabled={saveMut.isPending}
              >
                {saveMut.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                {voyageKey ? "Save & continue" : "Skip"} <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {step === "author" && (
              <button
                onClick={saveAuthorAndAdvance}
                className="btn-accent flex items-center gap-2"
                disabled={saveMut.isPending}
              >
                {saveMut.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                Continue <ChevronRight className="w-4 h-4" />
              </button>
            )}
            {step === "done" && (
              <button onClick={finish} className="btn-accent flex items-center gap-2">
                <Rocket className="w-4 h-4" /> Open dashboard
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------- step components ----------

function WelcomeStep() {
  return (
    <div className="space-y-5">
      <h2 className="text-2xl font-bold">Welcome to Agentic-Z</h2>
      <p className="text-muted">
        DayZ modding command center. Live event feed, autonomous director runs,
        RAG search across vanilla + your code, and a Mod Creator that turns a
        plain-English pitch into a real mod scaffold.
      </p>

      <div className="grid grid-cols-2 gap-3 my-4">
        <FeatureCard icon={<Wand2 className="w-4 h-4" />} title="Mod Creator"
          desc="Pitch a mod idea. Claude writes config.cpp, scripts, types.xml — full scaffold." />
        <FeatureCard icon={<Activity className="w-4 h-4" />} title="Live event feed"
          desc="Errors classified by lane (script / config / asset / server) as they happen." />
        <FeatureCard icon={<Search className="w-4 h-4" />} title="Cmd+K search"
          desc="Semantic search across vanilla DayZ, the wiki, and your own code." />
        <FeatureCard icon={<Rocket className="w-4 h-4" />} title="Director"
          desc="Goal-pursuing agent that audits, fixes, builds, and tests mods autonomously." />
      </div>

      <p className="text-xs text-muted">
        Quick setup: 4 steps, ~2 minutes. You can skip anything and configure later in Settings.
      </p>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="panel p-3">
      <div className="flex items-center gap-2 text-accent-bright text-sm font-medium">
        {icon} {title}
      </div>
      <div className="text-xs text-muted mt-1">{desc}</div>
    </div>
  );
}

function AnthropicStep({ value, onChange, show, onToggleShow, currentlySet, currentMasked, testResult, onTest, testPending }: {
  value: string;
  onChange: (s: string) => void;
  show: boolean;
  onToggleShow: () => void;
  currentlySet: boolean;
  currentMasked: string;
  testResult: { ok: boolean; msg: string } | null;
  onTest: () => void;
  testPending: boolean;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Anthropic API key</h2>
      <p className="text-sm text-muted">
        Required for the Mod Creator and Audit features. Pay-as-you-go on{" "}
        <strong>your</strong> Anthropic account — Agentic-Z just makes the calls;
        we never see your spend.
      </p>
      <p className="text-xs text-muted">
        Get a key at{" "}
        <a href="https://console.anthropic.com/" target="_blank" className="text-accent-bright underline inline-flex items-center gap-1">
          console.anthropic.com <ExternalLink className="w-3 h-3" />
        </a>. Stored locally in <code>.env</code> at the repo root (gitignored).
      </p>

      {currentlySet && (
        <div className="text-sm flex items-center gap-2 text-ok">
          <CheckCircle2 className="w-4 h-4" />
          Key already set: <span className="font-mono">{currentMasked}</span>
          <button onClick={onTest} disabled={testPending} className="btn ml-2 text-xs flex items-center gap-1">
            {testPending && <Loader2 className="w-3 h-3 animate-spin" />} Test
          </button>
        </div>
      )}
      {testResult && (
        <div className={"text-xs flex items-center gap-2 " + (testResult.ok ? "text-ok" : "text-err")}>
          {testResult.ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
          {testResult.msg}
        </div>
      )}

      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={currentlySet ? "(leave blank to keep existing)" : "sk-ant-…"}
          className="w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent pr-10"
        />
        <button onClick={onToggleShow} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white">
          {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

function VoyageStep({ value, onChange, show, onToggleShow, currentlySet, currentMasked }: {
  value: string;
  onChange: (s: string) => void;
  show: boolean;
  onToggleShow: () => void;
  currentlySet: boolean;
  currentMasked: string;
}) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Voyage AI key <span className="text-muted text-base font-normal">(optional)</span></h2>
      <p className="text-sm text-muted">
        Powers the Cmd+K RAG search across vanilla DayZ, the wiki, and your own
        code. Free tier covers 200M tokens — full vanilla rebuild is ~5-65M tokens
        so you'll likely never pay.
      </p>
      <p className="text-xs text-muted">
        Get a key at{" "}
        <a href="https://dash.voyageai.com" target="_blank" className="text-accent-bright underline inline-flex items-center gap-1">
          dash.voyageai.com <ExternalLink className="w-3 h-3" />
        </a>. Skippable — without it, search uses local Grep instead of semantic.
      </p>

      {currentlySet && (
        <div className="text-sm flex items-center gap-2 text-ok">
          <CheckCircle2 className="w-4 h-4" />
          Key already set: <span className="font-mono">{currentMasked}</span>
        </div>
      )}

      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={currentlySet ? "(leave blank to keep existing)" : "pa-…"}
          className="w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent pr-10"
        />
        <button onClick={onToggleShow} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white">
          {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

function AuthorStep({ value, onChange }: { value: string; onChange: (s: string) => void }) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Author handle</h2>
      <p className="text-sm text-muted">
        Goes into <code>config.cpp</code> as the mod author when you scaffold a new mod.
        Cached at <code>.claude/local-memory/dayz-author.txt</code>.
      </p>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="YourHandle"
        className="w-full bg-bg border border-bg-elevated rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent"
      />
      <p className="text-xs text-muted">
        Optional. Skip and you'll be prompted on the first <code>/dayz-new-mod</code> call.
      </p>
    </div>
  );
}

function DoneStep({
  hasAnthropicKey, hasVoyageKey, author, preflightOk, preflightErrors, preflightWarnings,
}: {
  hasAnthropicKey: boolean;
  hasVoyageKey: boolean;
  author: string;
  preflightOk: boolean;
  preflightErrors: string[];
  preflightWarnings: string[];
}) {
  const ready = hasAnthropicKey && preflightOk;
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        {ready ? <CheckCircle2 className="w-6 h-6 text-ok" /> : <AlertTriangle className="w-6 h-6 text-warn" />}
        {ready ? "You're all set" : "Almost there"}
      </h2>

      <div className="panel p-4 space-y-2 text-sm">
        <Item ok={hasAnthropicKey} label="Anthropic API key" sub={hasAnthropicKey ? "ready" : "skipped — Mod Creator unavailable"} />
        <Item ok={hasVoyageKey} label="Voyage AI key" sub={hasVoyageKey ? "ready" : "skipped — Cmd+K falls back to Grep"} optional />
        <Item ok={!!author} label="Author handle" sub={author || "(not set)"} optional />
        <Item ok={preflightOk} label="DayZ environment" sub={preflightOk ? "all checks passing" : `${preflightErrors.length} error, ${preflightWarnings.length} warning`} />
      </div>

      {!preflightOk && (preflightErrors.length > 0 || preflightWarnings.length > 0) && (
        <div className="panel p-3 text-xs space-y-1">
          {preflightErrors.map((e, i) => <div key={i} className="text-err">• {e}</div>)}
          {preflightWarnings.map((w, i) => <div key={i} className="text-warn">• {w}</div>)}
        </div>
      )}

      <p className="text-sm">
        {ready ? (
          <>
            Try the Mod Creator first — click <strong>"New mod from pitch"</strong> on the dashboard.
            Or hit <kbd className="font-mono text-xs bg-bg-elevated px-1 rounded">Ctrl+K</kbd> to search.
          </>
        ) : (
          <>You can fix anything later in <strong>Settings</strong>. Click "Open dashboard" to continue.</>
        )}
      </p>
    </div>
  );
}

function Item({ ok, label, sub, optional }: { ok: boolean; label: string; sub: string; optional?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {ok
        ? <CheckCircle2 className="w-4 h-4 text-ok" />
        : optional
          ? <AlertTriangle className="w-4 h-4 text-muted" />
          : <AlertTriangle className="w-4 h-4 text-warn" />
      }
      <span className="font-medium">{label}</span>
      <span className="text-muted text-xs ml-auto">{sub}</span>
    </div>
  );
}

/** Returns true if onboarding should auto-show (no keys + not previously skipped). */
export function useShouldShowOnboarding(): boolean {
  const settings = useQuery({ queryKey: ["settings"], queryFn: SettingsApi.get });
  if (!settings.data) return false;
  if (settings.data.anthropic_key_set) return false;          // assume returning user
  if (localStorage.getItem(SKIP_FLAG) === "1") return false;  // user dismissed
  return true;
}
