import { Link, useLocation } from "react-router-dom";
import { Sparkles, FileText, BarChart3, Terminal } from "lucide-react";
import { useState } from "react";
import AdminLogModal from "./AdminLogModal";

export default function Navbar() {
  const location = useLocation();
  const [showLogs, setShowLogs] = useState(false);

  return (
    <>
      <header className="border-b border-white/10 bg-[#0B0F19]/90 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-accentIndigo to-accentCyan flex items-center justify-center text-white shadow-lg shadow-accentIndigo/20 group-hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-heading font-bold text-base sm:text-lg tracking-tight text-textPrimary leading-tight">
                AI-Based Resume Matching & Candidate Ranking System
              </span>
            </div>
          </Link>

          <nav className="flex items-center gap-1.5 sm:gap-3">
            <Link
              to="/"
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition ${
                location.pathname === "/"
                  ? "text-accentCyan bg-white/5 border border-accentCyan/20"
                  : "text-textMuted hover:text-textPrimary hover:bg-white/[0.03]"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" />
                <span>Job & Resumes</span>
              </span>
            </Link>

            <Link
              to="/how-it-works"
              className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition ${
                location.pathname === "/how-it-works"
                  ? "text-accentCyan bg-white/5 border border-accentCyan/20"
                  : "text-textMuted hover:text-textPrimary hover:bg-white/[0.03]"
              }`}
            >
              <span className="flex items-center gap-1.5">
                <BarChart3 className="w-3.5 h-3.5" />
                <span>Ranking Criteria</span>
              </span>
            </Link>

            {/* Diagnostic Logs (Admin 12345) */}
            <button
              onClick={() => setShowLogs(true)}
              className="px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/10 text-textMuted hover:text-accentCyan border border-white/10 transition flex items-center gap-1.5 text-xs font-mono ml-1"
              title="System Diagnostics & Telemetry (Admin Password: 12345)"
            >
              <Terminal className="w-3.5 h-3.5 text-accentCyan" />
              <span className="hidden md:inline">Logs</span>
            </button>
          </nav>
        </div>
      </header>

      {/* Admin Diagnostic Console Modal */}
      <AdminLogModal isOpen={showLogs} onClose={() => setShowLogs(false)} />
    </>
  );
}
