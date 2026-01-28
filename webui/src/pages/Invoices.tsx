import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { invoices as api } from "../api/client";
import type { Invoice } from "../types/api";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";
import Badge from "../components/Badge";

export default function Invoices() {
  const [items, setItems] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api
      .list(50, 0)
      .then((r) => {
        setItems(r.invoices);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadMsg("");
    setError("");
    try {
      const res = await api.upload(file);
      setUploadMsg(`Uploaded: ${res.invoice.invoice_number ?? res.invoice_id} (confidence: ${(res.confidence * 100).toFixed(0)}%)`);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  };

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">Invoices</h1>

      {/* Upload area */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center mb-6 transition-colors cursor-pointer ${
          dragOver ? "border-blue-500 bg-blue-500/5" : "border-slate-700 hover:border-slate-500"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        {uploading ? (
          <div className="flex items-center justify-center gap-2 text-blue-400">
            <Spinner /> Uploading...
          </div>
        ) : (
          <>
            <p className="text-slate-400 mb-1">
              Drag &amp; drop a PDF invoice here, or click to browse
            </p>
            <p className="text-xs text-slate-600">PDF files accepted</p>
          </>
        )}
        <input
          id="file-input"
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={onFileInput}
        />
      </div>

      {uploadMsg && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded px-4 py-3 text-sm mb-4">
          {uploadMsg}
        </div>
      )}

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {/* Invoice list */}
      <div className="mt-4">
        <p className="text-sm text-slate-500 mb-3">{total} invoice{total !== 1 ? "s" : ""}</p>

        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner className="w-8 h-8" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-slate-600 text-center py-12">No invoices yet. Upload one above.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-slate-500">
                  <th className="py-2 pr-4">Invoice #</th>
                  <th className="py-2 pr-4">Vendor</th>
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 pr-4 text-right">Total</th>
                  <th className="py-2 pr-4">Items</th>
                  <th className="py-2">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {items.map((inv) => (
                  <tr key={inv.id} className="border-b border-slate-800/50 hover:bg-slate-900/50">
                    <td className="py-2.5 pr-4">
                      <Link to={`/invoices/${inv.id}`} className="text-blue-400 hover:text-blue-300">
                        {inv.invoice_number ?? inv.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-4 text-slate-300">{inv.vendor_name ?? "—"}</td>
                    <td className="py-2.5 pr-4 text-slate-400">{inv.invoice_date ?? "—"}</td>
                    <td className="py-2.5 pr-4 text-right font-mono">
                      {inv.total_amount != null ? `${inv.total_amount.toLocaleString()} ${inv.currency}` : "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-slate-400">{inv.line_items.length}</td>
                    <td className="py-2.5">
                      <Badge color={inv.confidence >= 0.8 ? "green" : inv.confidence >= 0.5 ? "yellow" : "red"}>
                        {(inv.confidence * 100).toFixed(0)}%
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
