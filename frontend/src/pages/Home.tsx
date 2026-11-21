import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createJob, uploadJobFile, updateRequirements, Job } from "../lib/api";
import {
  Upload,
  ArrowRight,
  FileText,
  Check,
  Plus,
  X,
  GraduationCap,
  Clock,
} from "lucide-react";

export default function Home() {
  const navigate = useNavigate();
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Review step state
  const [job, setJob] = useState<Job | null>(null);
  const [mustHaveSkills, setMustHaveSkills] = useState<string[]>([]);
  const [niceToHaveSkills, setNiceToHaveSkills] = useState<string[]>([]);
  const [requiredYears, setRequiredYears] = useState<number>(0);
  const [degreeLevel, setDegreeLevel] = useState<number>(0);
  const [newSkill, setNewSkill] = useState("");
  const [newSkillType, setNewSkillType] = useState<"must" | "nice">("must");
  const [savingReqs, setSavingReqs] = useState(false);

  const handleCreateJob = async () => {
    if (!jdText.trim() || jdText.trim().length < 20) {
      setError("Please provide a job description with at least 20 characters.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const created = await createJob(jdText);
      populateReviewState(created);
    } catch (err: any) {
      setError(err.message || "Failed to parse job description.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setLoading(true);

    try {
      const created = await uploadJobFile(file);
      populateReviewState(created);
    } catch (err: any) {
      setError(err.message || "Failed to upload and parse job description.");
    } finally {
      setLoading(false);
    }
  };

  const populateReviewState = (createdJob: Job) => {
    setJob(createdJob);
    const reqs = createdJob.requirements || {};
    const skillsList = reqs.skills || [];

    const must = skillsList
      .filter((s: any) => s.importance === "must_have")
      .map((s: any) => s.name || s.skill || "")
      .filter((s: string) => Boolean(s && s.trim()));
    const nice = skillsList
      .filter((s: any) => s.importance === "nice_to_have")
      .map((s: any) => s.name || s.skill || "")
      .filter((s: string) => Boolean(s && s.trim()));

    setMustHaveSkills(must);
    setNiceToHaveSkills(nice);
    setRequiredYears(reqs.required_years || 0);
    setDegreeLevel(reqs.degree_level || 0);
  };

  const removeSkill = (skill: string, type: "must" | "nice") => {
    if (type === "must") {
      setMustHaveSkills(mustHaveSkills.filter((s) => s !== skill));
    } else {
      setNiceToHaveSkills(niceToHaveSkills.filter((s) => s !== skill));
    }
  };

  const addCustomSkill = () => {
    const trimmed = newSkill.trim();
    if (!trimmed) return;

    if (newSkillType === "must") {
      if (!mustHaveSkills.includes(trimmed)) {
        setMustHaveSkills([...mustHaveSkills, trimmed]);
      }
    } else {
      if (!niceToHaveSkills.includes(trimmed)) {
        setNiceToHaveSkills([...niceToHaveSkills, trimmed]);
      }
    }
    setNewSkill("");
  };

  const handleConfirmAndProceed = async () => {
    if (!job) return;
    setSavingReqs(true);
    setError(null);
    try {
      const updatedSkills = [
        ...mustHaveSkills.map((s) => ({ name: s, skill: s, importance: "must_have" })),
        ...niceToHaveSkills.map((s) => ({ name: s, skill: s, importance: "nice_to_have" })),
      ];

      await updateRequirements(job.id, {
        skills: updatedSkills,
        required_years: requiredYears,
        degree_level: degreeLevel,
      });

      navigate(`/upload/${job.id}`);
    } catch (err: any) {
      console.error("Failed to update requirements:", err);
      setError(err.message || "Failed to update requirements");
      setSavingReqs(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12 space-y-8 animate-fadeIn">
      {/* Hero Header */}
      <div className="text-center space-y-3">
        <h1 className="text-3xl sm:text-4xl font-extrabold font-heading tracking-tight text-textPrimary">
          AI-Based Resume Matching &amp; Candidate Ranking System
        </h1>
        <p className="text-textMuted max-w-2xl mx-auto text-sm sm:text-base">
          Compare multiple candidate resumes against your job requirements and generate transparent, objective matching scores.
        </p>
      </div>

      {!job ? (
        <div className="space-y-6">
          {/* Job Description Input Card */}
          <div className="glass-card p-6 sm:p-8 space-y-5">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <label className="text-sm font-semibold text-textPrimary flex items-center gap-2">
                <FileText className="w-4 h-4 text-accentCyan" />
                <span>Job Description Input</span>
              </label>

              <label className="cursor-pointer px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs font-medium text-textPrimary border border-white/10 transition inline-flex items-center gap-2">
                <Upload className="w-3.5 h-3.5 text-accentCyan" />
                <span>Upload Document (.txt, .pdf, .docx)</span>
                <input
                  type="file"
                  accept=".txt,.pdf,.docx"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>

            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste job description requirements, key responsibilities, experience, and qualifications here..."
              rows={12}
              className="w-full rounded-xl bg-background/70 border border-white/10 p-4 text-sm font-mono text-textPrimary placeholder:text-textMuted/60 focus:outline-none focus:border-accentCyan focus:ring-1 focus:ring-accentCyan transition resize-y"
            />

            {error && (
              <div className="p-3.5 rounded-xl bg-scoreRed/10 border border-scoreRed/30 text-scoreRed text-xs">
                {error}
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs font-mono text-textMuted">
                {jdText.length > 0 ? `${jdText.length} characters entered` : "Supports paste or multi-format file upload"}
              </span>

              <button
                onClick={handleCreateJob}
                disabled={loading}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-accentIndigo to-accentCyan text-white text-sm font-semibold hover:opacity-95 transition disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-accentIndigo/20"
              >
                {loading ? (
                  <span>Extracting Key Requirements...</span>
                ) : (
                  <>
                    <span>Extract Key Requirements</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Requirements Review Section */
        <div className="glass-card p-6 sm:p-8 space-y-8 animate-fadeIn">
          <div className="border-b border-white/10 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-mono text-accentCyan bg-accentCyan/10 px-2.5 py-0.5 rounded-full mb-2">
                <Check className="w-3.5 h-3.5" />
                <span>Extracted Requirements</span>
              </div>
              <h2 className="text-2xl font-bold font-heading text-textPrimary">{job.title}</h2>
              <p className="text-xs text-textMuted mt-1">
                Review and adjust extracted skills, required tenure, and education level before batch uploading resumes.
              </p>
            </div>

            <button
              onClick={() => setJob(null)}
              className="text-xs text-textMuted hover:text-textPrimary transition px-3 py-1.5 rounded-lg border border-white/10 self-start sm:self-auto"
            >
              Change Job Description
            </button>
          </div>

          {/* Parameters Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <label className="text-xs font-medium text-textMuted flex items-center gap-2">
                <Clock className="w-4 h-4 text-accentCyan" />
                Minimum Required Experience
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min="0"
                  max="20"
                  value={requiredYears}
                  onChange={(e) => setRequiredYears(Math.max(0, parseInt(e.target.value) || 0))}
                  className="w-24 px-3 py-1.5 rounded-lg bg-background border border-white/10 text-sm font-mono text-textPrimary focus:outline-none focus:border-accentCyan"
                />
                <span className="text-sm text-textMuted">years</span>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <label className="text-xs font-medium text-textMuted flex items-center gap-2">
                <GraduationCap className="w-4 h-4 text-accentIndigo" />
                Minimum Degree Requirement
              </label>
              <select
                value={degreeLevel}
                onChange={(e) => setDegreeLevel(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-1.5 rounded-lg bg-background border border-white/10 text-sm font-mono text-textPrimary focus:outline-none focus:border-accentCyan"
              >
                <option value="0">None / Any Education Level</option>
                <option value="1">Associate Degree / Diploma</option>
                <option value="2">Bachelor&apos;s Degree (B.S. / B.A. / B.Tech)</option>
                <option value="3">Master&apos;s Degree (M.S. / M.A. / M.Tech / MBA)</option>
                <option value="4">Doctorate (Ph.D.)</option>
              </select>
            </div>
          </div>

          {/* Must-Have Skills */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-textPrimary flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accentCyan"></span>
                Must-Have Skills (Core Prerequisites)
              </h3>
              <span className="text-xs text-textMuted font-mono">
                {mustHaveSkills.length} required
              </span>
            </div>

            <div className="flex flex-wrap gap-2 min-h-[40px] p-3 rounded-xl bg-white/[0.02] border border-white/5">
              {mustHaveSkills.length === 0 ? (
                <span className="text-xs text-textMuted italic">No must-have skills specified</span>
              ) : (
                mustHaveSkills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-accentCyan/10 text-accentCyan border border-accentCyan/20 shadow-sm"
                  >
                    <span className="font-medium text-textPrimary">{skill}</span>
                    <button
                      type="button"
                      onClick={() => removeSkill(skill, "must")}
                      className="hover:text-scoreRed transition p-0.5 rounded text-accentCyan/70 hover:bg-white/10"
                      title={`Remove ${skill}`}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))
              )}
            </div>
          </div>

          {/* Nice-To-Have Skills */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-textPrimary flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-accentIndigo"></span>
                Nice-To-Have Skills (Preferred)
              </h3>
              <span className="text-xs text-textMuted font-mono">
                {niceToHaveSkills.length} preferred
              </span>
            </div>

            <div className="flex flex-wrap gap-2 min-h-[40px] p-3 rounded-xl bg-white/[0.02] border border-white/5">
              {niceToHaveSkills.length === 0 ? (
                <span className="text-xs text-textMuted italic">No nice-to-have skills specified</span>
              ) : (
                niceToHaveSkills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-accentIndigo/10 text-accentIndigo border border-accentIndigo/20 shadow-sm"
                  >
                    <span className="font-medium text-textPrimary">{skill}</span>
                    <button
                      type="button"
                      onClick={() => removeSkill(skill, "nice")}
                      className="hover:text-scoreRed transition p-0.5 rounded text-accentIndigo/70 hover:bg-white/10"
                      title={`Remove ${skill}`}
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </span>
                ))
              )}
            </div>
          </div>

          {/* Add Skill Field */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-3">
            <label className="text-xs font-medium text-textMuted">Add Custom Skill or Requirement</label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={newSkill}
                onChange={(e) => setNewSkill(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addCustomSkill()}
                placeholder="e.g. Java, Kotlin, Docker, AWS"
                className="flex-1 min-w-[200px] px-3 py-1.5 rounded-lg bg-background border border-white/10 text-xs text-textPrimary placeholder:text-textMuted/50 focus:outline-none focus:border-accentCyan font-mono"
              />

              <select
                value={newSkillType}
                onChange={(e) => setNewSkillType(e.target.value as "must" | "nice")}
                className="px-3 py-1.5 rounded-lg bg-background border border-white/10 text-xs text-textPrimary focus:outline-none focus:border-accentCyan font-mono"
              >
                <option value="must">Must-Have</option>
                <option value="nice">Nice-To-Have</option>
              </select>

              <button
                onClick={addCustomSkill}
                className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-textPrimary flex items-center gap-1 transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add</span>
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 rounded-xl bg-scoreRed/10 border border-scoreRed/30 text-scoreRed text-xs">
              {error}
            </div>
          )}

          {/* Action Bar */}
          <div className="border-t border-white/10 pt-6 flex items-center justify-end">
            <button
              onClick={handleConfirmAndProceed}
              disabled={savingReqs}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-accentIndigo to-accentCyan text-white text-sm font-semibold hover:opacity-95 transition disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-accentIndigo/20"
            >
              <span>{savingReqs ? "Saving..." : "Save & Proceed to Resume Upload"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
