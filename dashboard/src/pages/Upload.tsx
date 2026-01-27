import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { UploadInvoiceResponse } from '@/api/types';

export function UploadPage() {
  useDocumentTitle('Upload Invoice');

  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadInvoiceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Options
  const [autoAudit, setAutoAudit] = useState(true);
  const [autoIndex, setAutoIndex] = useState(true);
  const [vendorHint, setVendorHint] = useState('');

  // Focus result area when upload completes
  useEffect(() => {
    if (result) {
      resultRef.current?.focus();
    }
  }, [result]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.type === 'application/pdf' || droppedFile.type.startsWith('image/'))) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError('Please upload a PDF or image file');
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  }, []);

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.invoices.upload(file, {
        auto_audit: autoAudit,
        auto_index: autoIndex,
        vendor_hint: vendorHint || undefined,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  const handleDropZoneKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInputRef.current?.click();
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Upload Invoice</h1>
        <p className="text-gray-400 mt-1">Upload a PDF or image to parse and audit</p>
      </div>

      {!result ? (
        <>
          {/* Drop Zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onKeyDown={handleDropZoneKeyDown}
            role="button"
            tabIndex={0}
            aria-label={file ? `Selected file: ${file.name}. Press Enter to change file.` : 'Upload area: drag a file here or press Enter to browse'}
            className={`card border-2 border-dashed transition-colors cursor-pointer ${
              isDragging
                ? 'border-primary-500 bg-primary-500/10'
                : file
                  ? 'border-green-500 bg-green-500/10'
                  : 'border-dark-600 hover:border-dark-500'
            }`}
          >
            <div className="flex flex-col items-center justify-center py-12">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,image/*"
                onChange={handleFileSelect}
                className="hidden"
                aria-label="Choose invoice file (PDF or image)"
              />
              {file ? (
                <>
                  <svg className="w-12 h-12 text-green-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-lg font-medium text-white">{file.name}</p>
                  <p className="text-sm text-gray-400 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleReset(); }}
                    className="mt-4 text-sm text-red-400 hover:text-red-300"
                  >
                    Remove file
                  </button>
                </>
              ) : (
                <>
                  <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  <p className="text-lg font-medium text-gray-300">Drop your invoice here</p>
                  <p className="text-sm text-gray-400 mt-1">or click to browse</p>
                  <p className="text-xs text-gray-400 mt-2">PDF or image files supported</p>
                </>
              )}
            </div>
          </div>

          {/* Options */}
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">Options</h2>
            <div className="space-y-4">
              <div>
                <label htmlFor="vendor-hint" className="label">Vendor Hint (optional)</label>
                <input
                  id="vendor-hint"
                  type="text"
                  value={vendorHint}
                  onChange={(e) => setVendorHint(e.target.value)}
                  placeholder="e.g., VOLTA HUB"
                  className="input"
                />
              </div>
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoAudit}
                    onChange={(e) => setAutoAudit(e.target.checked)}
                    className="w-4 h-4 accent-primary-500"
                  />
                  <span className="text-gray-300">Auto-audit after parsing</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoIndex}
                    onChange={(e) => setAutoIndex(e.target.checked)}
                    className="w-4 h-4 accent-primary-500"
                  />
                  <span className="text-gray-300">Index for search</span>
                </label>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div role="alert" className="p-4 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400">
              {error}
            </div>
          )}

          {/* Upload Button */}
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="btn btn-primary w-full py-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploading ? (
              <span className="flex items-center justify-center gap-2" role="status">
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Processing...
              </span>
            ) : (
              'Upload & Process'
            )}
          </button>
        </>
      ) : (
        /* Results */
        <div className="space-y-6">
          {/* Success Banner */}
          <div ref={resultRef} tabIndex={-1} role="status" className="p-4 bg-green-500/20 border border-green-500/50 rounded-lg outline-none">
            <div className="flex items-center gap-3">
              <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="font-medium text-green-400">Invoice processed successfully</p>
                <p className="text-sm text-green-400/70">Confidence: {Math.round(result.confidence * 100)}%</p>
              </div>
            </div>
          </div>

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div role="alert" className="p-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
              <p className="font-medium text-yellow-400 mb-2">Warnings</p>
              <ul className="text-sm text-yellow-400/70 list-disc list-inside">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Invoice Details */}
          <div className="card">
            <h2 className="text-lg font-semibold text-white mb-4">Parsed Invoice</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-400">Invoice Number</p>
                <p className="text-white">{result.invoice.invoice_number || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Vendor</p>
                <p className="text-white">{result.invoice.vendor_name || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Date</p>
                <p className="text-white">{result.invoice.invoice_date || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400">Total</p>
                <p className="text-white font-semibold">
                  {result.invoice.currency} {result.invoice.total_amount?.toFixed(2) || '0.00'}
                </p>
              </div>
            </div>

            {result.invoice.line_items.length > 0 && (
              <div className="mt-6">
                <p className="text-sm text-gray-400 mb-2">Line Items ({result.invoice.line_items.length})</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-400 border-b border-dark-700">
                        <th className="pb-2" scope="col">Description</th>
                        <th className="pb-2 text-right" scope="col">Qty</th>
                        <th className="pb-2 text-right" scope="col">Price</th>
                        <th className="pb-2 text-right" scope="col">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.invoice.line_items.map((item, i) => (
                        <tr key={i} className="border-b border-dark-800">
                          <td className="py-2 text-white">{item.description}</td>
                          <td className="py-2 text-right text-gray-400">{item.quantity}</td>
                          <td className="py-2 text-right text-gray-400">{item.unit_price.toFixed(2)}</td>
                          <td className="py-2 text-right text-white">{item.total_price.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Audit Results */}
          {result.audit && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">Audit Results</h2>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    result.audit.passed
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}
                >
                  {result.audit.passed ? '\u2713 Passed' : '\u2717 Failed'}
                </span>
              </div>
              {result.audit.findings.length > 0 && (
                <ul className="space-y-2">
                  {result.audit.findings.map((finding, i) => (
                    <li
                      key={i}
                      className={`p-3 rounded-lg ${
                        finding.severity === 'error'
                          ? 'bg-red-500/10 border border-red-500/30'
                          : finding.severity === 'warning'
                            ? 'bg-yellow-500/10 border border-yellow-500/30'
                            : 'bg-blue-500/10 border border-blue-500/30'
                      }`}
                    >
                      <p className="font-medium text-white">{finding.message}</p>
                      <p className="text-xs text-gray-400 mt-1">
                        {finding.code} - {finding.category}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {result.audit.summary && (
                <p className="mt-4 text-gray-400 text-sm">{result.audit.summary}</p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-4">
            <button onClick={handleReset} className="btn btn-secondary flex-1">
              Upload Another
            </button>
            <button
              onClick={() => navigate(`/invoices/${result.invoice_id}`)}
              className="btn btn-primary flex-1"
            >
              View Invoice
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
