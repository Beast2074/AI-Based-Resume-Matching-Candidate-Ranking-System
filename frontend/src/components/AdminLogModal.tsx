import React, { useState, useEffect, useRef } from "react";
import {
  ShieldAlert,
  Terminal,
  RefreshCw,
  Trash2,
  Lock,
  Unlock,
  X,
  Search,
  CheckCircle2,
  XCircle,
  Copy,
  Cpu,
  Database,
  Activity,
} from "lucide-react";
import {
  fetchSystemLogs,
  verifyAdminPassword,
  clearSystemLogs,
  DiagnosticLog,
  TelemetryStatus,
} from "../lib/api";

interface AdminLogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SUBSYSTEMS = [
  "ALL",
  "PARSER",
  "JD_EXTRACTOR",
  "SKILLS",
  "EMBEDDER",
  "SCORING",
  "API",
  "SECURITY",
  "SYSTEM",
];

const LEVELS = ["ALL", "INFO", "WARNING", "ERROR"];

export default function AdminLogModal({ isOpen, onClose }: AdminLogModalProps) {
  const [password, setPassword] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return sessionStorage.getItem("system_admin_auth") === "12345";
  });
  const [authError, setAuthError] = useState("");
  const [isVerifying, setIsVerifying] = useState(false);

  const [logs, setLogs] = useState<DiagnosticLog[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryStatus | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const [selectedSubsystem, setSelectedSubsystem] = useState("ALL");
  const [selectedLevel, setSelectedLevel] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);

  const logContainerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // Synchronize authentication from sessionStorage
  useEffect(() => {
    const saved = sessionStorage.getItem("system_admin_auth");
    if (saved) {
      setPassword(saved);
      setIsAuthenticated(true);
    }
  }, []);

  // Poll logs when authenticated and open
  useEffect(() => {
    if (!isOpen || !isAuthenticated) return;

    let intervalId: any = null;

    const loadLogs = async () => {
      try {
        const activePass = password || sessionStorage.getItem("system_admin_auth") || "12345";
        const data = await fetchSystemLogs(
          activePass,
          0,
          selectedLevel,
          selectedSubsystem
        );
        setLogs(data.logs);
        setTelemetry(data.telemetry);
      } catch (err: any) {
        if (err.message === "UNAUTHORIZED") {
          setIsAuthenticated(false);
          sessionStorage.removeItem("system_admin_auth");
          setAuthError("Session expired or unauthorized. Please re-enter password.");
        }
      }
    };

    loadLogs();

    if (autoRefresh) {
      intervalId = setInterval(loadLogs, 2500);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isOpen, isAuthenticated, autoRefresh, selectedLevel, selectedSubsystem, password]);

  // Auto scroll terminal to bottom
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    setIsVerifying(true);

    try {
      const ok = await verifyAdminPassword(password);
      if (ok) {
        setIsAuthenticated(true);
        sessionStorage.setItem("system_admin_auth", password);
        // Load initial logs
        const data = await fetchSystemLogs(password);
        setLogs(data.logs);
        setTelemetry(data.telemetry);
      } else {
        setAuthError("Incorrect admin password. Access denied.");
      }
    } catch {
      setAuthError("Unable to verify credentials. Ensure backend is running.");
    } finally {
      setIsVerifying(false);
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setPassword("");
    sessionStorage.removeItem("system_admin_auth");
    setLogs([]);
  };

  const handleClear = async () => {
    if (!window.confirm("Are you sure you want to clear the diagnostic log buffer?")) return;
    try {
      const activePass = password || sessionStorage.getItem("system_admin_auth") || "12345";
      await clearSystemLogs(activePass);
      const data = await fetchSystemLogs(activePass);
      setLogs(data.logs);
      setTelemetry(data.telemetry);
    } catch (err) {
      alert("Failed to clear logs: " + String(err));
    }
  };

  const handleCopyLogs = () => {
    const text = logs
      .map(
        (l) =>
          `[${l.timestamp}] [${l.level}] [${l.subsystem}] ${l.message} ${
            Object.keys(l.details || {}).length ? JSON.stringify(l.details) : ""
          }`
      )
      .join("\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filteredLogs = logs.filter((l) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      l.message.toLowerCase().includes(q) ||
      l.subsystem.toLowerCase().includes(q) ||
      l.level.toLowerCase().includes(q)
    );
  });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-5xl bg-[#0B0F19] border border-white/10 rounded-2xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Top Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-accentIndigo/20 border border-accentIndigo/30 flex items-center justify-center text-accentCyan">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-textPrimary tracking-tight">
                  Live System Diagnostic Console
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accentCyan/10 text-accentCyan border border-accentCyan/20">
                  Telemetry Engine
                </span>
              </div>
              <p className="text-xs text-textMuted">
                Real-time sub-system observability, PII-sanitized logs & failure diagnosis
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isAuthenticated && (
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-textMuted hover:text-textPrimary bg-white/5 hover:bg-white/10 border border-white/10 flex items-center gap-1.5 transition"
                title="Lock Console"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Lock</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-textMuted hover:text-textPrimary hover:bg-white/5 transition"
              title="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        {!isAuthenticated ? (
          /* Password Authentication Gate */
          <div className="p-8 sm:p-12 flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-4 shadow-lg shadow-amber-500/10">
              <ShieldAlert className="w-8 h-8" />
            </div>

            <h4 className="text-xl font-heading font-bold text-textPrimary mb-2">
              Administrator Verification Required
            </h4>
            <p className="text-sm text-textMuted max-w-md mb-6">
              System logs and internal diagnostics are protected to prevent unauthorized log and data leaks. Enter the administrator password to unlock the console.
            </p>

            <form onSubmit={handleLogin} className="w-full max-w-sm space-y-4">
              <div className="relative">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password (12345)"
                  autoFocus
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-textPrimary placeholder:text-textMuted/50 focus:outline-none focus:border-accentCyan focus:ring-1 focus:ring-accentCyan text-sm font-mono tracking-wider transition"
                />
              </div>

              {authError && (
                <div className="px-3.5 py-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 text-left flex items-center gap-2">
                  <XCircle className="w-4 h-4 shrink-0" />
                  <span>{authError}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={isVerifying || !password}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-accentIndigo to-accentCyan text-white font-medium text-sm shadow-lg shadow-accentIndigo/20 hover:opacity-95 disabled:opacity-50 transition flex items-center justify-center gap-2"
              >
                {isVerifying ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Unlock className="w-4 h-4" />
                )}
                <span>Unlock System Telemetry</span>
              </button>

              <p className="text-[11px] text-textMuted/60 font-mono">
                Default demonstration key: <span className="text-accentCyan font-bold">12345</span>
              </p>
            </form>
          </div>
        ) : (
          /* Live Telemetry & Console View */
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* System Health Telemetry Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-black/40 border-b border-white/5 text-xs font-mono">
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                <Activity className="w-4 h-4 text-emerald-400" />
                <div>
                  <div className="text-[10px] text-textMuted uppercase tracking-wider">Health Status</div>
                  <div className="text-emerald-400 font-semibold uppercase">
                    {telemetry?.status || "HEALTHY"}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                <Cpu className="w-4 h-4 text-accentCyan" />
                <div>
                  <div className="text-[10px] text-textMuted uppercase tracking-wider">ONNX Engine</div>
                  <div className="text-textPrimary truncate" title={telemetry?.model_name}>
                    {telemetry?.model_loaded ? "bge-small-en (384d)" : "Offline"}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                <Database className="w-4 h-4 text-indigo-400" />
                <div>
                  <div className="text-[10px] text-textMuted uppercase tracking-wider">Indexed Data</div>
                  <div className="text-textPrimary">
                    {telemetry?.total_jobs || 0} Jobs / {telemetry?.total_candidates || 0} Cand
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                <Terminal className="w-4 h-4 text-amber-400" />
                <div>
                  <div className="text-[10px] text-textMuted uppercase tracking-wider">Errors / Logs</div>
                  <div className="text-textPrimary">
                    <span className={telemetry && telemetry.error_count > 0 ? "text-rose-400 font-bold" : "text-emerald-400"}>
                      {telemetry?.error_count || 0} Err
                    </span>{" "}
                    / {logs.length} Buffered
                  </div>
                </div>
              </div>
            </div>

            {/* Filter Controls Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-4 border-b border-white/5 bg-white/[0.01]">
              <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto">
                <span className="text-[11px] font-mono text-textMuted uppercase tracking-wider mr-1">
                  Subsystem:
                </span>
                {SUBSYSTEMS.map((sub) => (
                  <button
                    key={sub}
                    onClick={() => setSelectedSubsystem(sub)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-mono transition ${
                      selectedSubsystem === sub
                        ? "bg-accentIndigo text-white font-semibold shadow-sm shadow-accentIndigo/30"
                        : "bg-white/5 text-textMuted hover:text-textPrimary hover:bg-white/10"
                    }`}
                  >
                    {sub}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {/* Level selector */}
                <select
                  value={selectedLevel}
                  onChange={(e) => setSelectedLevel(e.target.value)}
                  className="px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-mono text-textPrimary focus:outline-none focus:border-accentCyan"
                >
                  {LEVELS.map((lvl) => (
                    <option key={lvl} value={lvl} className="bg-slate-900 text-white">
                      {lvl === "ALL" ? "All Levels" : lvl}
                    </option>
                  ))}
                </select>

                {/* Search Input */}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-textMuted absolute left-2.5 top-2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search logs..."
                    className="pl-8 pr-3 py-1 bg-white/5 border border-white/10 rounded-md text-xs text-textPrimary placeholder:text-textMuted/40 focus:outline-none focus:border-accentCyan w-36 sm:w-44 font-mono"
                  />
                </div>

                {/* Auto-refresh switch */}
                <button
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 transition ${
                    autoRefresh
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      : "bg-white/5 border-white/10 text-textMuted"
                  }`}
                  title="Toggle 2.5s live polling"
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${autoRefresh ? "bg-emerald-400 animate-ping" : "bg-textMuted"}`} />
                  <span>{autoRefresh ? "Live (2.5s)" : "Paused"}</span>
                </button>

                {/* Copy logs */}
                <button
                  onClick={handleCopyLogs}
                  className="p-1.5 rounded-md bg-white/5 border border-white/10 text-textMuted hover:text-textPrimary transition"
                  title="Copy logs to clipboard"
                >
                  {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                </button>

                {/* Clear buffer */}
                <button
                  onClick={handleClear}
                  className="p-1.5 rounded-md bg-white/5 border border-white/10 text-textMuted hover:text-rose-400 hover:border-rose-500/30 transition"
                  title="Clear log buffer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Terminal Log Console */}
            <div
              ref={logContainerRef}
              className="flex-1 overflow-y-auto p-4 bg-[#070A12] font-mono text-xs space-y-1.5 select-text min-h-[300px]"
            >
              {filteredLogs.length === 0 ? (
                <div className="py-16 text-center text-textMuted/60 flex flex-col items-center justify-center">
                  <Terminal className="w-8 h-8 mb-2 opacity-40" />
                  <p>No log records match current filters.</p>
                </div>
              ) : (
                filteredLogs.map((log) => {
                  const isErr = log.level === "ERROR" || log.level === "CRITICAL";
                  const isWarn = log.level === "WARNING";
                  const levelColor = isErr
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                    : isWarn
                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";

                  return (
                    <div
                      key={log.id}
                      className={`py-1 px-2.5 rounded hover:bg-white/[0.03] transition flex items-start gap-2.5 leading-relaxed ${
                        isErr ? "bg-rose-500/[0.04]" : isWarn ? "bg-amber-500/[0.02]" : ""
                      }`}
                    >
                      <span className="text-textMuted/50 shrink-0 text-[10px] pt-0.5 select-none">
                        {log.timestamp.split(" ")[1]}
                      </span>

                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold shrink-0 ${levelColor}`}>
                        {log.level}
                      </span>

                      <span className="px-1.5 py-0.2 rounded text-[10px] bg-accentIndigo/10 text-accentIndigo border border-accentIndigo/20 shrink-0">
                        {log.subsystem}
                      </span>

                      <span className="text-textPrimary/90 break-words flex-1">
                        {log.message}
                      </span>

                      {log.details && Object.keys(log.details).length > 0 && (
                        <span className="text-[10px] text-textMuted/60 max-w-xs truncate hidden sm:inline" title={JSON.stringify(log.details)}>
                          {JSON.stringify(log.details)}
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Terminal Footer */}
            <div className="px-4 py-2 bg-black/60 border-t border-white/5 flex items-center justify-between text-[11px] font-mono text-textMuted">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Zero Data Leaks Active: PII & internal paths automatically redacted.</span>
              </div>
              <label className="flex items-center gap-1.5 cursor-pointer hover:text-textPrimary transition">
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                  className="rounded bg-white/5 border-white/10 text-accentCyan focus:ring-0"
                />
                <span>Auto-scroll to bottom</span>
              </label>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
