/**
 * API Client with Zod runtime validation.
 */
import { z } from "zod";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// --- Zod Schemas ---

export const HealthSchema = z.object({
  status: z.string(),
  model_loaded: z.boolean(),
  version: z.string(),
});
export type HealthResponse = z.infer<typeof HealthSchema>;

export const ScoringConfigSchema = z.object({
  weights: z.object({
    skills: z.number(),
    semantic: z.number(),
    experience: z.number(),
    education: z.number(),
  }),
  skill_weights: z.object({
    must_have: z.number(),
    nice_to_have: z.number(),
  }),
  skill_credits: z.object({
    exact_experience: z.number(),
    exact_skills_list: z.number(),
    exact_other: z.number(),
    partial_semantic_factor: z.number(),
  }),
  thresholds: z.object({
    tau_low: z.number(),
    tau_high: z.number(),
    relevant_experience_cosine: z.number(),
  }),
  gate: z.object({
    must_have_coverage_threshold: z.number(),
    cap_score: z.number(),
    flag_name: z.string(),
  }),
});
export type ScoringConfig = z.infer<typeof ScoringConfigSchema>;

export const JobSchema = z.object({
  id: z.string(),
  title: z.string(),
  raw_text: z.string(),
  requirements: z.record(z.any()),
  required_years: z.number().nullable().optional(),
  degree_level: z.number(),
  created_at: z.string(),
});
export type Job = z.infer<typeof JobSchema>;

export const CandidateSummarySchema = z.object({
  id: z.string(),
  job_id: z.string(),
  filename: z.string(),
  parse_status: z.string(),
  parse_warnings: z.array(z.string()),
  name: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  total_years: z.number(),
  skills: z.array(z.any()),
  created_at: z.string(),
});
export type CandidateSummary = z.infer<typeof CandidateSummarySchema>;

export const RankingCandidateItemSchema = z.object({
  rank: z.number(),
  id: z.string(),
  filename: z.string(),
  name: z.string(),
  email: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  total_years: z.number(),
  relevant_years: z.number(),
  total: z.number(),
  skills_score: z.number(),
  semantic_score: z.number(),
  experience_score: z.number(),
  education_score: z.number(),
  must_have_coverage: z.number(),
  capped: z.boolean(),
  matched_skills: z.array(z.string()),
  flags: z.array(z.string()),
});
export type RankingCandidateItem = z.infer<typeof RankingCandidateItemSchema>;

export const RankingResponseSchema = z.object({
  job_id: z.string(),
  summary: z.object({
    total_candidates: z.number(),
    scored_candidates: z.number(),
    top_score: z.number(),
    median_score: z.number(),
    capped_count: z.number(),
  }),
  candidates: z.array(RankingCandidateItemSchema),
});
export type RankingResponse = z.infer<typeof RankingResponseSchema>;

export const CandidateDetailSchema = z.object({
  id: z.string(),
  job_id: z.string(),
  filename: z.string(),
  name: z.string(),
  email: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  parse_status: z.string(),
  parse_warnings: z.array(z.string()),
  total_years: z.number(),
  raw_text: z.string(),
  sections: z.record(z.string()),
  skills: z.array(z.any()),
  entries: z.array(z.any()),
  education: z.record(z.any()),
  score: z.record(z.any()).nullable().optional(),
  explanation: z.record(z.any()).nullable().optional(),
});
export type CandidateDetail = z.infer<typeof CandidateDetailSchema>;

// --- API Client Methods ---

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  const data = await res.json();
  return HealthSchema.parse(data);
}

export async function fetchScoringConfig(): Promise<ScoringConfig> {
  const res = await fetch(`${API_BASE_URL}/api/scoring-config`);
  if (!res.ok) throw new Error(`Failed to fetch scoring config: ${res.statusText}`);
  const data = await res.json();
  return ScoringConfigSchema.parse(data);
}

export async function createJob(text: string, title?: string): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, title }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create job");
  }
  return JobSchema.parse(await res.json());
}

export async function uploadJobFile(file: File): Promise<Job> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/jobs/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload job file");
  }
  return JobSchema.parse(await res.json());
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("Job not found");
  return JobSchema.parse(await res.json());
}

export async function updateRequirements(
  jobId: string,
  payload: { title?: string; skills: any[]; required_years?: number; degree_level?: number }
): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/requirements`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update requirements");
  return JobSchema.parse(await res.json());
}

export async function uploadResume(jobId: string, file: File): Promise<CandidateSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/resumes`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: ${res.statusText}`);
  }
  return CandidateSummarySchema.parse(await res.json());
}

export async function runMatching(jobId: string): Promise<{ scored_count: number; message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/match`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to run candidate matching");
  return res.json();
}

export async function getRanking(
  jobId: string,
  minScore: number = 0,
  anonymize: boolean = false
): Promise<RankingResponse> {
  const params = new URLSearchParams({
    min_score: minScore.toString(),
    anonymize: anonymize.toString(),
  });
  const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/ranking?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch ranking");
  return RankingResponseSchema.parse(await res.json());
}

export async function getCandidate(candidateId: string, anonymize: boolean = false): Promise<CandidateDetail> {
  const res = await fetch(`${API_BASE_URL}/api/candidates/${candidateId}?anonymize=${anonymize}`);
  if (!res.ok) throw new Error("Candidate not found");
  return CandidateDetailSchema.parse(await res.json());
}

export function getExportCsvUrl(jobId: string): string {
  return `${API_BASE_URL}/api/jobs/${jobId}/export.csv`;
}

// --- Live Logging & Admin Diagnostics ---

export interface DiagnosticLog {
  id: number;
  timestamp: string;
  subsystem: string;
  level: string;
  message: string;
  details: Record<string, any>;
}

export interface TelemetryStatus {
  status: string;
  uptime_seconds: number;
  total_logs: number;
  error_count: number;
  warning_count: number;
  model_loaded: boolean;
  model_name: string;
  database_status: string;
  total_jobs: number;
  total_candidates: number;
}

export interface LogsResponse {
  status: string;
  telemetry: TelemetryStatus;
  count: number;
  logs: DiagnosticLog[];
}

export async function verifyAdminPassword(password: string): Promise<boolean> {
  const res = await fetch(`${API_BASE_URL}/api/admin/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  return data.authenticated === true;
}

export async function fetchSystemLogs(
  password: string,
  sinceId: number = 0,
  level?: string,
  subsystem?: string
): Promise<LogsResponse> {
  const params = new URLSearchParams({ since_id: sinceId.toString() });
  if (level && level !== "ALL") params.append("level", level);
  if (subsystem && subsystem !== "ALL") params.append("subsystem", subsystem);

  const res = await fetch(`${API_BASE_URL}/api/admin/logs?${params.toString()}`, {
    headers: {
      "X-Admin-Password": password,
    },
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error("UNAUTHORIZED");
    }
    throw new Error(`Failed to fetch logs: ${res.statusText}`);
  }
  return res.json();
}

export async function clearSystemLogs(password: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/admin/logs`, {
    method: "DELETE",
    headers: {
      "X-Admin-Password": password,
    },
  });
  if (!res.ok) {
    throw new Error("Failed to clear diagnostic logs");
  }
}
