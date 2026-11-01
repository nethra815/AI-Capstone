// DEV ONLY. Loaded through a dynamic import guarded by import.meta.env.DEV, so it is not in production builds.
// The live pipeline currently keeps 0 circular amendments, so it never returns "conflict". This fixture follows the
// real AskResult shape (and cites real passage ids) so the "Policy changed" view can be checked. Type "dev:conflict".
import type { AskResult } from "../api";

export function conflictFixture(asOf: string): AskResult {
  const arh = {
    chunk_id: "SPIT_ACAD_ARH_2026_27_01_013",
    doc_id: "SPIT/ACAD/ARH/2026-27/01",
    title: "Sardar Patel Institute of Technology (SPIT)",
    version: "3.0",
    section: "4. Attendance Regulations",
    clauses: ["4", "4.5"],
    pages: [2],
    published_on: "2026-06-27",
    effective_from: "2026-08-03",
  };
  const cir = {
    chunk_id: "SPIT_ACAD_CIR_2026_27_03_004",
    doc_id: "SPIT/ACAD/CIR/2026-27/03",
    title: "Sardar Patel Institute of Technology (SPIT)",
    version: "?",
    section: "3. Amendments Summary Table",
    clauses: ["3"],
    pages: [1],
    published_on: "2026-10-12",
    effective_from: "2026-10-12",
  };
  const text = "The attendance condonation fee is ₹750 per course.";
  return {
    question: "dev:conflict",
    mode: "evidence_aware",
    as_of: asOf,
    batch: null,
    language: "en",
    search_text: "attendance condonation fee per course",
    spell_fixes: [],
    notices: [],
    conflicts: [
      {
        older_source: "Sardar Patel Institute of Technology (SPIT) cl. 4.5",
        older_says: "The attendance condonation fee is ₹500 per course.",
        newer_source: "SPIT/ACAD/CIR/2026-27/03 item 2",
        newer_says: "Attendance condonation fee revised from ₹500 to ₹750 per course.",
        applies: `newer (effective 2026-10-12) as of ${asOf}`,
      },
    ],
    retrieved_ids: ["SPIT_ACAD_CIR_2026_27_03_004", "SPIT_ACAD_ARH_2026_27_01_013"],
    context_ids: ["SPIT_ACAD_CIR_2026_27_03_004", "SPIT_ACAD_ARH_2026_27_01_013"],
    abstain_reason: null,
    embed_backend: "fixture",
    coverage: 0.74,
    n_claims: 1,
    n_verified: 1,
    claims: [
      {
        text,
        evidence: [cir.chunk_id],
        verified: true,
        support_score: 0.8,
        citations: [{ ...cir, excerpt: text }, { ...arh, excerpt: text }],
      },
    ],
    claims_text: text,
    answer: `- ${text} [1]`,
    outcome: "conflict",
    latency_ms: 0,
  };
}
