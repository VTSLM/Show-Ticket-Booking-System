"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { organizerVerificationApi } from "@/lib/api";
import {
  validatePan,
  validateGstin,
  validateIfsc,
} from "@/lib/identity-validators";
import { BusinessType, DocumentType } from "@/lib/verification-types";

// ─── constants ────────────────────────────────────────────────────────────────

const INDIAN_STATES = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
  "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka",
  "Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram",
  "Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu",
  "Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
  "Delhi","Jammu and Kashmir","Ladakh","Puducherry","Chandigarh",
];

const STEPS = [
  { id: 1, label: "Business Info" },
  { id: 2, label: "Identity" },
  { id: 3, label: "Bank & Payout" },
  { id: 4, label: "Documents" },
  { id: 5, label: "Review & Submit" },
];

function statusBadge(status: string) {
  if (status === "APPROVED")
    return "bg-emerald-900/60 text-emerald-300 border border-emerald-600/50";
  if (status === "SUBMITTED")
    return "bg-blue-900/60 text-blue-300 border border-blue-600/50";
  if (status === "CHANGES_REQUESTED")
    return "bg-amber-900/60 text-amber-300 border border-amber-600/50";
  return "bg-slate-700/60 text-slate-300 border border-slate-600/50";
}

// ─── component ────────────────────────────────────────────────────────────────

export default function OrganizerVerificationPage() {
  const { profile, loading: authLoading } = useAuth();
  const router = useRouter();

  // list
  const [applications, setApplications] = useState<any[]>([]);
  const [listLoading, setListLoading] = useState(true);

  // form identity
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(1);

  // step 1 — business info
  const [legalName, setLegalName] = useState("");
  const [businessType, setBusinessType] = useState<BusinessType>("INDIVIDUAL");
  const [stateName, setStateName] = useState("");

  // step 2 — identity
  const [pan, setPan] = useState("");
  const [gstin, setGstin] = useState("");

  // step 3 — bank
  const [bankHolderName, setBankHolderName] = useState("");
  const [ifsc, setIfsc] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [confirmAccountNumber, setConfirmAccountNumber] = useState("");

  // async flags
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);

  // ── load list ──────────────────────────────────────────────────────────────

  const loadApplications = useCallback(async () => {
    try {
      setListLoading(true);
      const data = await organizerVerificationApi.myApplications();
      setApplications(data || []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load applications");
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !profile) { router.push("/auth/login"); return; }
    if (!authLoading && profile) loadApplications();
  }, [profile, authLoading, loadApplications, router]);

  // ── current app object ────────────────────────────────────────────────────

  const currentApp = useMemo(
    () => applications.find((a) => a.id === selectedAppId),
    [applications, selectedAppId]
  );

  // ── required docs ─────────────────────────────────────────────────────────

  const requiredDocTypes: DocumentType[] = useMemo(() => {
    if (businessType === "COMPANY" || businessType === "LLP")
      return ["PAN", "GST_CERTIFICATE", "BANK_PROOF", "BUSINESS_REGISTRATION"];
    if (businessType === "TRUST")
      return ["PAN", "BANK_PROOF", "BUSINESS_REGISTRATION"];
    return ["PAN", "BANK_PROOF"];
  }, [businessType]);

  // ── A-02 real-time validators ─────────────────────────────────────────────

  const panValidation = useMemo(() => {
    if (!pan || pan.includes("*")) return null;
    return validatePan(pan, businessType);
  }, [pan, businessType]);

  const gstinValidation = useMemo(() => {
    if (!gstin || gstin.includes("*")) return null;
    return validateGstin(gstin, pan.includes("*") ? null : pan);
  }, [gstin, pan]);

  const ifscValidation = useMemo(() => {
    if (!ifsc) return null;
    return validateIfsc(ifsc);
  }, [ifsc]);

  // ── populate form ──────────────────────────────────────────────────────────

  const populateForm = (app: any) => {
    setSelectedAppId(app.id);
    setLegalName(app.legal_name || "");
    setBusinessType(app.business_type || "INDIVIDUAL");
    setStateName(app.state || "");
    setPan(app.pan_masked || "");
    setGstin(app.gstin_masked || "");
    if (app.bank_account) {
      setBankHolderName(app.bank_account.holder_name || "");
      setIfsc(app.bank_account.ifsc || "");
      setAccountNumber(app.bank_account.account_masked || "");
      setConfirmAccountNumber(app.bank_account.account_masked || "");
    } else {
      setBankHolderName(""); setIfsc(""); setAccountNumber(""); setConfirmAccountNumber("");
    }
    setCurrentStep(1);
  };

  const startNewApplication = () => {
    setSelectedAppId(null);
    setLegalName(""); setBusinessType("INDIVIDUAL"); setStateName("");
    setPan(""); setGstin("");
    setBankHolderName(""); setIfsc(""); setAccountNumber(""); setConfirmAccountNumber("");
    setCurrentStep(1);
    toast.success("Ready to create a new application");
  };

  // ── save draft ─────────────────────────────────────────────────────────────

  const handleSaveDraft = async () => {
    if (!legalName.trim()) { toast.error("Please enter a legal business name"); return; }
    if (accountNumber && confirmAccountNumber && accountNumber !== confirmAccountNumber) {
      toast.error("Bank account numbers do not match"); return;
    }

    setIsSavingDraft(true);
    try {
      const payload: any = {
        legal_name: legalName.trim(),
        business_type: businessType,
        state: stateName || null,
      };
      if (pan && !pan.includes("*")) payload.pan = pan.trim().toUpperCase();
      if (gstin && !gstin.includes("*")) payload.gstin = gstin.trim().toUpperCase();
      if (bankHolderName) payload.bank_holder_name = bankHolderName.trim();
      if (ifsc) payload.ifsc = ifsc.trim().toUpperCase();
      if (accountNumber && !accountNumber.includes("*")) payload.account_number = accountNumber.trim();

      const saved = await organizerVerificationApi.saveDraft(payload);
      toast.success("Draft saved!");
      await loadApplications();
      if (saved?.id) setSelectedAppId(saved.id);
    } catch (err: any) {
      toast.error(err.message || "Failed to save draft");
    } finally {
      setIsSavingDraft(false);
    }
  };

  // ── document upload ───────────────────────────────────────────────────────

  const handleFileUpload = async (docType: string, file: File) => {
    if (!selectedAppId) {
      toast.error("Save your draft first before uploading documents"); return;
    }
    setUploadingDocType(docType);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", docType);
      fd.append("case_type", "ORGANIZER");
      await organizerVerificationApi.uploadDocument(selectedAppId, fd);
      toast.success(`${docType.replace(/_/g, " ")} uploaded!`);
      await loadApplications();
    } catch (err: any) {
      toast.error(err.message || "Upload failed");
    } finally {
      setUploadingDocType(null);
    }
  };

  const handleViewDocument = async (documentId: string) => {
    try {
      const data = await organizerVerificationApi.getViewUrl(documentId);
      if (data?.signed_url) window.open(data.signed_url, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      toast.error(err.message || "Could not generate view link");
    }
  };

  // ── submit ────────────────────────────────────────────────────────────────

  const handleSubmitForReview = async (appId?: string) => {
    const targetId = appId || selectedAppId;
    if (!targetId) { toast.error("No application selected"); return; }
    setIsSubmitting(true);
    try {
      await organizerVerificationApi.submit(targetId);
      toast.success("Application submitted for review!");
      await loadApplications();
    } catch (err: any) {
      toast.error(err.message || "Failed to submit");
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── step navigation ───────────────────────────────────────────────────────

  const goNext = async () => {
    if (currentStep === 1) {
      if (!legalName.trim()) { toast.error("Legal business name is required"); return; }
      if (!stateName) { toast.error("Please select a state"); return; }
    }
    if (currentStep === 2) {
      if (panValidation && !panValidation.isValid) { toast.error("Fix PAN errors before continuing"); return; }
      if (gstinValidation && !gstinValidation.isValid) { toast.error("Fix GSTIN errors before continuing"); return; }
    }
    if (currentStep === 3) {
      if (ifscValidation && !ifscValidation.isValid) { toast.error("Fix IFSC errors before continuing"); return; }
      if (accountNumber && confirmAccountNumber && accountNumber !== confirmAccountNumber) {
        toast.error("Account numbers do not match"); return;
      }
      // Auto-save draft when moving from step 3 → 4
      await handleSaveDraft();
    }
    setCurrentStep((s) => Math.min(s + 1, 5));
  };

  const goBack = () => setCurrentStep((s) => Math.max(s - 1, 1));

  // ── render helpers ─────────────────────────────────────────────────────────

  const inputCls = (error?: boolean) =>
    `w-full bg-[#070d1d] border ${
      error ? "border-red-500" : "border-blue-900/70"
    } text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500`;

  const labelCls = "block text-xs font-semibold text-slate-300 mb-1";

  // ── render ────────────────────────────────────────────────────────────────

  if (authLoading) {
    return (
      <div className="min-h-screen bg-[#070c18] flex items-center justify-center">
        <p className="text-slate-400 text-sm">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#070c18] text-white px-4 sm:px-8 py-8">
      <div className="max-w-4xl mx-auto space-y-8">

        {/* ── Page header ── */}
        <div>
          <p className="text-xs font-bold tracking-widest text-sky-400 uppercase">
            ORGANIZER WORKSPACE
          </p>
          <h1 className="text-3xl font-extrabold text-white mt-1">
            Organizer verification
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Add organizer business identity, attach verified documents, and submit for review.
          </p>
        </div>

        {/* ── Wizard card ── */}
        <div className="bg-[#0b1328] border border-blue-900/60 rounded-2xl shadow-xl overflow-hidden">

          {/* Card header */}
          <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-blue-900/40">
            <div>
              <h2 className="text-lg font-bold text-white">
                {selectedAppId ? "Edit organizer application" : "New organizer application"}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Fill in the organizer business details and attach the required proof before submitting.
              </p>
            </div>
            {selectedAppId && (
              <button
                type="button"
                onClick={startNewApplication}
                className="ml-4 shrink-0 px-3 py-1.5 rounded-lg border border-slate-600 hover:border-slate-400 text-xs text-slate-200 transition-colors"
              >
                Start a new application
              </button>
            )}
          </div>

          {/* Step progress bar */}
          <div className="px-6 pt-5 pb-2">
            <div className="flex items-center gap-0">
              {STEPS.map((step, idx) => {
                const done = currentStep > step.id;
                const active = currentStep === step.id;
                return (
                  <div key={step.id} className="flex items-center flex-1">
                    <div className="flex flex-col items-center gap-1 min-w-[52px]">
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${
                          done
                            ? "bg-blue-600 border-blue-600 text-white"
                            : active
                            ? "bg-transparent border-blue-500 text-blue-400"
                            : "bg-transparent border-slate-700 text-slate-600"
                        }`}
                      >
                        {done ? (
                          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414L8.414 15l-5.121-5.121a1 1 0 011.414-1.414L8.414 12.172l6.879-6.879a1 1 0 011.414 0z" clipRule="evenodd"/>
                          </svg>
                        ) : step.id}
                      </div>
                      <span
                        className={`text-[10px] font-medium whitespace-nowrap ${
                          active ? "text-blue-400" : done ? "text-slate-300" : "text-slate-600"
                        }`}
                      >
                        {step.label}
                      </span>
                    </div>
                    {idx < STEPS.length - 1 && (
                      <div
                        className={`flex-1 h-px mx-1 mt-[-12px] transition-all ${
                          done ? "bg-blue-600" : "bg-slate-700"
                        }`}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Step content ── */}
          <div className="px-6 py-6 space-y-5">

            {/* STEP 1 — Business Info */}
            {currentStep === 1 && (
              <div className="space-y-4">
                <div>
                  <label className={labelCls}>
                    Legal business name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Skyline Entertainment Pvt Ltd"
                    value={legalName}
                    onChange={(e) => setLegalName(e.target.value)}
                    className={inputCls()}
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className={labelCls}>
                      Business type <span className="text-red-400">*</span>
                    </label>
                    <select
                      value={businessType}
                      onChange={(e) => setBusinessType(e.target.value as BusinessType)}
                      className={inputCls()}
                    >
                      <option value="INDIVIDUAL">INDIVIDUAL (Person)</option>
                      <option value="SOLE_PROPRIETOR">SOLE PROPRIETOR</option>
                      <option value="COMPANY">COMPANY (Private / Public Ltd)</option>
                      <option value="LLP">LLP (Limited Liability Partnership)</option>
                      <option value="TRUST">TRUST / Non-Profit</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelCls}>
                      Operating state <span className="text-red-400">*</span>
                    </label>
                    <select
                      value={stateName}
                      onChange={(e) => setStateName(e.target.value)}
                      className={inputCls()}
                    >
                      <option value="">Select state / union territory</option>
                      {INDIAN_STATES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* STEP 2 — Identity */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div>
                  <label className={labelCls}>
                    PAN (Permanent Account Number) <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    maxLength={10}
                    placeholder="e.g. AAACC1122C"
                    value={pan}
                    onChange={(e) => setPan(e.target.value.toUpperCase())}
                    className={`${inputCls(!!panValidation && !panValidation.isValid)} font-mono`}
                  />
                  {panValidation && !panValidation.isValid && (
                    <p className="text-[11px] text-red-400 mt-1">{panValidation.errorMessage}</p>
                  )}
                  {panValidation && panValidation.isValid && (
                    <p className="text-[11px] text-emerald-400 mt-1">✓ PAN looks valid</p>
                  )}
                </div>

                <div>
                  <label className={labelCls}>
                    GSTIN{" "}
                    {businessType === "COMPANY" || businessType === "LLP" ? (
                      <span className="text-red-400">*</span>
                    ) : (
                      <span className="text-slate-500 font-normal">(optional)</span>
                    )}
                  </label>
                  <input
                    type="text"
                    maxLength={15}
                    placeholder="e.g. 27AAACC1122C1Z5"
                    value={gstin}
                    onChange={(e) => setGstin(e.target.value.toUpperCase())}
                    className={`${inputCls(!!gstinValidation && !gstinValidation.isValid)} font-mono`}
                  />
                  {gstinValidation && !gstinValidation.isValid && (
                    <p className="text-[11px] text-red-400 mt-1">{gstinValidation.errorMessage}</p>
                  )}
                  {gstinValidation && gstinValidation.isValid && (
                    <p className="text-[11px] text-emerald-400 mt-1">✓ GSTIN looks valid</p>
                  )}
                </div>
              </div>
            )}

            {/* STEP 3 — Bank & Payout */}
            {currentStep === 3 && (
              <div className="space-y-4">
                <p className="text-xs font-bold text-sky-400 uppercase tracking-wider">
                  Settlement Bank Account
                </p>

                <div>
                  <label className={labelCls}>
                    Account holder name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    placeholder="Name as per bank records"
                    value={bankHolderName}
                    onChange={(e) => setBankHolderName(e.target.value)}
                    className={inputCls()}
                  />
                </div>

                <div>
                  <label className={labelCls}>
                    IFSC code <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    maxLength={11}
                    placeholder="e.g. HDFC0001234"
                    value={ifsc}
                    onChange={(e) => setIfsc(e.target.value.toUpperCase())}
                    className={`${inputCls(!!ifscValidation && !ifscValidation.isValid)} font-mono`}
                  />
                  {ifscValidation && !ifscValidation.isValid && (
                    <p className="text-[11px] text-red-400 mt-1">{ifscValidation.errorMessage}</p>
                  )}
                  {ifscValidation && ifscValidation.isValid && (
                    <p className="text-[11px] text-emerald-400 mt-1">✓ IFSC looks valid</p>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className={labelCls}>
                      Account number <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      placeholder="Enter account number"
                      value={accountNumber}
                      onChange={(e) => setAccountNumber(e.target.value)}
                      className={`${inputCls()} font-mono`}
                    />
                  </div>
                  <div>
                    <label className={labelCls}>
                      Confirm account number <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="password"
                      placeholder="Re-enter account number"
                      value={confirmAccountNumber}
                      onChange={(e) => setConfirmAccountNumber(e.target.value)}
                      className={`${inputCls(
                        !!(accountNumber && confirmAccountNumber && accountNumber !== confirmAccountNumber)
                      )} font-mono`}
                    />
                    {accountNumber && confirmAccountNumber && accountNumber !== confirmAccountNumber && (
                      <p className="text-[11px] text-red-400 mt-1">Account numbers do not match</p>
                    )}
                  </div>
                </div>

                {/* Inline save-draft button for step 3 */}
                <div className="pt-1">
                  <button
                    type="button"
                    disabled={isSavingDraft}
                    onClick={handleSaveDraft}
                    className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-5 py-2 rounded-lg text-sm shadow transition-colors"
                  >
                    {isSavingDraft ? "Saving…" : selectedAppId ? "Update draft" : "Save draft"}
                  </button>
                </div>
              </div>
            )}

            {/* STEP 4 — Documents */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-bold text-sky-400 uppercase tracking-wider">
                    Required verification documents
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Upload verified PDFs or images (max 10 MB). Each upload creates an immutable revision.
                  </p>
                </div>

                {!selectedAppId ? (
                  <div className="bg-[#070d1d] border border-blue-900/40 rounded-xl p-6 text-center text-xs text-slate-400">
                    Please save your draft first (go back to step 3) before attaching documents.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {requiredDocTypes.map((dtype) => {
                      const uploadedDocs = (currentApp?.documents || []).filter(
                        (d: any) => d.doc_type === dtype
                      );
                      const latestDoc = uploadedDocs[0];

                      return (
                        <div
                          key={dtype}
                          className="bg-[#070d1d] border border-blue-900/60 rounded-xl p-4 space-y-2.5"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-white">
                              {dtype.replace(/_/g, " ")}
                            </span>
                            {latestDoc ? (
                              <span className="bg-blue-900/60 text-blue-300 border border-blue-700/50 text-[10px] px-2 py-0.5 rounded-full font-medium">
                                Version {latestDoc.version}
                              </span>
                            ) : (
                              <span className="text-[10px] text-amber-400 font-medium">Required</span>
                            )}
                          </div>

                          <input
                            type="file"
                            accept=".pdf,.jpg,.jpeg,.png"
                            disabled={uploadingDocType === dtype}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(dtype, file);
                            }}
                            className="text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-900/50 file:text-blue-300 hover:file:bg-blue-900/80 cursor-pointer w-full"
                          />

                          {uploadingDocType === dtype && (
                            <p className="text-[11px] text-sky-400 animate-pulse">
                              Uploading to secure vault…
                            </p>
                          )}

                          {latestDoc && (
                            <div className="flex items-center justify-between pt-1 text-[11px]">
                              <span className="text-slate-400">
                                {latestDoc.doc_number_masked || "Document on file"}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleViewDocument(latestDoc.id)}
                                className="text-sky-400 hover:underline font-medium"
                              >
                                View →
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* STEP 5 — Review & Submit */}
            {currentStep === 5 && (
              <div className="space-y-5">
                <p className="text-xs font-bold text-sky-400 uppercase tracking-wider">
                  Review & submit
                </p>

                {/* Summary rows */}
                <div className="bg-[#070d1d] border border-blue-900/40 rounded-xl divide-y divide-blue-900/30">
                  {[
                    ["Legal name", legalName || "—"],
                    ["Business type", businessType],
                    ["State", stateName || "—"],
                    ["PAN", pan || "—"],
                    ["GSTIN", gstin || "—"],
                    ["Account holder", bankHolderName || "—"],
                    ["IFSC", ifsc || "—"],
                    ["Account number", accountNumber ? "••••" + accountNumber.slice(-4) : "—"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between px-4 py-2.5 text-sm">
                      <span className="text-slate-400 text-xs">{k}</span>
                      <span className="text-white font-medium font-mono text-xs">{v}</span>
                    </div>
                  ))}
                </div>

                {/* Documents checklist */}
                <div>
                  <p className="text-xs font-semibold text-slate-300 mb-2">Documents</p>
                  <div className="space-y-1.5">
                    {requiredDocTypes.map((dtype) => {
                      const uploaded = (currentApp?.documents || []).some(
                        (d: any) => d.doc_type === dtype
                      );
                      return (
                        <div key={dtype} className="flex items-center gap-2 text-xs">
                          {uploaded ? (
                            <span className="w-4 h-4 rounded-full bg-emerald-500/20 border border-emerald-500 flex items-center justify-center text-emerald-400 text-[10px]">✓</span>
                          ) : (
                            <span className="w-4 h-4 rounded-full bg-red-500/10 border border-red-500 flex items-center justify-center text-red-400 text-[10px]">✗</span>
                          )}
                          <span className={uploaded ? "text-slate-300" : "text-red-400"}>
                            {dtype.replace(/_/g, " ")}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Submit button */}
                {selectedAppId &&
                  (currentApp?.verification_status === "DRAFT" ||
                    currentApp?.verification_status === "CHANGES_REQUESTED") && (
                    <button
                      type="button"
                      disabled={isSubmitting}
                      onClick={() => handleSubmitForReview()}
                      className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-lg text-sm shadow transition-colors"
                    >
                      {isSubmitting ? "Submitting…" : "Submit for review"}
                    </button>
                  )}

                {currentApp?.verification_status === "SUBMITTED" && (
                  <div className="rounded-xl bg-blue-900/20 border border-blue-700/40 p-4 text-sm text-blue-200 text-center">
                    ✅ This application has been submitted and is under review.
                  </div>
                )}
              </div>
            )}

            {/* ── Navigation buttons ── */}
            <div className="pt-4 border-t border-blue-900/30 flex items-center justify-between">
              <button
                type="button"
                onClick={goBack}
                disabled={currentStep === 1}
                className="px-4 py-2 rounded-lg border border-slate-700 hover:border-slate-500 text-xs text-slate-300 disabled:opacity-30 transition-colors"
              >
                ← Back
              </button>

              {currentStep < 5 ? (
                <button
                  type="button"
                  onClick={goNext}
                  disabled={isSavingDraft}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-5 py-2 rounded-lg text-sm shadow transition-colors"
                >
                  {isSavingDraft ? "Saving…" : "Next →"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSaveDraft}
                  disabled={isSavingDraft}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-5 py-2 rounded-lg text-sm shadow transition-colors"
                >
                  {isSavingDraft ? "Saving…" : "Save changes"}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── Your applications ── */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white">Your applications</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                {applications.length} application{applications.length === 1 ? "" : "s"}
              </p>
            </div>
            <button
              type="button"
              onClick={loadApplications}
              disabled={listLoading}
              className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800/40 hover:bg-slate-800 text-xs text-slate-300 transition-colors"
            >
              {listLoading ? "Refreshing…" : "Refresh"}
            </button>
          </div>

          {applications.length === 0 ? (
            <div className="bg-[#0b1328] border border-blue-900/50 rounded-xl p-8 text-center text-sm text-slate-400">
              No verification applications yet. Complete the form above to begin.
            </div>
          ) : (
            <div className="space-y-3">
              {applications.map((app) => (
                <div
                  key={app.id}
                  className="bg-[#0b1328] border border-blue-900/60 rounded-xl p-5 hover:border-blue-700/60 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h3 className="text-base font-bold text-white">{app.legal_name}</h3>
                      <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${statusBadge(app.verification_status)}`}>
                        {app.verification_status}
                      </span>
                      {app.trust_tier && (
                        <span className="bg-indigo-900/50 text-indigo-300 border border-indigo-700/50 text-xs px-2.5 py-0.5 rounded-full">
                          {app.trust_tier}
                        </span>
                      )}
                      {/* doc version count */}
                      {(app.documents || []).length > 0 && (
                        <span className="text-[10px] text-slate-500">
                          Version {Math.max(...(app.documents || []).map((d: any) => d.version || 1))}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400">
                      {app.business_type} · {app.state || "No state"} · PAN: {app.pan_masked || "N/A"}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      {(app.documents || []).length} doc{(app.documents || []).length === 1 ? "" : "s"} attached · Updated{" "}
                      {new Date(app.updated_at).toLocaleDateString()}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                    <button
                      type="button"
                      onClick={() => populateForm(app)}
                      className="px-3 py-1.5 rounded-lg border border-slate-600 hover:border-slate-400 text-xs text-slate-200 transition-colors"
                    >
                      Edit
                    </button>
                    {(app.verification_status === "DRAFT" || app.verification_status === "CHANGES_REQUESTED") && (
                      <button
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => handleSubmitForReview(app.id)}
                        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-4 py-1.5 rounded-lg text-xs transition-colors"
                      >
                        {isSubmitting ? "Submitting…" : "Submit for review"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
