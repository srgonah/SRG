import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/api/client';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { Invoice } from '@/api/types';

export function InvoicesPage() {
  useDocumentTitle('Invoices');

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 20;

  useEffect(() => {
    async function loadInvoices() {
      setLoading(true);
      try {
        const res = await api.invoices.list(limit, page * limit);
        setInvoices(res.invoices || []);
        setTotal(res.total || 0);
      } catch (err) {
        console.error('Failed to load invoices:', err);
      } finally {
        setLoading(false);
      }
    }
    loadInvoices();
  }, [page]);

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Invoices</h1>
          <p className="text-gray-400 mt-1">{total} invoices total</p>
        </div>
        <Link to="/upload" className="btn btn-primary">
          Upload Invoice
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64" role="status">
          <div className="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
          <span className="sr-only">Loading invoices...</span>
        </div>
      ) : invoices.length === 0 ? (
        <div className="card text-center py-12">
          <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-gray-400 mb-4">No invoices yet</p>
          <Link to="/upload" className="btn btn-primary">
            Upload your first invoice
          </Link>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden p-0">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-gray-400 border-b border-dark-700">
                  <th className="p-4" scope="col">Invoice</th>
                  <th className="p-4" scope="col">Vendor</th>
                  <th className="p-4" scope="col">Date</th>
                  <th className="p-4 text-right" scope="col">Amount</th>
                  <th className="p-4 text-right" scope="col">Confidence</th>
                  <th className="p-4" scope="col"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-dark-800 hover:bg-dark-800/50 transition-colors">
                    <td className="p-4">
                      <p className="font-medium text-white">{inv.invoice_number || 'Unknown'}</p>
                      <p className="text-xs text-gray-400">{inv.source_file || '-'}</p>
                    </td>
                    <td className="p-4 text-gray-300">{inv.vendor_name || '-'}</td>
                    <td className="p-4 text-gray-400">{inv.invoice_date || '-'}</td>
                    <td className="p-4 text-right">
                      <span className="font-medium text-white">
                        {inv.currency} {inv.total_amount?.toFixed(2) || '0.00'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <span
                        className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                          inv.confidence >= 0.8
                            ? 'bg-green-500/20 text-green-400'
                            : inv.confidence >= 0.5
                              ? 'bg-yellow-500/20 text-yellow-400'
                              : 'bg-red-500/20 text-red-400'
                        }`}
                      >
                        {Math.round(inv.confidence * 100)}%
                      </span>
                    </td>
                    <td className="p-4">
                      <Link
                        to={`/invoices/${inv.id}`}
                        className="text-primary-400 hover:text-primary-300 text-sm"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <nav className="flex items-center justify-center gap-2" aria-label="Invoice pagination">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="btn btn-secondary disabled:opacity-50"
                aria-label="Previous page"
              >
                Previous
              </button>
              <span className="text-gray-400 px-4" aria-current="page">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="btn btn-secondary disabled:opacity-50"
                aria-label="Next page"
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
