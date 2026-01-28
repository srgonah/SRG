import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { invoices as api } from "../api/client";
import type { Invoice, AuditResult } from "../types/api";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";
import Badge from "../components/Badge";

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [audits, setAudits] = useState<AuditResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    setLoading(true);
    setError("");
    Promise.all([api.get(id), api.audits(id).catch(() => [])])
      .then(([inv, aud]) => {
        setInvoice(inv);
        setAudits(aud);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(load, [load]);

  const downloadPdf = async () => {
    if (!id) return;
    setPdfLoading(true);
    try {
      const blob = await api.proformaPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `proforma-${invoice?.invoice_number ?? id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setPdfLoading(false);
    }
  };

  const runAudit = async () => {
    if (!id) return;
    setAuditLoading(true);
    try {
      const result = await api.audit(id);
      setAudits((prev) => [result, ...prev]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Audit failed");
    } finally {
      setAuditLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  if (!invoice) {
    return <ErrorBanner message={error || "Invoice not found"} />;
  }

  const latestAudit = audits[0];

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link to="/invoices" className="text-slate-500 hover:text-slate-300 text-sm">&larr; Invoices</Link>
        <h1 className="text-xl font-semibold">
          Invoice {invoice.invoice_number ?? invoice.id.slice(0, 8)}
        </h1>
        <Badge color={invoice.confidence >= 0.8 ? "green" : "yellow"}>
          {(invoice.confidence * 100).toFixed(0)}% confidence
        </Badge>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {/* Actions */}
      <div className="flex gap-3 mb-6">
        <button
          onClick={downloadPdf}
          disabled={pdfLoading}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm transition-colors flex items-center gap-2"
        >
          {pdfLoading && <Spinner />}
          Download Proforma PDF
        </button>
        <button
          onClick={runAudit}
          disabled={auditLoading}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded text-sm transition-colors flex items-center gap-2"
        >
          {auditLoading && <Spinner />}
          Run Audit
        </button>
      </div>

      {/* Invoice details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <section className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h2 className="text-sm font-medium text-slate-500 mb-3">Details</h2>
          <dl className="space-y-2 text-sm">
            {([
              ["Vendor", invoice.vendor_name],
              ["Buyer", invoice.buyer_name],
              ["Date", invoice.invoice_date],
              ["Due Date", invoice.due_date],
              ["Currency", invoice.currency],
              ["Parser", invoice.parser_used],
              ["Source File", invoice.source_file],
            ] as const).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <dt className="text-slate-500">{k}</dt>
                <dd className="text-right">{v ?? "—"}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h2 className="text-sm font-medium text-slate-500 mb-3">Totals</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Subtotal</dt>
              <dd className="font-mono">{invoice.subtotal?.toLocaleString() ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Tax</dt>
              <dd className="font-mono">{invoice.tax_amount?.toLocaleString() ?? "—"}</dd>
            </div>
            <div className="flex justify-between border-t border-slate-800 pt-2 mt-2">
              <dt className="font-medium">Total</dt>
              <dd className="font-mono font-medium">{invoice.total_amount?.toLocaleString() ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Calculated</dt>
              <dd className="font-mono">{invoice.calculated_total.toLocaleString()}</dd>
            </div>
          </dl>
        </section>

        {latestAudit && (
          <section className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <h2 className="text-sm font-medium text-slate-500 mb-3">Latest Audit</h2>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge color={latestAudit.passed ? "green" : "red"}>
                  {latestAudit.passed ? "PASSED" : "FAILED"}
                </Badge>
                <span className="text-slate-500 text-xs">
                  {new Date(latestAudit.audited_at).toLocaleString()}
                </span>
              </div>
              <p className="text-slate-400">{latestAudit.summary ?? "No summary"}</p>
              <div className="flex gap-3 text-xs">
                <span className="text-red-400">{latestAudit.error_count} errors</span>
                <span className="text-yellow-400">{latestAudit.warning_count} warnings</span>
              </div>
            </div>
          </section>
        )}
      </div>

      {/* Line items */}
      <section className="mb-8">
        <h2 className="text-sm font-medium text-slate-400 mb-3">
          Line Items ({invoice.line_items.length})
        </h2>
        {invoice.line_items.length === 0 ? (
          <p className="text-slate-600 text-sm">No line items parsed.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-slate-500">
                  <th className="py-2 pr-4">Description</th>
                  <th className="py-2 pr-4 text-right">Qty</th>
                  <th className="py-2 pr-4">Unit</th>
                  <th className="py-2 pr-4 text-right">Unit Price</th>
                  <th className="py-2 pr-4 text-right">Total</th>
                  <th className="py-2">HS Code</th>
                  <th className="py-2">Catalog</th>
                </tr>
              </thead>
              <tbody>
                {invoice.line_items.map((item, i) => (
                  <tr key={i} className="border-b border-slate-800/50">
                    <td className="py-2 pr-4 max-w-xs truncate">{item.description}</td>
                    <td className="py-2 pr-4 text-right font-mono">{item.quantity}</td>
                    <td className="py-2 pr-4 text-slate-400">{item.unit ?? "—"}</td>
                    <td className="py-2 pr-4 text-right font-mono">{item.unit_price.toLocaleString()}</td>
                    <td className="py-2 pr-4 text-right font-mono">{item.total_price.toLocaleString()}</td>
                    <td className="py-2 text-slate-400">{item.hs_code ?? "—"}</td>
                    <td className="py-2">
                      {item.matched_material_id ? (
                        <Badge color="green">Matched</Badge>
                      ) : item.needs_catalog ? (
                        <Badge color="yellow">Needs match</Badge>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Audit findings */}
      {audits.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-slate-400 mb-3">
            Audit Findings ({audits.length} audit{audits.length !== 1 ? "s" : ""})
          </h2>
          {audits.map((audit) => (
            <div key={audit.id} className="mb-4 bg-slate-900 border border-slate-800 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3 text-xs text-slate-500">
                <Badge color={audit.passed ? "green" : "red"}>
                  {audit.passed ? "PASS" : "FAIL"}
                </Badge>
                {new Date(audit.audited_at).toLocaleString()}
                {audit.duration_ms != null && <span>({audit.duration_ms}ms)</span>}
              </div>
              {audit.findings.length === 0 ? (
                <p className="text-sm text-slate-500">No issues found.</p>
              ) : (
                <div className="space-y-2">
                  {audit.findings.map((f, i) => (
                    <div
                      key={i}
                      className={`text-sm px-3 py-2 rounded border ${
                        f.severity === "error"
                          ? "bg-red-500/5 border-red-500/20 text-red-400"
                          : f.severity === "warning"
                            ? "bg-yellow-500/5 border-yellow-500/20 text-yellow-400"
                            : "bg-slate-800 border-slate-700 text-slate-400"
                      }`}
                    >
                      <span className="font-mono text-xs mr-2">[{f.code}]</span>
                      {f.message}
                      {f.field && <span className="ml-2 text-xs opacity-60">({f.field})</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
