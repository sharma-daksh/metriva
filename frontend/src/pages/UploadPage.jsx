import { useCallback, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { previewUpload, commitUpload } from "../services/api";

const CANONICAL_FIELDS = [
  { field: "transaction_id", label: "Transaction ID", required: false },
  { field: "merchant_id", label: "Merchant ID", required: true },
  { field: "timestamp", label: "Timestamp", required: true },
  { field: "amount", label: "Amount", required: true },
  { field: "status", label: "Status", required: true },
  { field: "payment_method", label: "Payment Method", required: false },
  { field: "payment_processor_or_bank", label: "Payment Processor / Bank", required: false },
  { field: "sender_bank", label: "Sender Bank", required: false },
  { field: "receiver_bank", label: "Receiver Bank", required: false },
  { field: "device_type", label: "Device Type", required: false },
  { field: "network_type", label: "Network Type", required: false },
  { field: "state", label: "State", required: false },
  { field: "merchant_category", label: "Merchant Category", required: false },
  { field: "customer_id", label: "Customer ID", required: false },
];

const STEPS = { PICK: "pick", MAPPING: "mapping", RESULT: "result" };

export default function UploadPage() {
  const navigate = useNavigate();
  const { refreshDatasetStatus } = useOutletContext();
  const [step, setStep] = useState(STEPS.PICK);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(async (selectedFile) => {
    if (!selectedFile) return;
    setError(null);
    setBusy(true);
    setFile(selectedFile);
    try {
      const data = await previewUpload(selectedFile);
      setPreview(data);
      setMapping(data.suggested_mapping);
      setStep(STEPS.MAPPING);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }, []);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) handleFile(dropped);
  };

  const handleCommit = async () => {
    setBusy(true);
    setError(null);
    try {
      const data = await commitUpload(file, mapping);
      setResult(data);
      setStep(STEPS.RESULT);
      if (data.success) refreshDatasetStatus();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const missingRequired = CANONICAL_FIELDS.filter((f) => f.required && !mapping[f.field]);

  return (
    <div>
      <h1 style={styles.h1}>Upload Payment Data</h1>
      <p style={styles.subtitle}>
        Upload your own transaction CSV. It goes through the same validation, anomaly detection,
        and incident pipeline as the built-in demo — once activated, the whole dashboard reflects
        your data.
      </p>

      {error && <div style={styles.errorBox}>{error}</div>}

      {step === STEPS.PICK && (
        <div
          style={{ ...styles.dropzone, ...(dragOver ? styles.dropzoneActive : {}) }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <p style={styles.dropzoneText}>Drag &amp; drop a CSV file here</p>
          <p style={styles.dropzoneOr}>or</p>
          <label style={styles.chooseBtn}>
            Choose CSV
            <input
              type="file"
              accept=".csv"
              style={{ display: "none" }}
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
          </label>
          {busy && <p style={styles.busyText}>Reading file…</p>}
        </div>
      )}

      {step === STEPS.MAPPING && preview && (
        <div>
          <div style={styles.summaryBox}>
            <strong>{preview.row_count.toLocaleString("en-IN")} rows</strong> detected in{" "}
            <strong>{preview.filename}</strong>, with {preview.columns_found.length} columns.
          </div>

          <h2 style={styles.h2}>Confirm column mapping</h2>
          <p style={styles.subnote}>
            We matched columns automatically where we could. Review and correct any before
            continuing — fields left unmapped are treated as unavailable, never guessed.
          </p>

          <div style={styles.mappingTable}>
            <div style={styles.mappingHeaderRow}>
              <div>Metriva field</div>
              <div>Your column</div>
            </div>
            {CANONICAL_FIELDS.map(({ field, label, required }) => (
              <div key={field} style={styles.mappingRow}>
                <div style={styles.mappingFieldLabel}>
                  {label} {required && <span style={styles.requiredMark}>*</span>}
                </div>
                <select
                  value={mapping[field] || ""}
                  onChange={(e) => setMapping({ ...mapping, [field]: e.target.value || null })}
                  style={{
                    ...styles.mappingSelect,
                    ...(required && !mapping[field] ? styles.mappingSelectMissing : {}),
                  }}
                >
                  <option value="">— not available —</option>
                  {preview.columns_found.map((col) => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          {missingRequired.length > 0 && (
            <p style={styles.warningText}>
              Required before continuing: {missingRequired.map((f) => f.label).join(", ")}
            </p>
          )}

          <h2 style={styles.h2}>Preview</h2>
          <div style={styles.previewTableWrap}>
            <table style={styles.previewTable}>
              <thead>
                <tr>{preview.columns_found.map((c) => <th key={c} style={styles.previewTh}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {preview.preview_rows.map((row, i) => (
                  <tr key={i}>
                    {preview.columns_found.map((c) => (
                      <td key={c} style={styles.previewTd}>{row[c] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={styles.actionRow}>
            <button style={styles.secondaryBtn} onClick={() => { setStep(STEPS.PICK); setFile(null); setPreview(null); }}>
              Choose a different file
            </button>
            <button
              style={{ ...styles.primaryBtn, ...(missingRequired.length > 0 ? styles.btnDisabled : {}) }}
              disabled={missingRequired.length > 0 || busy}
              onClick={handleCommit}
            >
              {busy ? "Processing…" : "Continue"}
            </button>
          </div>
        </div>
      )}

      {step === STEPS.RESULT && result && (
        <div>
          {result.success ? (
            <>
              <div style={styles.successBox}>{result.message}</div>

              <h2 style={styles.h2}>Data Quality</h2>
              <div style={styles.qualityGrid}>
                <QualityStat label="Rows" value={result.quality_report.rows} />
                <QualityStat label="Valid rows" value={result.quality_report.valid_rows} good />
                <QualityStat label="Duplicate rows" value={result.quality_report.duplicate_rows} />
                <QualityStat label="Missing timestamps" value={result.quality_report.missing_timestamps} />
                <QualityStat label="Invalid amounts" value={result.quality_report.invalid_amounts} />
                <QualityStat label="Unknown statuses" value={result.quality_report.unknown_statuses} />
              </div>

              {result.generated_transaction_id && (
                <p style={styles.subnote}>
                  No transaction ID column was mapped — we generated sequential internal IDs for
                  tracking. No transaction data was invented.
                </p>
              )}

              <h2 style={styles.h2}>Summary</h2>
              <div style={styles.summaryBox}>
                <strong>{result.summary.merchants}</strong> merchants,{" "}
                <strong>{result.summary.transactions.toLocaleString("en-IN")}</strong> transactions,{" "}
                {result.summary.date_range.start} to {result.summary.date_range.end} —{" "}
                <strong>{result.summary.incidents_detected}</strong> incident(s) detected.
              </div>

              <div style={styles.actionRow}>
                <button style={styles.primaryBtn} onClick={() => navigate("/")}>
                  Go to Overview
                </button>
              </div>
            </>
          ) : (
            <>
              <div style={styles.errorBox}>{result.message}</div>
              <h2 style={styles.h2}>Data Quality</h2>
              <div style={styles.qualityGrid}>
                <QualityStat label="Rows" value={result.quality_report.rows} />
                <QualityStat label="Valid rows" value={result.quality_report.valid_rows} />
              </div>
              <div style={styles.actionRow}>
                <button style={styles.secondaryBtn} onClick={() => { setStep(STEPS.PICK); setFile(null); setPreview(null); setResult(null); }}>
                  Try a different file
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function QualityStat({ label, value, good }) {
  const flagged = !good && value > 0;
  return (
    <div style={styles.qualityCard}>
      <div style={styles.qualityLabel}>{label}</div>
      <div style={{ ...styles.qualityValue, color: flagged ? "#dc2626" : "#111827" }}>{value}</div>
    </div>
  );
}

const styles = {
  h1: { fontSize: "1.6rem", margin: 0, marginBottom: 6 },
  h2: { fontSize: "1.05rem", marginTop: 28, marginBottom: 10 },
  subtitle: { color: "#6b7280", fontSize: "0.9rem", maxWidth: 640, lineHeight: 1.5 },
  subnote: { fontSize: "0.8rem", color: "#6b7280", marginBottom: 14 },
  errorBox: {
    backgroundColor: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b",
    padding: "10px 14px", borderRadius: 8, fontSize: "0.85rem", marginBottom: 16,
  },
  successBox: {
    backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534",
    padding: "10px 14px", borderRadius: 8, fontSize: "0.9rem", marginBottom: 16,
  },
  dropzone: {
    border: "2px dashed #d1d5db", borderRadius: 12, padding: "48px 24px",
    textAlign: "center", backgroundColor: "white", marginTop: 24,
  },
  dropzoneActive: { borderColor: "#2563eb", backgroundColor: "#eff6ff" },
  dropzoneText: { fontSize: "1rem", color: "#374151", fontWeight: 500 },
  dropzoneOr: { color: "#9ca3af", fontSize: "0.85rem", margin: "10px 0" },
  chooseBtn: {
    display: "inline-block", padding: "8px 18px", borderRadius: 8, backgroundColor: "#0f172a",
    color: "white", fontSize: "0.85rem", cursor: "pointer", fontWeight: 600,
  },
  busyText: { color: "#6b7280", fontSize: "0.85rem", marginTop: 16 },
  summaryBox: {
    backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 8,
    padding: "12px 16px", fontSize: "0.88rem", color: "#374151", marginBottom: 10,
  },
  mappingTable: { backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10, overflow: "hidden" },
  mappingHeaderRow: {
    display: "grid", gridTemplateColumns: "1fr 1fr", padding: "8px 16px",
    backgroundColor: "#f9fafb", fontSize: "0.72rem", fontWeight: 700, color: "#6b7280",
    textTransform: "uppercase", letterSpacing: "0.03em",
  },
  mappingRow: {
    display: "grid", gridTemplateColumns: "1fr 1fr", padding: "8px 16px",
    alignItems: "center", borderTop: "1px solid #f3f4f6",
  },
  mappingFieldLabel: { fontSize: "0.85rem", color: "#111827" },
  requiredMark: { color: "#dc2626" },
  mappingSelect: { padding: "6px 10px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: "0.83rem" },
  mappingSelectMissing: { borderColor: "#fca5a5", backgroundColor: "#fef2f2" },
  warningText: { color: "#991b1b", fontSize: "0.82rem", marginTop: 10 },
  previewTableWrap: { overflowX: "auto", backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 10 },
  previewTable: { borderCollapse: "collapse", fontSize: "0.78rem", width: "100%" },
  previewTh: {
    padding: "8px 12px", backgroundColor: "#f9fafb", borderBottom: "1px solid #e5e7eb",
    textAlign: "left", whiteSpace: "nowrap", color: "#4b5563",
  },
  previewTd: { padding: "8px 12px", borderBottom: "1px solid #f3f4f6", whiteSpace: "nowrap" },
  actionRow: { display: "flex", gap: 10, marginTop: 24 },
  primaryBtn: {
    padding: "10px 20px", borderRadius: 8, border: "none", backgroundColor: "#0f172a",
    color: "white", fontSize: "0.88rem", fontWeight: 600, cursor: "pointer",
  },
  secondaryBtn: {
    padding: "10px 20px", borderRadius: 8, border: "1px solid #d1d5db", backgroundColor: "white",
    color: "#374151", fontSize: "0.88rem", cursor: "pointer",
  },
  btnDisabled: { opacity: 0.4, cursor: "not-allowed" },
  qualityGrid: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 },
  qualityCard: { backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: 8, padding: "12px 14px" },
  qualityLabel: { fontSize: "0.75rem", color: "#6b7280" },
  qualityValue: { fontSize: "1.3rem", fontWeight: 700, marginTop: 2 },
};
