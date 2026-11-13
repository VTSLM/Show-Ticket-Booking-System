"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { organizerAdminApi } from "@/lib/api";

export default function AdminOrganizerReviewPage() {
  const { user, isAdmin, loading: authLoading } = useAuth();
  const router = useRouter();

  const [queue, setQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Review decision states
  const [decisionModal, setDecisionModal] = useState<{
    open: boolean;
    type: "APPROVED" | "REJECTED" | "CHANGES_REQUESTED" | null;
  }>({ open: false, type: null });
  const [decisionComment, setDecisionComment] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  // Document comment state
  const [docCommentModal, setDocCommentModal] = useState<{
    open: boolean;
    docId: string | null;
    docType: string | null;
    status: "REJECTED" | "CHANGES_REQUESTED" | null;
  }>({ open: false, docId: null, docType: null, status: null });
  const [docComment, setDocComment] = useState("");

  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.push("/");
      return;
    }
    if (!authLoading && isAdmin) {
      loadQueue();
    }
  }, [authLoading, isAdmin]);

  const loadQueue = async () => {
    try {
      setLoading(true);
      const res = await organizerAdminApi.getReviewQueue();
      setQueue(res.cases || []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load review queue");
    } finally {
      setLoading(false);
    }
  };

  const loadCaseDetail = async (caseId: string) => {
    try {
      setDetailLoading(true);
      setSelectedCaseId(caseId);
      const res = await organizerAdminApi.getWorkspace(caseId);
      setCaseDetail(res);
    } catch (err: any) {
      toast.error(err.message || "Failed to load case details");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleClaim = async (caseId: string) => {
    try {
      setActionLoading(true);
      await organizerAdminApi.claimCase(caseId);
      toast.success("Case claimed! Review workspace unlocked.");
      await loadQueue();
      await loadCaseDetail(caseId);
    } catch (err: any) {
      toast.error(err.message || "Could not claim case");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRelease = async (caseId: string) => {
    try {
      setActionLoading(true);
      await organizerAdminApi.releaseCase(caseId);
      toast.success("Case released back to queue");
      await loadQueue();
      if (selectedCaseId === caseId) {
        await loadCaseDetail(caseId);
      }
    } catch (err: any) {
      toast.error(err.message || "Could not release case");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDocumentReview = async (
    docId: string,
    status: "APPROVED" | "REJECTED" | "CHANGES_REQUESTED",
    comment?: string
  ) => {
    try {
      setActionLoading(true);
      await organizerAdminApi.reviewDocument(docId, status, comment);
      toast.success(`Document status updated to ${status}`);
      if (selectedCaseId) {
        await loadCaseDetail(selectedCaseId);
      }
      setDocCommentModal({ open: false, docId: null, docType: null, status: null });
      setDocComment("");
    } catch (err: any) {
      toast.error(err.message || "Failed to update document status");
    } finally {
      setActionLoading(false);
    }
  };

  const submitDecision = async () => {
    if (!selectedCaseId || !decisionModal.type) return;

    if (decisionModal.type === "REJECTED" && !decisionComment.trim()) {
      toast.error("Rejection reason is required.");
      return;
    }
    if (decisionModal.type === "CHANGES_REQUESTED" && !decisionComment.trim()) {
      toast.error("Feedback instructions are required when requesting changes.");
      return;
    }

    try {
      setActionLoading(true);
      await organizerAdminApi.makeDecision(
        selectedCaseId,
        decisionModal.type,
        decisionComment,
        decisionModal.type === "REJECTED" ? decisionComment : undefined
      );
      toast.success(`Application decision '${decisionModal.type}' recorded!`);
      setDecisionModal({ open: false, type: null });
      setDecisionComment("");
      await loadQueue();
      await loadCaseDetail(selectedCaseId);
    } catch (err: any) {
      toast.error(err.message || "Failed to record decision");
    } finally {
      setActionLoading(false);
    }
  };

  if (authLoading || loading) {
    return (
      <main className="min-h-screen bg-[#070c18] text-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <p className="text-sm text-gray-400">Loading administrator review workspace...</p>
        </div>
      </main>
    );
  }

  const isCaseClaimedByMe =
    caseDetail?.organizer?.reviewer_id &&
    caseDetail.organizer.reviewer_id === user?.uid;

  const isClaimedBySomeoneElse =
    caseDetail?.organizer?.reviewer_id &&
    caseDetail.organizer.reviewer_id !== user?.uid &&
    new Date(caseDetail.organizer.claim_expires_at) > new Date();

  return (
    <main className="min-h-screen bg-[#070c18] text-white px-4 py-8 sm:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header matching Venue Review */}
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <div className="text-xs font-semibold tracking-wider text-blue-400 uppercase">
              Administrator Workspace
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white mt-1">
              Organizer review
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Claim a case before reviewing it. A claim is required to make a decision.
            </p>
          </div>
          <button
            onClick={loadQueue}
            className="self-start sm:self-auto px-4 py-2 text-xs font-medium bg-[#101a2d] hover:bg-[#16243d] border border-white/10 rounded-lg text-gray-200 transition-colors"
          >
            Refresh queue
          </button>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Review Queue (4 cols) */}
          <section className="lg:col-span-4 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-200">Review queue</h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                {queue.length} cases
              </span>
            </div>

            {queue.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 bg-[#0a1222] p-8 text-center space-y-2">
                <div className="text-sm font-semibold text-gray-300">Queue is clear</div>
                <p className="text-xs text-gray-400">
                  Submitted organizer applications will appear here.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {queue.map((c) => {
                  const isSelected = selectedCaseId === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => loadCaseDetail(c.id)}
                      className={`cursor-pointer rounded-2xl border p-4 transition-all ${
                        isSelected
                          ? "bg-[#14233f] border-blue-500 shadow-[0_0_15px_rgba(40,124,255,0.2)]"
                          : "bg-[#0b1426] border-white/10 hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="font-semibold text-sm text-white">
                            {c.legal_name}
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">
                            {c.business_type} • {c.state || "India"}
                          </div>
                          <div className="text-[11px] text-gray-400 mt-1">
                            Applicant: {c.applicant_name} ({c.applicant_email})
                          </div>
                        </div>
                        <span
                          className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                            c.verification_status === "IN_REVIEW"
                              ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                              : c.verification_status === "CHANGES_REQUESTED"
                              ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                              : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                          }`}
                        >
                          {c.verification_status}
                        </span>
                      </div>

                      {c.reviewer_name && (
                        <div className="mt-3 pt-2 border-t border-white/5 flex items-center justify-between text-[11px] text-gray-400">
                          <span>Claimed by: {c.reviewer_name}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Right Column: Case Workspace (8 cols) */}
          <section className="lg:col-span-8">
            {!selectedCaseId ? (
              <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-12 text-center space-y-3">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10 text-blue-400">
                  <svg
                    className="h-6 w-6"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth="2"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div className="text-base font-semibold text-white">No case selected</div>
                <p className="text-xs text-gray-400 max-w-sm mx-auto">
                  Select a case from the queue on the left and claim it to open the review
                  workspace.
                </p>
              </div>
            ) : detailLoading ? (
              <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-12 text-center text-gray-400 text-sm">
                Loading case details...
              </div>
            ) : !caseDetail ? null : (
              <div className="space-y-6">
                {/* Case Top Bar with Claim / Release Controls */}
                <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-white">
                      {caseDetail.organizer.legal_name}
                    </h2>
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                      <span>Status: {caseDetail.organizer.verification_status}</span>
                      <span>•</span>
                      <span>Tier: {caseDetail.organizer.trust_tier}</span>
                      <span>•</span>
                      <span>ID: {caseDetail.organizer.id.slice(0, 8)}...</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {caseDetail.organizer.reviewer_id ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">
                          Claimed by {caseDetail.organizer.reviewer_name || "Reviewer"}
                        </span>
                        <button
                          onClick={() => handleRelease(selectedCaseId)}
                          disabled={actionLoading}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 transition-colors"
                        >
                          Release claim
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleClaim(selectedCaseId)}
                        disabled={actionLoading}
                        className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white shadow-md transition-colors"
                      >
                        Claim case to review
                      </button>
                    )}
                  </div>
                </div>

                {/* Risk Assessment Report */}
                {caseDetail.risk_assessment && (
                  <div
                    className={`rounded-2xl border p-5 ${
                      caseDetail.risk_assessment.risk_level === "HIGH"
                        ? "bg-red-950/20 border-red-500/30"
                        : caseDetail.risk_assessment.risk_level === "MEDIUM"
                        ? "bg-amber-950/20 border-amber-500/30"
                        : "bg-emerald-950/20 border-emerald-500/30"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider text-gray-300">
                          Automated Risk Assessment
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                            caseDetail.risk_assessment.risk_level === "HIGH"
                              ? "bg-red-500 text-white"
                              : caseDetail.risk_assessment.risk_level === "MEDIUM"
                              ? "bg-amber-500 text-black"
                              : "bg-emerald-500 text-white"
                          }`}
                        >
                          {caseDetail.risk_assessment.risk_level} RISK (Score:{" "}
                          {caseDetail.risk_assessment.risk_score}/100)
                        </span>
                      </div>
                      <span className="text-xs text-gray-400">
                        {caseDetail.risk_assessment.flags_count} flag(s)
                      </span>
                    </div>

                    <p className="text-xs text-gray-300 mb-3">
                      {caseDetail.risk_assessment.recommendation}
                    </p>

                    {caseDetail.risk_assessment.flags.length > 0 && (
                      <div className="space-y-1.5 mt-2">
                        {caseDetail.risk_assessment.flags.map((f: any, idx: number) => (
                          <div
                            key={idx}
                            className="text-xs flex items-start gap-2 bg-black/20 p-2 rounded-lg"
                          >
                            <span className="font-mono text-red-400 font-bold">
                              [{f.severity}]
                            </span>
                            <span className="text-gray-200">{f.description}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Business & Bank Details Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Identity Card */}
                  <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-5 space-y-3">
                    <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">
                      Business Identity
                    </h3>
                    <div className="text-xs space-y-2">
                      <div className="flex justify-between py-1 border-b border-white/5">
                        <span className="text-gray-400">Legal Name</span>
                        <span className="font-medium text-white">
                          {caseDetail.organizer.legal_name}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-white/5">
                        <span className="text-gray-400">Business Type</span>
                        <span className="font-medium text-white">
                          {caseDetail.organizer.business_type}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-white/5">
                        <span className="text-gray-400">Operating State</span>
                        <span className="font-medium text-white">
                          {caseDetail.organizer.state || "Not provided"}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-white/5">
                        <span className="text-gray-400">Masked PAN</span>
                        <span className="font-mono text-blue-400 font-semibold">
                          {caseDetail.organizer.pan_masked || "None"}
                        </span>
                      </div>
                      <div className="flex justify-between py-1">
                        <span className="text-gray-400">Masked GSTIN</span>
                        <span className="font-mono text-blue-400 font-semibold">
                          {caseDetail.organizer.gstin_masked || "None"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Bank Account Card */}
                  <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">
                        Settlement Bank Account
                      </h3>
                      {caseDetail.bank_verification?.verified ? (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          Mock Verified
                        </span>
                      ) : (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          Unverified
                        </span>
                      )}
                    </div>

                    {caseDetail.bank_account ? (
                      <div className="text-xs space-y-2">
                        <div className="flex justify-between py-1 border-b border-white/5">
                          <span className="text-gray-400">Account Holder</span>
                          <span className="font-medium text-white">
                            {caseDetail.bank_account.holder_name}
                          </span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-white/5">
                          <span className="text-gray-400">IFSC Code</span>
                          <span className="font-mono text-white">
                            {caseDetail.bank_account.ifsc}
                          </span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-white/5">
                          <span className="text-gray-400">Masked Account</span>
                          <span className="font-mono text-blue-400 font-semibold">
                            {caseDetail.bank_account.account_masked}
                          </span>
                        </div>
                        {caseDetail.bank_verification?.bank_name && (
                          <div className="flex justify-between py-1">
                            <span className="text-gray-400">Detected Bank</span>
                            <span className="text-gray-200">
                              {caseDetail.bank_verification.bank_name}
                            </span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-gray-400">No bank account registered yet.</p>
                    )}
                  </div>
                </div>

                {/* Document Verification Checklist */}
                <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-5 space-y-4">
                  <h3 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">
                    Submitted Documents ({caseDetail.documents.length})
                  </h3>

                  {caseDetail.documents.length === 0 ? (
                    <p className="text-xs text-gray-400">No documents attached.</p>
                  ) : (
                    <div className="space-y-3">
                      {caseDetail.documents.map((doc: any) => (
                        <div
                          key={doc.id}
                          className="rounded-xl border border-white/5 bg-[#0e192f] p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-sm text-white">
                                {doc.doc_type}
                              </span>
                              <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                                Version {doc.version}
                              </span>
                              <span
                                className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                                  doc.review_status === "APPROVED"
                                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                    : doc.review_status === "REJECTED"
                                    ? "bg-red-500/20 text-red-300 border border-red-500/30"
                                    : doc.review_status === "CHANGES_REQUESTED"
                                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                    : "bg-gray-500/20 text-gray-300"
                                }`}
                              >
                                {doc.review_status}
                              </span>
                            </div>

                            <div className="text-xs text-gray-400">
                              Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}
                              {doc.issued_by && ` • Issued by: ${doc.issued_by}`}
                            </div>

                            {doc.reviewer_comment && (
                              <div className="text-xs text-amber-300 bg-amber-950/20 p-2 rounded border border-amber-500/20 mt-1">
                                Feedback: {doc.reviewer_comment}
                              </div>
                            )}
                          </div>

                          <div className="flex items-center gap-2 flex-wrap">
                            {doc.view_url && (
                              <a
                                href={doc.view_url}
                                target="_blank"
                                rel="noreferrer"
                                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600/30 hover:bg-blue-600/50 text-blue-200 border border-blue-500/30 transition-colors"
                              >
                                View File ↗
                              </a>
                            )}

                            {/* Reviewer controls for document */}
                            <button
                              onClick={() => handleDocumentReview(doc.id, "APPROVED")}
                              disabled={actionLoading}
                              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-200 border border-emerald-500/30 transition-colors"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() =>
                                setDocCommentModal({
                                  open: true,
                                  docId: doc.id,
                                  docType: doc.doc_type,
                                  status: "CHANGES_REQUESTED",
                                })
                              }
                              disabled={actionLoading}
                              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-amber-600/30 hover:bg-amber-600/50 text-amber-200 border border-amber-500/30 transition-colors"
                            >
                              Request Change
                            </button>
                            <button
                              onClick={() =>
                                setDocCommentModal({
                                  open: true,
                                  docId: doc.id,
                                  docType: doc.doc_type,
                                  status: "REJECTED",
                                })
                              }
                              disabled={actionLoading}
                              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600/30 hover:bg-red-600/50 text-red-200 border border-red-500/30 transition-colors"
                            >
                              Reject
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Overall Decision Action Bar */}
                <div className="rounded-2xl border border-white/10 bg-[#0b1426] p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Application Decision</h3>
                    <p className="text-xs text-gray-400">
                      Determine overall verification outcome for this organizer.
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() =>
                        setDecisionModal({ open: true, type: "CHANGES_REQUESTED" })
                      }
                      disabled={actionLoading}
                      className="px-4 py-2 text-xs font-semibold rounded-lg bg-amber-600 hover:bg-amber-500 text-black shadow transition-colors"
                    >
                      Request Changes
                    </button>
                    <button
                      onClick={() =>
                        setDecisionModal({ open: true, type: "REJECTED" })
                      }
                      disabled={actionLoading}
                      className="px-4 py-2 text-xs font-semibold rounded-lg bg-red-600 hover:bg-red-500 text-white shadow transition-colors"
                    >
                      Reject Application
                    </button>
                    <button
                      onClick={() =>
                        setDecisionModal({ open: true, type: "APPROVED" })
                      }
                      disabled={actionLoading}
                      className="px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow transition-colors"
                    >
                      Approve Organizer
                    </button>
                  </div>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>

      {/* Decision Modal */}
      {decisionModal.open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b1426] border border-white/10 rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">
              Confirm Decision: {decisionModal.type}
            </h3>
            <p className="text-xs text-gray-400">
              {decisionModal.type === "APPROVED"
                ? "This will verify the organizer, grant TIER_1 trust tier, and notify the applicant."
                : decisionModal.type === "REJECTED"
                ? "Provide a mandatory rejection reason detailing why this application was declined."
                : "Provide instructions for the applicant regarding which documents or fields need correction."}
            </p>

            <textarea
              rows={4}
              value={decisionComment}
              onChange={(e) => setDecisionComment(e.target.value)}
              placeholder="Enter feedback or mandatory justification..."
              className="w-full bg-[#050b14] border border-white/10 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-blue-500"
            />

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setDecisionModal({ open: false, type: null });
                  setDecisionComment("");
                }}
                className="px-4 py-2 text-xs text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={submitDecision}
                disabled={actionLoading}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white"
              >
                Confirm Decision
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Document Comment Modal */}
      {docCommentModal.open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b1426] border border-white/10 rounded-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">
              {docCommentModal.status === "REJECTED"
                ? "Reject Document"
                : "Request Changes on Document"}
            </h3>
            <p className="text-xs text-gray-400">
              Document: {docCommentModal.docType}. Please explain why this document is
              unacceptable or what needs correction.
            </p>

            <textarea
              rows={3}
              value={docComment}
              onChange={(e) => setDocComment(e.target.value)}
              placeholder="e.g. Blurry photo, expired certificate, name mismatch..."
              className="w-full bg-[#050b14] border border-white/10 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-blue-500"
            />

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setDocCommentModal({ open: false, docId: null, docType: null, status: null });
                  setDocComment("");
                }}
                className="px-4 py-2 text-xs text-gray-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (docCommentModal.docId && docCommentModal.status) {
                    handleDocumentReview(
                      docCommentModal.docId,
                      docCommentModal.status,
                      docComment
                    );
                  }
                }}
                disabled={actionLoading}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white"
              >
                Save Review
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

