import { useEffect, useState } from "react";
import { fetchScoringConfig, ScoringConfig } from "../lib/api";
import {
  Cpu,
  Layers,
  Calculator,
  GitBranch,
  ShieldCheck,
  Award,
} from "lucide-react";

export default function HowItWorks() {
  const [config, setConfig] = useState<ScoringConfig | null>(null);

  useEffect(() => {
    fetchScoringConfig()
      .then(setConfig)
      .catch((err) => console.error("Could not fetch scoring config:", err));
  }, []);

  const weights = config?.weights || {
    skills: 0.40,
    semantic: 0.25,
    experience: 0.25,
    education: 0.10,
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12 space-y-10 animate-fadeIn">
      {/* Title */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accentCyan/10 border border-accentCyan/30 text-accentCyan text-xs font-mono">
          <Calculator className="w-3.5 h-3.5" />
          <span>Evaluation Framework</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold font-heading text-textPrimary">
          Candidate Ranking Methodology
        </h1>
        <p className="text-sm text-textMuted max-w-2xl mx-auto">
          An objective, multi-pillar evaluation engine designed to evaluate candidates against job requirements.
        </p>
      </div>

      {/* Formula & Weights */}
      <div className="glass-card p-6 sm:p-8 space-y-6">
        <div className="border-b border-white/10 pb-4">
          <h2 className="text-xl font-bold font-heading text-textPrimary flex items-center gap-2">
            <Cpu className="w-5 h-5 text-accentCyan" />
            Weighted Scoring Formula
          </h2>
          <p className="text-xs text-textMuted mt-1">
            Scores are normalized to a standard 0–100 scale across four evaluation dimensions.
          </p>
        </div>

        <div className="p-4 rounded-xl bg-background border border-white/10 font-mono text-xs sm:text-sm text-accentCyan text-center overflow-x-auto shadow-inner">
          Overall Score = round(100 × ({(weights.skills * 100).toFixed(0)}% × Skills + {(weights.semantic * 100).toFixed(0)}% × Semantic + {(weights.experience * 100).toFixed(0)}% × Experience + {(weights.education * 100).toFixed(0)}% × Education))
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 text-center space-y-1">
            <span className="text-xs text-textMuted font-mono">Skills Weight</span>
            <span className="font-mono text-2xl font-bold text-accentCyan">
              {(weights.skills * 100).toFixed(0)}%
            </span>
          </div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 text-center space-y-1">
            <span className="text-xs text-textMuted font-mono">Semantic Weight</span>
            <span className="font-mono text-2xl font-bold text-accentIndigo">
              {(weights.semantic * 100).toFixed(0)}%
            </span>
          </div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 text-center space-y-1">
            <span className="text-xs text-textMuted font-mono">Experience Weight</span>
            <span className="font-mono text-2xl font-bold text-scoreGreen">
              {(weights.experience * 100).toFixed(0)}%
            </span>
          </div>
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 text-center space-y-1">
            <span className="text-xs text-textMuted font-mono">Education Weight</span>
            <span className="font-mono text-2xl font-bold text-scoreAmber">
              {(weights.education * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* 4 Pillars of Scoring */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-card p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accentCyan/10 border border-accentCyan/30 flex items-center justify-center text-accentCyan">
              <Award className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-textPrimary text-base">1. Skills Matching (40%)</h3>
          </div>
          <p className="text-xs text-textMuted leading-relaxed">
            Identifies both exact and interchangeable skills from candidate work histories. Evaluates must-have requirements at double weight and nice-to-have skills at standard weight.
          </p>
        </div>

        <div className="glass-card p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accentIndigo/10 border border-accentIndigo/30 flex items-center justify-center text-accentIndigo">
              <Layers className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-textPrimary text-base">2. Semantic Similarity (25%)</h3>
          </div>
          <p className="text-xs text-textMuted leading-relaxed">
            Evaluates contextual alignment between candidate project descriptions and job responsibilities rather than relying solely on exact keyword presence.
          </p>
        </div>

        <div className="glass-card p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Cpu className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-textPrimary text-base">3. Experience Tenure (25%)</h3>
          </div>
          <p className="text-xs text-textMuted leading-relaxed">
            Computes non-overlapping calendar employment periods across all career roles, comparing verified tenure against the minimum required experience.
          </p>
        </div>

        <div className="glass-card p-6 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <h3 className="font-bold text-textPrimary text-base">4. Education Level (10%)</h3>
          </div>
          <p className="text-xs text-textMuted leading-relaxed">
            Grants structured credit for verified degrees (Doctorate, Master&apos;s, Bachelor&apos;s, Associate/Diploma) matching or exceeding position prerequisites.
          </p>
        </div>
      </div>

      {/* Worked Example */}
      <div className="glass-card p-6 sm:p-8 space-y-6">
        <h2 className="text-xl font-bold font-heading text-textPrimary flex items-center gap-2 border-b border-white/10 pb-4">
          <GitBranch className="w-5 h-5 text-scoreGreen" />
          Scoring Worked Example
        </h2>

        <div className="space-y-4 text-xs">
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2 font-mono">
            <p className="text-textPrimary font-semibold">
              Sample Requirements: Java (Must), Spring Boot (Must), SQL (Must), Docker (Must), AWS (Nice-to-Have)
            </p>
            <div className="p-3.5 rounded-lg bg-background border border-white/5 text-accentCyan space-y-1.5 leading-relaxed">
              <p>• Skills Component: 80% coverage → (40% × 80 = 32.0 pts)</p>
              <p>• Semantic Component: 85% alignment → (25% × 85 = 21.3 pts)</p>
              <p>• Experience Component: 4.5 yrs / 5.0 yrs required → (25% × 90 = 22.5 pts)</p>
              <p>• Education Component: Meets Bachelor&apos;s Degree → (10% × 100 = 10.0 pts)</p>
              <div className="border-t border-white/10 pt-2 font-bold text-textPrimary text-sm flex items-center justify-between">
                <span>Final Matching Score</span>
                <span className="text-accentCyan font-mono">86 / 100</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
