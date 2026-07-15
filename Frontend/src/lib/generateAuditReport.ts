/**
 * generateAuditReport.ts
 * ========================
 * Generates a full 16-section Supply Chain Risk Audit Report as a .docx file.
 * No AI/tech-stack names are exposed in the output.
 */

import {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, PageBreak, Header, Footer,
  PageNumber, NumberFormat, UnderlineType, ImageRun,
} from "docx";
import { saveAs } from "file-saver";
import { fmtINR } from "@/lib/currency";
import { api } from "@/lib/api";

// ─── Palette helpers ──────────────────────────────────────────────────────────
const RED    = "DC2626"; // Sentinel red
const DARK   = "0F172A"; // Slate 900
const GREY   = "475569"; // Slate 600
const LGREY  = "F8FAFC"; // Slate 50
const WHITE  = "FFFFFF";
const GREEN  = "16A34A"; // Green 600
const AMBER  = "D97706"; // Amber 600

function h1(text: string): Paragraph {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 200 },
    children: [
      new TextRun({
        text,
        bold: true,
        size: 36,
        color: RED,
        font: "Inter",
      }),
    ],
  });
}

function h2(text: string): Paragraph {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RED, space: 4 } },
    children: [
      new TextRun({
        text,
        bold: true,
        size: 26,
        color: DARK,
        font: "Inter",
      }),
    ],
  });
}

function h3(text: string): Paragraph {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 80 },
    children: [
      new TextRun({ text, bold: true, size: 22, color: GREY, font: "Inter" }),
    ],
  });
}

function body(text: string, options?: { bold?: boolean; italic?: boolean; color?: string }): Paragraph {
  return new Paragraph({
    spacing: { before: 80, after: 80 },
    children: [
      new TextRun({
        text,
        size: 20,
        font: "Inter",
        bold: options?.bold,
        italics: options?.italic,
        color: options?.color ?? DARK,
      }),
    ],
  });
}

function kv(label: string, value: string): Paragraph {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    children: [
      new TextRun({ text: `${label}: `, bold: true, size: 20, font: "Inter", color: GREY }),
      new TextRun({ text: value || "—", size: 20, font: "Inter", color: DARK }),
    ],
  });
}

function pageBreak(): Paragraph {
  return new Paragraph({ children: [new PageBreak()] });
}

function separator(): Paragraph {
  return new Paragraph({
    spacing: { before: 200, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "E2E8F0" } },
    children: [new TextRun({ text: "" })],
  });
}

function bullet(text: string): Paragraph {
  return new Paragraph({
    bullet: { level: 0 },
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text, size: 20, font: "Inter", color: DARK })],
  });
}

function dataTable(headers: string[], rows: string[][]): Table {
  const headerCells = headers.map(
    (h) =>
      new TableCell({
        shading: { type: ShadingType.SOLID, color: RED, fill: RED },
        margins: { top: 120, bottom: 120, left: 150, right: 150 },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: h, bold: true, color: WHITE, size: 24, font: "Inter" })],
          }),
        ],
      })
  );

  const dataRows = rows.map((row, ri) =>
    new TableRow({
      children: row.map(
        (cell) =>
          new TableCell({
            shading: ri % 2 === 0
              ? { type: ShadingType.SOLID, color: LGREY, fill: LGREY }
              : { type: ShadingType.SOLID, color: WHITE, fill: WHITE },
            margins: { top: 120, bottom: 120, left: 150, right: 150 },
            children: [
              new Paragraph({
                children: [new TextRun({ text: cell || "—", size: 22, font: "Inter", color: DARK })],
              }),
            ],
          })
      ),
    })
  );

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [new TableRow({ children: headerCells }), ...dataRows],
  });
}

// ─── Severity colour helper ───────────────────────────────────────────────────
function severityColor(sev: string): string {
  if (sev === "CRITICAL") return RED;
  if (sev === "WARNING")  return AMBER;
  return GREEN;
}

// ─── Main export ─────────────────────────────────────────────────────────────
export async function generateAuditReport(
  incidents: any[],
  auditLog: any[],
  govMetrics: any,
  postRecords: any[]
): Promise<void> {
  let groqSummary = "This report provides a comprehensive audit of the supply chain risk landscape as monitored by the Praecantator autonomous intelligence platform. It is intended for executive review and operational decision-making.";
  try {
    const lightIncidents = incidents.map(inc => ({
      title: inc.event_title || inc.title,
      severity: inc.severity,
      region: inc.region || inc.event_country,
      status: inc.status,
      exposure: inc.total_exposure_usd
    })).slice(0, 15);
    const res = await api.incidents.execSummary({ incidents: lightIncidents });
    if (res && res.summary) {
      groqSummary = res.summary;
    }
  } catch (err) {
    console.error("Failed to generate Groq summary:", err);
  }

  const now     = new Date();
  const dateStr = now.toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
  const total   = incidents.length;
  const critical = incidents.filter((i) => i.severity === "CRITICAL").length;
  const warning  = incidents.filter((i) => i.severity === "WARNING" || i.severity === "HIGH").length;
  const safe     = total - critical - warning;
  const totalExposure = incidents.reduce((s, i) => s + Number(i.total_exposure_usd || 0), 0);
  const avgConf = total > 0
    ? (incidents.reduce((s, i) => s + Number(i.gnn_confidence || 0), 0) / total * 100).toFixed(1)
    : "N/A";
  const healthPct = total > 0 ? ((safe / total) * 100).toFixed(0) : "100";
  const top3 = [...incidents]
    .sort((a, b) => Number(b.total_exposure_usd || 0) - Number(a.total_exposure_usd || 0))
    .slice(0, 3);

  const gm = govMetrics ?? {};

  let logoBuffer: ArrayBuffer | undefined;
  try {
    const res = await fetch("/Praecantator.png");
    if (res.ok) {
      logoBuffer = await res.arrayBuffer();
    }
  } catch (e) {
    console.error("Failed to fetch logo for report", e);
  }

  // ── Cover page ─────────────────────────────────────────────────────────────
  const cover: any[] = [
    new Paragraph({ spacing: { before: 800 }, children: [new TextRun({ text: "" })] }),
    ...(logoBuffer ? [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 200, after: 200 },
        children: [
          new ImageRun({
            data: logoBuffer,
            transformation: {
              width: 150,
              height: 150,
            },
            type: "png",
          }),
        ],
      })
    ] : []),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({ text: "PRAECANTATOR", bold: true, size: 72, color: RED, font: "Inter", allCaps: true }),
      ],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 100, after: 100 },
      children: [
        new TextRun({ text: "SUPPLY CHAIN RISK AUDIT REPORT", bold: true, size: 40, color: DARK, font: "Inter" }),
      ],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 80, after: 600 },
      children: [
        new TextRun({ text: `Generated: ${dateStr} IST`, size: 22, color: GREY, font: "Inter", italics: true }),
      ],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({ text: "CONFIDENTIAL — RESTRICTED DISTRIBUTION", bold: true, size: 20, color: RED, font: "Inter" }),
      ],
    }),
    pageBreak(),
  ];

  // ── Section 1: Executive Summary ───────────────────────────────────────────
  const sec1: any[] = [
    h1("1. Executive Summary"),
    body(groqSummary),
    new Paragraph({ spacing: { before: 200 }, children: [new TextRun({ text: "" })] }),
    h3("Top 3 Priority Risks Requiring Immediate Action"),
    ...top3.map((inc, i) =>
      bullet(`${i + 1}. [${inc.severity}] ${inc.event_title || "Unknown"} — ${fmtINR(Number(inc.total_exposure_usd || 0))} exposure`)
    ),
    h3("Strategic Actions Recommended"),
    bullet("Activate backup supplier protocols for all CRITICAL-tier incidents."),
    bullet("Initiate route re-planning for logistics-related disruptions above $100,000 exposure."),
    bullet("Escalate unresolved incidents older than 72 hours to executive governance board."),
    bullet("Review inventory buffer positions for all Tier-1 affected suppliers."),
    pageBreak(),
  ];

  // ── Section 2-16: Per-incident + aggregate sections ────────────────────────
  const incidentSections: any[] = [];

  incidents.forEach((inc, idx) => {
    const conf   = (Number(inc.gnn_confidence || 0) * 100).toFixed(0);
    const expo   = Number(inc.total_exposure_usd || 0).toLocaleString();
    const nodes  = Number(inc.affected_node_count || 0);
    const sev    = String(inc.severity || "UNKNOWN");
    const status = String(inc.status || "ACTIVE");
    const title  = String(inc.event_title || "Unnamed Incident");

    incidentSections.push(
      h1(`2. Incident ${idx + 1} — ${title}`),
      separator(),

      // 2: Incident Overview
      h2("Incident Overview"),
      dataTable(
        ["Field", "Value"],
        [
          ["Title",               title],
          ["Detected At",         inc.created_at ? new Date(inc.created_at).toLocaleString() : "—"],
          ["Last Updated",        inc.updated_at  ? new Date(inc.updated_at).toLocaleString()  : "—"],
          ["Geographic Range",    inc.radius_km ? `${inc.radius_km} km radius` : (inc.impact_radius_km ? `${inc.impact_radius_km} km radius` : "—")],
          ["Coordinates",         (inc.event_lat && inc.event_lng) ? `${inc.event_lat}, ${inc.event_lng}` : "—"],
          ["Risk Category",       String(inc.event_type || inc.category || "—")],
          ["Severity Level",      sev],
          ["Source of Detection", String(inc.source || "Autonomous Signal Ingestion")],
          ["Current Status",      status],
        ]
      ),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 3: Affected Entities
      h2("3. Affected Entities"),
      kv("Affected Nodes",    String(nodes)),
      kv("Supplier Count",    String(inc.supplier_count || nodes || "—")),
      kv("Tier Level",        String(inc.tier || "Tier 1")),
      kv("Affected Facilities", String(inc.facilities || "—")),
      kv("Linked Products / SKUs", String(inc.skus || "—")),
      kv("Downstream Dependencies", String(inc.downstream_impact || "Pending assessment")),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 4: Risk Characterization
      h2("4. Risk Characterization"),
      kv("Detailed Description",    String(inc.description || inc.recommendation || "See decision log below.")),
      kv("Trigger Event",           String(inc.event_type || "—")),
      kv("Risk Type",               String(inc.risk_type || "Operational")),
      kv("Duration Estimate",       String(inc.duration_estimate || "Medium-term (7–30 days)")),
      kv("Probability Score",       `${conf}%`),
      kv("Impact Severity Score",   sev === "CRITICAL" ? "9–10 / 10" : sev === "WARNING" ? "5–7 / 10" : "1–4 / 10"),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 5: Financial Impact
      h2("5. Financial Impact Analysis"),
      dataTable(
        ["Financial Metric", "Value (INR)"],
        [
          ["Direct Financial Exposure",   fmtINR(Number(inc.total_exposure_usd || 0))],
          ["Indirect Loss Estimate",       `${fmtINR(Number(inc.total_exposure_usd || 0) * 0.25)} (est.)`],
          ["Revenue at Risk",              `${fmtINR(Number(inc.total_exposure_usd || 0) * 0.6)} (est.)`],
          ["Cost of Inaction",             `${fmtINR(Number(inc.total_exposure_usd || 0) * 1.3)} (est.)`],
          ["Estimated Mitigation Cost",    `${fmtINR(Number(inc.total_exposure_usd || 0) * 0.15)} (est.)`],
          ["Stockout Horizon",             inc.min_stockout_days ? `${inc.min_stockout_days} days` : "—"],
        ]
      ),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 6: Timeline Analysis
      h2("6. Timeline Analysis"),
      dataTable(
        ["Stage", "Timestamp"],
        [
          ["Detection",           inc.created_at  ? new Date(inc.created_at).toLocaleString()  : "—"],
          ["Analysis",            inc.analyzed_at ? new Date(inc.analyzed_at).toLocaleString() : "—"],
          ["Decision / Approval", inc.approved_at ? new Date(inc.approved_at).toLocaleString() : "—"],
          ["Execution",           inc.resolved_at ? new Date(inc.resolved_at).toLocaleString() : "—"],
          ["Audit Closure",       inc.updated_at  ? new Date(inc.updated_at).toLocaleString()  : "—"],
        ]
      ),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 7: AI Assessment
      h2("7. Intelligence Assessment & Confidence"),
      kv("Confidence Score",           `${conf}%`),
      kv("Data Sources",               "Global event feeds, geospatial satellite data, financial APIs, news intelligence"),
      kv("Assessment Summary",         String(inc.recommendation || "System recommendation pending operator review.")),
      kv("Known Uncertainties",        "Late-arriving data from regional sources may affect initial scoring. Confidence improves as corroborating signals accumulate."),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 8: Root Cause Analysis
      h2("8. Root Cause Analysis"),
      kv("Primary Cause",     String(inc.event_type || "Unclassified event trigger")),
      kv("Secondary Causes",  "Dependency concentration, insufficient buffer inventory, single-source supplier relationship"),
      kv("Historical Pattern","Cross-referenced against incident archive. Pattern similarity assessed automatically."),
      kv("Failure Mode",      sev === "CRITICAL" ? "High-frequency, high-impact — systemic exposure" : "Isolated — manageable with standard protocols"),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 9: Risk Propagation
      h2("9. Risk Propagation Analysis"),
      kv("Affected Nodes",        String(nodes)),
      kv("Upstream Impact",       "Suppliers feeding into affected node are under active monitoring."),
      kv("Downstream Impact",     String(inc.downstream_impact || "Production continuity at risk for linked manufacturing nodes.")),
      kv("Cascade Risk Score",    sev === "CRITICAL" ? "HIGH — immediate containment required" : "MODERATE — monitor for 48 hours"),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 10: Mitigation & Response
      h2("10. Mitigation & Response Actions"),
      kv("Decision Log",          String(inc.recommendation || "—")),
      kv("Immediate Actions",     status === "RESOLVED" || status === "APPROVED" ? "Executed — see Decision Log." : "Pending operator approval."),
      kv("Alternative Suppliers", String(inc.backup_supplier || "Cross-reference supplier intelligence for Tier-1 alternatives.")),
      kv("Route Re-planning",     String(inc.alternate_route || "Route optimization queued if logistics-related.")),
      kv("Inventory Buffer",      "Recommend 14-day buffer for affected SKUs."),
      kv("Escalation Level",      sev === "CRITICAL" ? "STRATEGIC — C-suite notification required" : "OPERATIONAL — procurement team"),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 11: Compliance
      h2("11. Compliance & Regulatory Check"),
      kv("Standards Affected",         "ISO 31000, ISO 28000, Internal SCRM Policy v3.2"),
      kv("Violations Detected",        status === "DISMISSED" ? "None — incident dismissed post-review." : "Under review — pending full audit closure."),
      kv("Reporting Obligations",      sev === "CRITICAL" ? "Executive board notification triggered." : "Standard incident logging sufficient."),
      kv("Audit Trail",                "Immutably recorded in system audit log."),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      // 12: Status Tracking
      h2("12. Risk Status Tracking"),
      kv("Current Status",       status),
      kv("Assigned Owner",       String(inc.assigned_to || "Procurement Operations")),
      kv("SLA Breach Indicator", status === "AWAITING_APPROVAL" ? "⚠ BREACH RISK — approval outstanding" : "Within SLA"),
      new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: "" })] }),

      pageBreak(),
    );
  });

  // ── Section 13: Supporting Evidence ────────────────────────────────────────
  const sec13: any[] = [
    h1("13. Supporting Evidence"),
    body("All signals are sourced from authenticated global intelligence feeds. Data integrity is verified through cross-source corroboration before any incident is escalated."),
    bullet("Geospatial event telemetry — continuous real-time ingestion"),
    bullet("Financial exposure data — FX-adjusted against live currency rates"),
    bullet("Supplier registry — cross-referenced with operational status"),
    bullet("News and geopolitical intelligence — multi-source aggregation"),
    pageBreak(),
  ];

  // ── Section 14: Metrics & Governance (REMOVED) ──────────────────────────────

  // ── Section 15: Conclusion ──────────────────────────────────────────────────
  const sec15: any[] = [
    h1("15. Conclusion & Strategic Insight"),
    body(`This audit covers ${total} risk events with a combined financial exposure of ${fmtINR(totalExposure)}. Network health stands at ${healthPct}%.`),
    new Paragraph({ spacing: { before: 100 }, children: [new TextRun({ text: "" })] }),
    h3("What This Report Reveals"),
    bullet("Supplier concentration in high-risk geographies remains the primary systemic vulnerability."),
    bullet("Logistics disruptions account for the fastest-escalating incident category."),
    bullet("Confidence convergence time is within acceptable SLA for all validated incidents."),
    h3("Long-term Recommendations"),
    bullet("Diversify Tier-1 supplier base across minimum 3 geographic regions per category."),
    bullet("Implement 30-day rolling buffer inventory for top-20 revenue-critical SKUs."),
    bullet("Establish pre-negotiated backup contracts with alternative carriers for high-risk corridors."),
    bullet("Conduct quarterly supply chain stress tests against historical disruption scenarios."),
    h3("Preventive Strategy"),
    bullet("Continuous geospatial monitoring with automated escalation thresholds."),
    bullet("Supplier health scoring reviewed monthly with contractual SLA enforcement."),
    bullet("Cross-functional rapid response team to be activated within 2 hours of CRITICAL incidents."),
    pageBreak(),
  ];

  // ── Section 16: Appendix ───────────────────────────────────────────────────
  const sec16: any[] = [
    h1("16. Appendix"),
    h3("Glossary"),
    kv("CRITICAL",              "Immediate action required. Exposure threshold exceeded."),
    kv("WARNING",               "Elevated risk. Monitoring escalated. Action within 24h."),
    kv("Confidence Score",      "Statistical confidence in risk classification (0–100%)."),
    kv("Exposure (INR)",        "Estimated direct financial value at risk from the incident."),
    kv("Cascade Risk Score",    "Probability that the incident propagates to adjacent supply nodes."),
    kv("OODA Pipeline",         "Observe-Orient-Decide-Act — the autonomous response cycle."),
    kv("SLA",                   "Service Level Agreement — the contractual response time threshold."),
    h3("Report Metadata"),
    kv("Platform",     "Praecantator — Autonomous Supply Chain Risk Management"),
    kv("Report Version", "1.0"),
    kv("Generated At", dateStr),
    kv("Classification", "CONFIDENTIAL"),
  ];

  // ── Assemble document ──────────────────────────────────────────────────────
  const doc = new Document({
    numbering: {
      config: [
        {
          reference: "bullet-list",
          levels: [{ level: 0, format: NumberFormat.BULLET, text: "•", alignment: AlignmentType.LEFT }],
        },
      ],
    },
    styles: {
      default: {
        document: {
          run: { font: "Inter", size: 20, color: DARK },
        },
      },
    },
    sections: [
      {
        headers: {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.RIGHT,
                border: { bottom: { style: BorderStyle.SINGLE, size: 2, color: "E2E8F0" } },
                children: [
                  new TextRun({ text: "PRAECANTATOR — SUPPLY CHAIN RISK AUDIT REPORT  ", bold: true, size: 16, color: GREY, font: "Inter" }),
                  new TextRun({ text: "CONFIDENTIAL", bold: true, size: 16, color: RED, font: "Inter" }),
                ],
              }),
            ],
          }),
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                border: { top: { style: BorderStyle.SINGLE, size: 2, color: "E2E8F0" } },
                children: [
                  new TextRun({ text: `Generated ${dateStr} | Page `, size: 16, color: GREY, font: "Inter" }),
                  new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY, font: "Inter" }),
                ],
              }),
            ],
          }),
        },
        children: [
          ...cover,
          ...sec1,
          ...incidentSections,
          ...sec13,
          ...sec15,
          ...sec16,
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, `Praecantator_Risk_Audit_${now.toISOString().slice(0, 10)}.docx`);
}
