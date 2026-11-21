export function getScoreColor(score: number): {
  text: string;
  bg: string;
  border: string;
  hex: string;
  label: string;
} {
  if (score >= 85) {
    return {
      text: "text-scoreGreen",
      bg: "bg-scoreGreen/10",
      border: "border-scoreGreen/30",
      hex: "#10B981",
      label: "Strong Match",
    };
  }
  if (score >= 70) {
    return {
      text: "text-scoreCyan",
      bg: "bg-scoreCyan/10",
      border: "border-scoreCyan/30",
      hex: "#22D3EE",
      label: "Good Match",
    };
  }
  if (score >= 50) {
    return {
      text: "text-scoreAmber",
      bg: "bg-scoreAmber/10",
      border: "border-scoreAmber/30",
      hex: "#F59E0B",
      label: "Moderate Match",
    };
  }
  return {
    text: "text-scoreRed",
    bg: "bg-scoreRed/10",
    border: "border-scoreRed/30",
    hex: "#EF4444",
    label: "Low Match",
  };
}

interface ScoreGaugeProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
}

export default function ScoreGauge({
  score,
  size = 180,
  strokeWidth = 14,
  showLabel = true,
}: ScoreGaugeProps) {
  const color = getScoreColor(score);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="w-full h-full -rotate-90 transform" viewBox={`0 0 ${size} ${size}`}>
          {/* Background Ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-white/5"
            fill="transparent"
          />
          {/* Progress Ring */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color.hex}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            style={{
              transition: "stroke-dashoffset 800ms ease-out",
              filter: `drop-shadow(0 0 10px ${color.hex}44)`,
            }}
          />
        </svg>

        {/* Center Label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono font-bold text-4xl sm:text-5xl tracking-tight text-textPrimary">
            {score}
          </span>
          <span className="text-xs uppercase font-mono tracking-wider text-textMuted mt-0.5">
            Match Score
          </span>
        </div>
      </div>

      {showLabel && (
        <div className="mt-3 text-center">
          <span
            className={`inline-block px-3 py-1 rounded-full text-xs font-mono font-medium border ${color.bg} ${color.text} ${color.border}`}
          >
            {color.label}
          </span>
        </div>
      )}
    </div>
  );
}
