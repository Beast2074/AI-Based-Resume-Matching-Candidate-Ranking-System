import { CheckCircle2, ShieldAlert } from "lucide-react";

interface ComponentItem {
  name: string;
  raw: number;
  weight: number;
  points: number;
}

interface WaterfallChartProps {
  components: ComponentItem[];
  totalScore: number;
  capped: boolean;
}

export default function WaterfallChart({
  components,
  totalScore,
  capped,
}: WaterfallChartProps) {
  const formulaText = components.length > 0
    ? components.map((c) => `${c.name.split(" ")[0]} (${(c.weight * 100).toFixed(0)}%)`).join(" + ")
    : "Skills (40%) + Semantic (25%) + Experience (25%) + Education (10%)";

  const colors = [
    {
      gradient: "from-accentIndigo to-indigo-400",
      bg: "bg-accentIndigo",
      text: "text-accentIndigo",
    },
    {
      gradient: "from-accentCyan to-cyan-400",
      bg: "bg-accentCyan",
      text: "text-accentCyan",
    },
    {
      gradient: "from-emerald-500 to-scoreGreen",
      bg: "bg-emerald-500",
      text: "text-scoreGreen",
    },
    {
      gradient: "from-amber-500 to-amber-400",
      bg: "bg-amber-500",
      text: "text-scoreAmber",
    },
  ];

  return (
    <div className="glass-card p-6 space-y-6">
      <div className="flex items-center justify-between border-b border-white/5 pb-4">
        <div>
          <h3 className="font-heading font-semibold text-lg text-textPrimary">
            Points Composition Breakdown
          </h3>
          <p className="text-xs text-textMuted mt-0.5">
            Transparent additive formula: {formulaText}
          </p>
        </div>
        {capped ? (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-scoreAmber/10 border border-scoreAmber/30 text-scoreAmber text-xs font-mono">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Score Capped (Gate Policy)</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-scoreGreen/10 border border-scoreGreen/30 text-scoreGreen text-xs font-mono">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Fully Additive (100 pts)</span>
          </div>
        )}
      </div>

      <div className="space-y-4">
        {components.map((step, idx) => {
          const color = colors[idx % colors.length];
          const maxPts = step.weight * 100;
          const percentage = Math.min(100, Math.max(0, step.raw * 100));

          return (
            <div key={step.name} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-textPrimary">{step.name}</span>
                <span className="font-mono text-textMuted">
                  {step.raw.toFixed(2)} raw × {maxPts.toFixed(0)}% ={" "}
                  <strong className={`${color.text} font-semibold`}>
                    +{step.points.toFixed(1)} pts
                  </strong>
                  <span className="text-textMuted/60 text-[11px] ml-1">
                    (of {maxPts.toFixed(0)} max)
                  </span>
                </span>
              </div>

              {/* Individual clean progress bar starting from left (0 to 100% of category) */}
              <div className="w-full bg-white/[0.04] rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-full rounded-full bg-gradient-to-r ${color.gradient} transition-all duration-700 ease-out`}
                  style={{
                    width: `${percentage}%`,
                  }}
                />
              </div>
            </div>
          );
        })}

        {/* Combined Cumulative Stacked Bar */}
        <div className="pt-4 border-t border-white/5 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="font-heading font-semibold text-textPrimary">Cumulative Score Composition</span>
              {capped && (
                <span className="text-[11px] font-mono text-scoreAmber bg-scoreAmber/10 px-2 py-0.5 rounded">
                  Capped at 65
                </span>
              )}
            </div>
            <span className="font-mono font-bold text-base text-textPrimary">
              {totalScore} <span className="text-xs text-textMuted font-normal">/ 100 pts</span>
            </span>
          </div>

          {/* Seamless stacked track without gaps or floating shapes */}
          <div className="w-full bg-white/[0.04] rounded-full h-3 overflow-hidden flex">
            {components.map((step, idx) => {
              const color = colors[idx % colors.length];
              return (
                <div
                  key={step.name}
                  className={`h-full bg-gradient-to-r ${color.gradient} transition-all duration-700 ease-out`}
                  style={{ width: `${Math.max(0, step.points)}%` }}
                  title={`${step.name}: +${step.points.toFixed(1)} pts`}
                />
              );
            })}
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-textMuted pt-0.5">
            <span>0 pts</span>
            <span>50 pts</span>
            <span>100 pts</span>
          </div>
        </div>
      </div>
    </div>
  );
}
