import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getRanking, getExportCsvUrl, RankingResponse } from "../lib/api";
import { getScoreColor } from "../components/ScoreGauge";
import {
  Download,
  Eye,
  EyeOff,
  Sliders,
  ShieldAlert,
  Award,
  BarChart2,
  Users,
  Search,
  ArrowRight,
  RefreshCw,
} from "lucide-react";

export default function Ranking() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const [ranking, setRanking] = useState<RankingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [minScore, setMinScore] = useState(0);
  const [anonymize, setAnonymize] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "matrix">("table");

  const loadRanking = async () => {
    if (!jobId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getRanking(jobId, 0, anonymize);
      setRanking(data);
      try {
        sessionStorage.setItem(`ranking_${jobId}`, JSON.stringify(data));
      } catch {}
    } catch (err: any) {
      // Try restoring from session storage if server instance cycled
      const cached = sessionStorage.getItem(`ranking_${jobId}`);
      if (cached) {
        try {
          setRanking(JSON.parse(cached));
          setError(null);
          return;
        } catch {}
      }
      setError(err?.message || "Failed to load rankings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRanking();
  }, [jobId, anonymize]);

  // Client-side filtering ensures instant, 60fps response without triggering network errors
  const filteredCandidates = (ranking?.candidates || []).filter((c) => {
    if (c.total < minScore) return false;
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      c.name.toLowerCase().includes(term) ||
      c.filename.toLowerCase().includes(term) ||
      c.matched_skills.some((s) => s.toLowerCase().includes(term))
    );
  });

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:py-12 space-y-8">
      {/* Page Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div>
          <h1 className="text-3xl font-bold font-heading text-textPrimary">Candidate Ranking Dashboard</h1>
          <p className="text-sm text-textMuted mt-1">
            Comparative evaluation and matching scores generated across all candidate resumes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {jobId && (
            <a
              href={getExportCsvUrl(jobId)}
              download
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-textPrimary flex items-center gap-2 transition"
            >
              <Download className="w-4 h-4 text-accentCyan" />
              <span>Export CSV</span>
            </a>
          )}
        </div>
      </div>

      {/* Summary KPI Cards */}
      {ranking && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-card p-5 space-y-1">
            <div className="flex items-center justify-between text-textMuted">
              <span className="text-xs uppercase font-mono tracking-wider">Candidates Scored</span>
              <Users className="w-4 h-4 text-accentIndigo" />
            </div>
            <p className="text-3xl font-mono font-bold text-textPrimary">
              {ranking.summary.scored_candidates}
            </p>
          </div>

          <div className="glass-card p-5 space-y-1">
            <div className="flex items-center justify-between text-textMuted">
              <span className="text-xs uppercase font-mono tracking-wider">Top Match Score</span>
              <Award className="w-4 h-4 text-scoreGreen" />
            </div>
            <p className="text-3xl font-mono font-bold text-scoreGreen">
              {ranking.summary.top_score}%
            </p>
          </div>

          <div className="glass-card p-5 space-y-1">
            <div className="flex items-center justify-between text-textMuted">
              <span className="text-xs uppercase font-mono tracking-wider">Median Score</span>
              <BarChart2 className="w-4 h-4 text-accentCyan" />
            </div>
            <p className="text-3xl font-mono font-bold text-accentCyan">
              {ranking.summary.median_score.toFixed(0)}%
            </p>
          </div>

          <div className="glass-card p-5 space-y-1">
            <div className="flex items-center justify-between text-textMuted">
              <span className="text-xs uppercase font-mono tracking-wider">Core Skills Capped</span>
              <ShieldAlert className="w-4 h-4 text-scoreAmber" />
            </div>
            <p className="text-3xl font-mono font-bold text-scoreAmber">
              {ranking.summary.capped_count}
            </p>
          </div>
        </div>
      )}

      {/* Controls Bar: Min score slider, Anonymize toggle, Search input */}
      <div className="glass-card p-4 sm:p-5 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-textMuted" />
          <input
            type="text"
            placeholder="Filter by name, skill..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-background border border-white/10 text-xs font-mono text-textPrimary placeholder:text-textMuted focus:outline-none focus:border-accentCyan"
          />
        </div>

        {/* Min Score Slider & Anonymize */}
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-3">
            <Sliders className="w-4 h-4 text-textMuted" />
            <span className="text-xs font-mono text-textMuted">Min Score:</span>
            <input
              type="range"
              min="0"
              max="90"
              step="5"
              value={minScore}
              onChange={(e) => setMinScore(parseInt(e.target.value, 10))}
              className="w-28 sm:w-36 accent-accentCyan cursor-pointer"
            />
            <span className="text-xs font-mono font-bold text-accentCyan min-w-[32px]">
              {minScore}%
            </span>
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center rounded-xl bg-white/[0.03] border border-white/10 p-1">
            <button
              onClick={() => setViewMode("table")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                viewMode === "table"
                  ? "bg-accentCyan text-black font-semibold shadow-sm"
                  : "text-textMuted hover:text-textPrimary"
              }`}
            >
              Table View
            </button>
            <button
              onClick={() => setViewMode("matrix")}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                viewMode === "matrix"
                  ? "bg-accentCyan text-black font-semibold shadow-sm"
                  : "text-textMuted hover:text-textPrimary"
              }`}
            >
              Comparison Matrix
            </button>
          </div>

          <button
            onClick={() => setAnonymize(!anonymize)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-2 transition ${
              anonymize
                ? "bg-accentIndigo/10 border-accentIndigo/40 text-accentIndigo"
                : "bg-white/[0.03] border-white/10 text-textMuted hover:text-textPrimary"
            }`}
          >
            {anonymize ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            <span>Anonymize Mode ({anonymize ? "ON" : "OFF"})</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="glass-card p-12 text-center space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-accentCyan" />
          <p className="text-sm text-textMuted">Loading candidate rankings...</p>
        </div>
      ) : error ? (
        <div className="glass-card p-8 text-center space-y-4">
          <p className="text-sm font-semibold text-scoreRed">{error}</p>
          {error.toLowerCase().includes("job not found") ? (
            <div className="space-y-3">
              <p className="text-xs text-textMuted max-w-md mx-auto">
                This job was analyzed in an earlier server session that has expired. Create a new job or re-upload resumes to start a fresh evaluation.
              </p>
              <button
                onClick={() => navigate("/")}
                className="px-5 py-2.5 rounded-xl bg-accentCyan text-black font-semibold text-xs hover:opacity-90 transition shadow-lg shadow-accentCyan/10"
              >
                Create New Analysis
              </button>
            </div>
          ) : (
            <button
              onClick={loadRanking}
              className="px-4 py-2 rounded-lg bg-white/5 border border-white/10 text-xs text-textPrimary hover:bg-white/10 transition"
            >
              Retry
            </button>
          )}
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="glass-card p-12 text-center space-y-2">
          <p className="text-base font-medium text-textPrimary">No candidates match criteria</p>
          <p className="text-xs text-textMuted">Try lowering the minimum score slider.</p>
        </div>
      ) : viewMode === "matrix" ? (
        /* Multi-Candidate Side-by-Side Comparison Matrix */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fadeIn">
          {filteredCandidates.map((c) => {
            const color = getScoreColor(c.total);
            return (
              <div
                key={c.id}
                onClick={() => navigate(`/candidates/${c.id}?anonymize=${anonymize}`)}
                className="glass-card p-6 space-y-5 hover:border-accentCyan/30 transition cursor-pointer group"
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-xl bg-accentIndigo/20 text-accentCyan flex items-center justify-center font-bold text-xs font-mono">
                      #{c.rank}
                    </span>
                    <div>
                      <h3 className="font-bold text-textPrimary text-base group-hover:text-accentCyan transition">
                        {c.name}
                      </h3>
                      <p className="text-xs font-mono text-textMuted truncate max-w-xs">
                        {c.email || c.filename}
                      </p>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-2xl font-bold font-mono" style={{ color: color.hex }}>
                      {c.total}%
                    </span>
                    <div className="text-[10px] uppercase font-mono tracking-wider text-textMuted">
                      Match Score
                    </div>
                  </div>
                </div>

                {/* Comparative Component Breakdown */}
                <div className="space-y-3 p-4 rounded-xl bg-white/[0.02] border border-white/5 text-xs font-mono">
                  {/* Skills */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-textMuted text-[11px]">
                      <span>Skills Match (40% weight)</span>
                      <span className="text-accentCyan">{(c.skills_score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-accentCyan h-full rounded-full"
                        style={{ width: `${Math.min(100, c.skills_score * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* Semantic */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-textMuted text-[11px]">
                      <span>Semantic Alignment (25% weight)</span>
                      <span className="text-accentIndigo">{(c.semantic_score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-accentIndigo h-full rounded-full"
                        style={{ width: `${Math.min(100, c.semantic_score * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* Experience */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-textMuted text-[11px]">
                      <span>Experience ({c.relevant_years.toFixed(1)} / {c.total_years.toFixed(1)} yrs)</span>
                      <span className="text-scoreGreen">{(c.experience_score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-scoreGreen h-full rounded-full"
                        style={{ width: `${Math.min(100, c.experience_score * 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* Education */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-textMuted text-[11px]">
                      <span>Education Level</span>
                      <span className="text-scoreAmber">{(c.education_score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-scoreAmber h-full rounded-full"
                        style={{ width: `${Math.min(100, c.education_score * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Matched Skills & Badges */}
                <div className="space-y-2">
                  <div className="text-[11px] text-textMuted flex items-center justify-between">
                    <span>Matched Skills ({c.matched_skills.length})</span>
                    {c.capped && (
                      <span className="text-[10px] text-scoreAmber bg-scoreAmber/10 border border-scoreAmber/20 px-2 py-0.5 rounded">
                        Core Skills Capped at 65
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {c.matched_skills.slice(0, 6).map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded text-[10px] bg-accentCyan/10 text-accentCyan border border-accentCyan/20"
                      >
                        {s}
                      </span>
                    ))}
                    {c.matched_skills.length > 6 && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono text-textMuted">
                        +{c.matched_skills.length - 6} more
                      </span>
                    )}
                  </div>
                </div>

                {/* Footer action */}
                <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs text-accentCyan">
                  <span>Inspect Candidate Deep Dive</span>
                  <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <>
          {/* Desktop Table View (>= 768px) */}
          <div className="hidden md:block glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-xs font-mono text-textMuted uppercase tracking-wider bg-white/[0.02]">
                    <th className="py-3 px-4 w-16 text-center">Rank</th>
                    <th className="py-3 px-4">Candidate</th>
                    <th className="py-3 px-4 w-32">Experience</th>
                    <th className="py-3 px-4 w-48">Match Score</th>
                    <th className="py-3 px-4">Matched Skills</th>
                    <th className="py-3 px-4 w-20 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-sm">
                  {filteredCandidates.map((c) => {
                    const color = getScoreColor(c.total);
                    return (
                      <tr
                        key={c.id}
                        onClick={() => navigate(`/candidates/${c.id}?anonymize=${anonymize}`)}
                        className="glass-card-hover cursor-pointer group"
                      >
                        {/* Rank */}
                        <td className="py-4 px-4 text-center font-mono font-bold">
                          <span
                            className={`inline-block w-7 h-7 rounded-full leading-7 text-xs ${
                              c.rank === 1
                                ? "bg-scoreGreen/20 text-scoreGreen border border-scoreGreen/30"
                                : c.rank === 2
                                ? "bg-accentCyan/20 text-accentCyan border border-accentCyan/30"
                                : c.rank === 3
                                ? "bg-accentIndigo/20 text-accentIndigo border border-accentIndigo/30"
                                : "text-textMuted"
                            }`}
                          >
                            {c.rank}
                          </span>
                        </td>

                        {/* Candidate Name & Info */}
                        <td className="py-4 px-4">
                          <div className="font-semibold text-textPrimary group-hover:text-accentCyan transition">
                            {c.name}
                          </div>
                          <div className="text-xs font-mono text-textMuted truncate max-w-xs">
                            {c.email || c.filename}
                          </div>
                        </td>

                        {/* Experience */}
                        <td className="py-4 px-4 font-mono text-xs">
                          <span className="font-medium text-textPrimary">
                            {c.relevant_years.toFixed(1)} yrs
                          </span>
                          <span className="text-[11px] text-textMuted block">
                            of {c.total_years.toFixed(1)} total
                          </span>
                        </td>

                        {/* Match Score & Progress Bar */}
                        <td className="py-4 px-4">
                          <div className="flex items-center justify-between text-xs font-mono font-bold mb-1">
                            <span className={color.text}>{c.total}%</span>
                            {c.capped && (
                              <span className="text-[10px] text-scoreAmber bg-scoreAmber/10 px-1.5 py-0.2 rounded font-normal">
                                Capped
                              </span>
                            )}
                          </div>
                          <div className="w-full bg-white/[0.04] rounded-full h-2 overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-500 ease-out"
                              style={{
                                width: `${c.total}%`,
                                backgroundColor: color.hex,
                              }}
                            />
                          </div>
                        </td>

                        {/* Matched Skills Chips */}
                        <td className="py-4 px-4">
                          <div className="flex flex-wrap gap-1.5">
                            {c.matched_skills.slice(0, 4).map((s) => (
                              <span
                                key={s}
                                className="px-2 py-0.5 rounded text-[11px] bg-white/[0.03] border border-white/5 text-textPrimary"
                              >
                                {s}
                              </span>
                            ))}
                            {c.matched_skills.length > 4 && (
                              <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-accentCyan/10 text-accentCyan">
                                +{c.matched_skills.length - 4}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Arrow */}
                        <td className="py-4 px-4 text-right">
                          <ArrowRight className="w-4 h-4 text-textMuted group-hover:text-accentCyan group-hover:translate-x-1 transition ml-auto" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Card View (< 768px) */}
          <div className="md:hidden space-y-4">
            {filteredCandidates.map((c) => {
              const color = getScoreColor(c.total);
              return (
                <div
                  key={c.id}
                  onClick={() => navigate(`/candidates/${c.id}?anonymize=${anonymize}`)}
                  className="glass-card p-5 space-y-4 cursor-pointer hover:border-accentIndigo/40 transition"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span className="w-6 h-6 rounded-full bg-white/5 text-center leading-6 text-xs font-mono font-bold text-accentCyan">
                        #{c.rank}
                      </span>
                      <div>
                        <h4 className="font-semibold text-textPrimary">{c.name}</h4>
                        <span className="text-xs font-mono text-textMuted">{c.filename}</span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className={`font-mono text-2xl font-bold ${color.text}`}>
                        {c.total}%
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-white/[0.04] rounded-full h-2 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${c.total}%`, backgroundColor: color.hex }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-xs font-mono text-textMuted border-t border-white/5 pt-3">
                    <span>
                      Exp: <strong className="text-textPrimary">{c.relevant_years.toFixed(1)} yrs</strong> rel.
                    </span>
                    {c.capped && (
                      <span className="text-[10px] text-scoreAmber bg-scoreAmber/10 px-2 py-0.5 rounded">
                        Capped at 65
                      </span>
                    )}
                  </div>

                  {/* Skills chips */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {c.matched_skills.slice(0, 4).map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded text-[10px] bg-white/[0.03] border border-white/5 text-textPrimary"
                      >
                        {s}
                      </span>
                    ))}
                    {c.matched_skills.length > 4 && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono text-accentCyan">
                        +{c.matched_skills.length - 4}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
