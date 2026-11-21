import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { getCandidate, CandidateDetail } from "../lib/api";
import ScoreGauge from "../components/ScoreGauge";
import WaterfallChart from "../components/WaterfallChart";
import {
  ArrowLeft,
  Mail,
  Phone,
  FileText,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
} from "lucide-react";

export default function CandidateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const anonymize = searchParams.get("anonymize") === "true";

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    getCandidate(id, anonymize)
      .then(setCandidate)
      .catch((err) => setError(err.message || "Failed to load candidate details"))
      .finally(() => setLoading(false));
  }, [id, anonymize]);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center space-y-3">
        <div className="w-8 h-8 rounded-full border-2 border-accentCyan border-t-transparent animate-spin mx-auto" />
        <p className="text-sm font-mono text-textMuted">Loading candidate explanation...</p>
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-4">
        <div className="glass-card p-8 border-scoreRed/30 space-y-3">
          <p className="text-base text-scoreRed font-semibold">{error || "Candidate not found"}</p>
          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-textPrimary hover:bg-white/10 transition"
          >
            ← Go Back
          </button>
        </div>
      </div>
    );
  }

  const exp = candidate.explanation || {};
  const score = candidate.score || {};
  const totalScore = score.total ?? 0;
  const isCapped = score.capped ?? false;
  const components = exp.components || [];
  const matchedSkills = exp.matched_skills || [];
  const partialSkills = exp.partial_skills || [];
  const missingSkills = exp.missing_skills || [];
  const reasons = exp.reasons || [];
  const expData = exp.experience || {};
  const reqYears = expData.required_years || 0;
  const relYears = expData.relevant_years || candidate.total_years;
  const totYears = expData.total_years || candidate.total_years;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12 space-y-8 animate-fadeIn">
      {/* Back button */}
      <div>
        <button
          onClick={() => navigate(-1)}
          className="text-xs font-mono text-textMuted hover:text-textPrimary flex items-center gap-1.5 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Rankings Table</span>
        </button>
      </div>

      {/* Header Profile Glass Card */}
      <div className="glass-card p-6 sm:p-8 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold font-heading text-textPrimary">{candidate.name}</h1>
              {isCapped && (
                <span className="px-2.5 py-0.5 rounded-full bg-scoreAmber/10 border border-scoreAmber/30 text-scoreAmber text-xs font-mono flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Capped at 65</span>
                </span>
              )}
            </div>
            <p className="text-xs font-mono text-textMuted mt-1">
              Source file: <span className="text-textPrimary">{candidate.filename}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-textMuted">
            {candidate.email && (
              <span className="flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-accentCyan" />
                <span>{candidate.email}</span>
              </span>
            )}
            {candidate.phone && (
              <span className="flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-accentIndigo" />
                <span>{candidate.phone}</span>
              </span>
            )}
          </div>
        </div>

        {/* Warnings alert if any */}
        {candidate.parse_warnings.length > 0 && (
          <div className="p-3.5 rounded-xl bg-scoreAmber/10 border border-scoreAmber/30 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-scoreAmber shrink-0 mt-0.5" />
            <div className="space-y-0.5 text-xs text-scoreAmber font-mono">
              {candidate.parse_warnings.map((w, idx) => (
                <p key={idx}>{w}</p>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Primary Metrics Grid: Gauge + Waterfall Chart */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Animated Score Gauge */}
        <div className="glass-card p-6 flex flex-col items-center justify-center space-y-4 md:col-span-1">
          <ScoreGauge score={totalScore} size={190} strokeWidth={15} />
          <div className="text-center space-y-1">
            <span className="text-xs font-mono text-textMuted">
              Must-Have Coverage:{" "}
              <strong className="text-textPrimary">
                {((score.must_have_coverage ?? 1.0) * 100).toFixed(0)}%
              </strong>
            </span>
          </div>
        </div>

        {/* Additive Points Waterfall Chart */}
        <div className="md:col-span-2">
          <WaterfallChart
            components={components}
            totalScore={totalScore}
            capped={isCapped}
          />
        </div>
      </div>

      {/* Experience Comparison Bars */}
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-white/5 pb-3">
          <h3 className="font-heading font-semibold text-base text-textPrimary flex items-center gap-2">
            <Clock className="w-4 h-4 text-accentCyan" />
            Experience Duration Comparison
          </h3>
          <span className="text-xs font-mono text-textMuted">
            Relevant / Required Ratio:{" "}
            <strong className="text-accentCyan">{expData.ratio ?? 1.0}x</strong>
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-1">
            <span className="text-xs text-textMuted block font-mono">Job Requirement</span>
            <span className="font-mono text-2xl font-bold text-textPrimary">
              {reqYears > 0 ? `${reqYears.toFixed(1)} yrs` : "No strict minimum"}
            </span>
          </div>

          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-1">
            <span className="text-xs text-textMuted block font-mono">Total Career Duration</span>
            <span className="font-mono text-2xl font-bold text-textPrimary">
              {totYears.toFixed(1)} yrs
            </span>
          </div>

          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-1">
            <span className="text-xs text-textMuted block font-mono">Cosine-Filtered Relevant</span>
            <span className="font-mono text-2xl font-bold text-scoreGreen">
              {relYears.toFixed(1)} yrs
            </span>
          </div>
        </div>
      </div>

      {/* 3 Skill Breakdown Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Panel 1: Matched Skills */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-2.5">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-scoreGreen flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" /> Matched Skills ({matchedSkills.length})
            </span>
          </div>

          <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
            {matchedSkills.length === 0 ? (
              <p className="text-xs text-textMuted italic">No direct skills matched.</p>
            ) : (
              matchedSkills.map((m: any, idx: number) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-white/[0.02] border border-white/5 space-y-1 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-textPrimary">{m.skill}</span>
                      {m.matched_as && m.matched_as !== m.skill && (
                        <span className="text-[10px] font-mono text-accentCyan ml-2">
                          (via {m.matched_as})
                        </span>
                      )}
                    </div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        m.evidence === "experience"
                          ? "bg-scoreGreen/10 text-scoreGreen"
                          : "bg-scoreAmber/10 text-scoreAmber"
                      }`}
                    >
                      {m.evidence === "experience" ? "In Experience (1.0)" : "Skills List Only (0.6)"}
                    </span>
                  </div>
                  {m.snippet && (
                    <p className="text-[11px] font-mono text-textMuted line-clamp-2 italic">
                      "{m.snippet}"
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Panel 2: Partial Semantic Matches */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-2.5">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-accentCyan flex items-center gap-1.5">
              <HelpCircle className="w-4 h-4" /> Partial Skills ({partialSkills.length})
            </span>
          </div>

          <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
            {partialSkills.length === 0 ? (
              <p className="text-xs text-textMuted italic">No partial semantic skills found.</p>
            ) : (
              partialSkills.map((p: any, idx: number) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-white/[0.02] border border-white/5 space-y-1 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-textPrimary">{p.required}</span>
                    <span className="text-[10px] font-mono text-accentCyan">
                      +{p.credit.toFixed(2)} credit
                    </span>
                  </div>
                  <p className="text-[11px] text-textMuted">
                    Closest: <strong className="text-textPrimary">{p.closest}</strong> (sim:{" "}
                    {(p.similarity * 100).toFixed(0)}%)
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Panel 3: Missing Skills */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-2.5">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-scoreRed flex items-center gap-1.5">
              <XCircle className="w-4 h-4" /> Missing Skills ({missingSkills.length})
            </span>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {missingSkills.length === 0 ? (
              <p className="text-xs text-scoreGreen italic">All required skills covered!</p>
            ) : (
              missingSkills.map((m: any, idx: number) => (
                <div
                  key={idx}
                  className={`p-2 rounded-lg border text-xs flex items-center justify-between ${
                    m.importance === "must_have"
                      ? "bg-scoreRed/5 border-scoreRed/20 text-scoreRed"
                      : "bg-white/[0.02] border-white/5 text-textMuted"
                  }`}
                >
                  <span className="font-medium">{m.skill}</span>
                  <span className="text-[10px] font-mono uppercase">
                    {m.importance === "must_have" ? "Must-Have" : "Nice-to-Have"}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Plain-English Transparent Reasons */}
      <div className="glass-card p-6 space-y-4">
        <h3 className="font-heading font-semibold text-base text-textPrimary flex items-center gap-2 border-b border-white/5 pb-3">
          <FileText className="w-4 h-4 text-accentIndigo" />
          Deterministic Plain-English Reasons
        </h3>

        <div className="space-y-2.5">
          {reasons.map((reason: string, idx: number) => (
            <div
              key={idx}
              className="p-3 rounded-xl bg-white/[0.02] border border-white/5 flex items-start gap-3 text-xs text-textPrimary"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-accentCyan mt-1.5 shrink-0" />
              <span>{reason}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Collapsible Extracted Text Viewer */}
      <div className="glass-card p-6 space-y-4">
        <button
          onClick={() => setShowRawText(!showRawText)}
          className="w-full flex items-center justify-between text-left font-heading font-semibold text-sm text-textPrimary"
        >
          <span className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-textMuted" />
            <span>Extracted Document Text ({candidate.raw_text.length} chars)</span>
          </span>
          {showRawText ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showRawText && (
          <pre className="p-4 rounded-xl bg-background border border-white/10 text-xs font-mono text-textMuted whitespace-pre-wrap max-h-96 overflow-y-auto">
            {candidate.raw_text}
          </pre>
        )}
      </div>
    </div>
  );
}
