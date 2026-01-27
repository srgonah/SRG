import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '@/api/client';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { Invoice, AuditResult } from '@/api/types';

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useDocumentTitle(invoice ? `Invoice ${invoice.invoice_number || id}` : 'Invoice Detail');

  useEffect(() => {
    async function loadInvoice() {
      if (!id) return;
      setLoading(true);
      try {
        const [inv, auditRes] = await Promise.all([
          api.invoices.get(id),
          api.invoices.getAudit(id),
        ]);
        setInvoice(inv);
        setAudit(auditRes);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load invoice');
      } finally {
        setLoading(false);
      }
    }
    loadInvoice();
  }, [id]);

  const handleAudit = async () => {
    if (!id) return;
    setAuditing(true);
    try {
      const result = await api.invoices.audit({ invoice_id: id, use_llm: true });
      setAudit(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Audit failed');
    } finally {
      setAuditing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" role="status">
        <div className="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
        <span className="sr-only">Loading invoice details...</span>
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div className="card text-center py-12" role="alert">
        <p className="text-red-400 mb-4">{error || 'Invoice not found'}</p>
        <Link to="/invoices" className="btn btn-secondary">
          Back to Invoices
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link to="/invoices" className="text-gray-400 hover:text-gray-300 text-sm mb-2 inline-block">
            &larr; Back to Invoices
          </Link>
          <h1 className="text-2xl font-bold text-white">
            Invoice {invoice.invoice_number || 'Unknown'}
          </h1>
          <p className="text-gray-400 mt-1">{invoice.vendor_name || 'Unknown vendor'}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleAudit}
            disabled={auditing}
            className="btn btn-secondary"
          >
            {auditing ? 'Auditing...' : 'Re-audit'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Invoice Details */}
        <div className="lg:col-span-2 space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">Details</h2>
            <div className="grid grid-cols-2 gap-4">
              <DetailRow label="Invoice Number" value={invoice.invoice_number} />
              <DetailRow label="Vendor" value={invoice.vendor_name} />
              <DetailRow label="Vendor Address" value={invoice.vendor_address} />
              <DetailRow label="Buyer" value={invoice.buyer_name} />
              <DetailRow label="Invoice Date" value={invoice.invoice_date} />
              <DetailRow label="Due Date" value={invoice.due_date} />
              <DetailRow label="Parser Used" value={invoice.parser_used} />
              <DetailRow
                label="Confidence"
                value={`${Math.round(invoice.confidence * 100)}%`}
              />
            </div>
          </div>

          {/* Line Items */}
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">
              Line Items ({invoice.line_items.length})
            </h2>
            {invoice.line_items.length === 0 ? (
              <p className="text-gray-400">No line items</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-400 border-b border-dark-700">
                      <th className="pb-3" scope="col">Description</th>
                      <th className="pb-3 text-right" scope="col">Qty</th>
                      <th className="pb-3 text-right" scope="col">Unit Price</th>
                      <th className="pb-3 text-right" scope="col">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.line_items.map((item, i) => (
                      <tr key={i} className="border-b border-dark-800">
                        <td className="py-3">
                          <p className="text-white">{item.description}</p>
                          {item.reference && (
                            <p className="text-xs text-gray-400">Ref: {item.reference}</p>
                          )}
                        </td>
                        <td className="py-3 text-right text-gray-400">
                          {item.quantity} {item.unit || ''}
                        </td>
                        <td className="py-3 text-right text-gray-400">
                          {item.unit_price.toFixed(2)}
                        </td>
                        <td className="py-3 text-right text-white font-medium">
                          {item.total_price.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Totals */}
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">Summary</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Subtotal</span>
                <span className="text-white">
                  {invoice.currency} {invoice.subtotal?.toFixed(2) || '-'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Tax</span>
                <span className="text-white">
                  {invoice.currency} {invoice.tax_amount?.toFixed(2) || '-'}
                </span>
              </div>
              <div className="border-t border-dark-700 pt-3 flex justify-between">
                <span className="font-semibold text-gray-300">Total</span>
                <span className="font-bold text-xl text-white">
                  {invoice.currency} {invoice.total_amount?.toFixed(2) || '0.00'}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Calculated Total</span>
                <span className="text-gray-400">
                  {invoice.currency} {invoice.calculated_total.toFixed(2)}
                </span>
              </div>
            </div>
          </div>

          {/* Audit Results */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Audit</h2>
              {audit && (
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium ${
                    audit.passed
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}
                >
                  {audit.passed ? '\u2713 Passed' : '\u2717 Failed'}
                </span>
              )}
            </div>

            {audit ? (
              <div className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Errors</span>
                  <span className={audit.error_count > 0 ? 'text-red-400' : 'text-green-400'}>
                    {audit.error_count}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Warnings</span>
                  <span className={audit.warning_count > 0 ? 'text-yellow-400' : 'text-green-400'}>
                    {audit.warning_count}
                  </span>
                </div>

                {audit.findings.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {audit.findings.map((f, i) => (
                      <div
                        key={i}
                        className={`p-3 rounded-lg text-sm ${
                          f.severity === 'error'
                            ? 'bg-red-500/10 border border-red-500/30 text-red-400'
                            : f.severity === 'warning'
                              ? 'bg-yellow-500/10 border border-yellow-500/30 text-yellow-400'
                              : 'bg-blue-500/10 border border-blue-500/30 text-blue-400'
                        }`}
                      >
                        <p className="font-medium">{f.message}</p>
                        <p className="text-xs opacity-70 mt-1">{f.code}</p>
                      </div>
                    ))}
                  </div>
                )}

                {audit.summary && (
                  <p className="text-sm text-gray-400 mt-4">{audit.summary}</p>
                )}
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-gray-400 text-sm mb-3">No audit results</p>
                <button onClick={handleAudit} disabled={auditing} className="btn btn-primary text-sm">
                  Run Audit
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-sm text-gray-400">{label}</p>
      <p className="text-white">{value || '-'}</p>
    </div>
  );
}
