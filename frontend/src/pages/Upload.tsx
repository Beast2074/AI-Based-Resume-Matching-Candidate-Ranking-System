import { useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useDropzone } from "react-dropzone";
import { uploadResume, runMatching, CandidateSummary } from "../lib/api";
import {
  Upload as UploadIcon,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Play,
  ArrowLeft,
  File,
  CheckCircle2,
} from "lucide-react";

interface UploadItem {
  id: string;
  file: File;
  status: "queued" | "uploading" | "parsed" | "error" | "no_text_layer";
  result?: CandidateSummary;
  error?: string;
}

const CONCURRENCY_LIMIT = 3;

export default function Upload() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const [items, setItems] = useState<UploadItem[]>([]);
  const [matching, setMatching] = useState(false);
  const [matchError, setMatchError] = useState<string | null>(null);

  // Upload worker pool processing up to 3 files concurrently
  const processUploadQueue = async (currentItems: UploadItem[]) => {
    let updated = [...currentItems];
    const pendingIndices = updated
      .map((item, idx) => ({ item, idx }))
      .filter(({ item }) => item.status === "queued");

    if (pendingIndices.length === 0 || !jobId) return;

    // Process in batches of 3
    const batch = pendingIndices.slice(0, CONCURRENCY_LIMIT);
    
    // Mark batch as uploading
    setItems((prev) =>
      prev.map((it) =>
        batch.some((b) => b.item.id === it.id) ? { ...it, status: "uploading" } : it
      )
    );

    await Promise.all(
      batch.map(async ({ item }) => {
        try {
          const res = await uploadResume(jobId, item.file);
          setItems((prev) =>
            prev.map((it) =>
              it.id === item.id
                ? {
                    ...it,
                    status: res.parse_status === "no_text_layer" ? "no_text_layer" : "parsed",
                    result: res,
                  }
                : it
            )
          );
        } catch (err: any) {
          setItems((prev) =>
            prev.map((it) =>
              it.id === item.id
                ? { ...it, status: "error", error: err?.message || "Upload failed" }
                : it
            )
          );
        }
      })
    );

    // Re-check remaining queue recursively
    setItems((prev) => {
      const stillPending = prev.some((it) => it.status === "queued");
      if (stillPending) {
        setTimeout(() => processUploadQueue(prev), 100);
      }
      return prev;
    });
  };

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setItems((prev) => {
        const existingNames = new Set(prev.map((it) => it.file.name));
        const uniqueFiles = acceptedFiles.filter((f) => !existingNames.has(f.name));
        if (uniqueFiles.length === 0) return prev;

        const newItems: UploadItem[] = uniqueFiles.map((file) => ({
          id: `${file.name}-${Date.now()}-${Math.random()}`,
          file,
          status: "queued",
        }));

        const next = [...prev, ...newItems];
        setTimeout(() => processUploadQueue(next), 50);
        return next;
      });
    },
    [jobId]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    },
    maxSize: 4 * 1024 * 1024,
  });

  const retryUpload = (id: string) => {
    setItems((prev) => {
      const next = prev.map((it) => (it.id === id ? { ...it, status: "queued" as const, error: undefined } : it));
      setTimeout(() => processUploadQueue(next), 50);
      return next;
    });
  };

  const handleRunMatching = async () => {
    if (!jobId) return;
    setMatching(true);
    setMatchError(null);
    try {
      await runMatching(jobId);
      navigate(`/ranking/${jobId}`);
    } catch (err: any) {
      setMatchError(err?.message || "Matching engine error");
      setMatching(false);
    }
  };

  const parsedCount = items.filter((i) => i.status === "parsed" || i.status === "no_text_layer").length;
  const isUploading = items.some((i) => i.status === "uploading" || i.status === "queued");

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-xs text-textMuted hover:text-textPrimary flex items-center gap-1.5 mb-2 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Job Setup</span>
          </button>
          <h1 className="text-3xl font-bold font-heading text-textPrimary">Upload Resumes</h1>
          <p className="text-sm text-textMuted mt-1">
            Upload candidate resumes (.PDF and .DOCX, up to 4 MB each).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunMatching}
            disabled={parsedCount === 0 || isUploading || matching}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-accentIndigo to-accentCyan text-white text-sm font-semibold hover:opacity-95 transition disabled:opacity-40 flex items-center gap-2 shadow-lg shadow-accentIndigo/25"
          >
            {matching ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Computing Match Scores...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Run Matching ({parsedCount} ready)</span>
              </>
            )}
          </button>
        </div>
      </div>

      {matchError && (
        <div className="p-4 rounded-xl bg-scoreRed/10 border border-scoreRed/30 text-scoreRed text-sm flex items-center gap-2">
          <XCircle className="w-5 h-5 shrink-0" />
          <span>{matchError}</span>
        </div>
      )}

      {/* Dropzone Card */}
      <div
        {...getRootProps()}
        className={`glass-card p-10 border-2 border-dashed transition-all cursor-pointer text-center space-y-3 ${
          isDragActive
            ? "border-accentCyan bg-accentCyan/5"
            : "border-white/10 hover:border-accentIndigo/50 hover:bg-white/[0.06]"
        }`}
      >
        <input {...getInputProps()} />
        <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto text-accentCyan">
          <UploadIcon className="w-6 h-6" />
        </div>
        <div>
          <p className="text-base font-medium text-textPrimary">
            {isDragActive ? "Drop candidate resumes here" : "Drag and drop 10+ resumes here, or browse files"}
          </p>
          <p className="text-xs text-textMuted mt-1 font-mono">
            Supports PDF & DOCX • Max 4 MB per file • Up to 3 parallel uploads
          </p>
        </div>
      </div>

      {/* Files List */}
      {items.length > 0 && (
        <div className="glass-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/5 pb-3">
            <h3 className="text-sm font-heading font-semibold text-textPrimary">
              Uploaded Files ({items.length})
            </h3>
            <span className="text-xs font-mono text-textMuted">
              {parsedCount} of {items.length} parsed
            </span>
          </div>

          <div className="divide-y divide-white/5">
            {items.map((item) => (
              <div
                key={item.id}
                className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="flex items-center gap-3">
                  <File className="w-4 h-4 text-textMuted shrink-0" />
                  <div>
                    <span className="font-mono text-textPrimary block truncate max-w-xs sm:max-w-md">
                      {item.file.name}
                    </span>
                    <span className="text-[11px] text-textMuted">
                      {(item.file.size / 1024).toFixed(1)} KB
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  {/* Status Indicator */}
                  {item.status === "uploading" && (
                    <span className="flex items-center gap-1.5 text-accentCyan font-mono">
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Parsing...</span>
                    </span>
                  )}

                  {item.status === "queued" && (
                    <span className="text-textMuted font-mono">Queued</span>
                  )}

                  {item.status === "parsed" && (
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="font-medium text-textPrimary block">
                          {item.result?.name || "Extracted Name"}
                        </span>
                        <span className="text-textMuted text-[11px] font-mono">
                          {item.result?.total_years.toFixed(1)} yrs exp
                        </span>
                      </div>
                      <CheckCircle2 className="w-4 h-4 text-scoreGreen" />
                    </div>
                  )}

                  {item.status === "no_text_layer" && (
                    <div className="flex items-center gap-2 text-scoreAmber">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span className="text-[11px]">No extractable text (scanned document)</span>
                    </div>
                  )}

                  {item.status === "error" && (
                    <div className="flex items-center gap-2">
                      <span className="text-scoreRed text-[11px]">{item.error || "Failed"}</span>
                      <button
                        onClick={() => retryUpload(item.id)}
                        className="p-1 rounded hover:bg-white/10 text-textMuted hover:text-textPrimary"
                        title="Retry upload"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
