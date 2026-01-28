import { useEffect, useState, useCallback } from "react";
import { companyDocuments as api } from "../api/client";
import type { CompanyDocument, CreateCompanyDocumentRequest } from "../types/api";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";
import Badge from "../components/Badge";
import Modal from "../components/Modal";

const EMPTY_FORM: CreateCompanyDocumentRequest = {
  company_key: "",
  title: "",
  document_type: "other",
  expiry_date: "",
  issued_date: "",
  issuer: "",
  notes: "",
};

export default function CompanyDocuments() {
  const [docs, setDocs] = useState<CompanyDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showExpiring, setShowExpiring] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    const req = showExpiring ? api.expiring(30) : api.list({ limit: 100 });
    req
      .then((r) => {
        setDocs(r.documents);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [showExpiring]);

  useEffect(load, [load]);

  const openCreate = () => {
    setEditId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (doc: CompanyDocument) => {
    setEditId(doc.id);
    setForm({
      company_key: doc.company_key,
      title: doc.title,
      document_type: doc.document_type,
      expiry_date: doc.expiry_date ?? "",
      issued_date: doc.issued_date ?? "",
      issuer: doc.issuer ?? "",
      notes: doc.notes ?? "",
    });
    setModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = {
        ...form,
        expiry_date: form.expiry_date || undefined,
        issued_date: form.issued_date || undefined,
        issuer: form.issuer || undefined,
        notes: form.notes || undefined,
      };
      if (editId != null) {
        await api.update(editId, body);
      } else {
        await api.create(body as CreateCompanyDocumentRequest);
      }
      setModalOpen(false);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this document?")) return;
    try {
      await api.delete(id);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const setField = (key: keyof typeof form, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Company Documents</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowExpiring(!showExpiring)}
            className={`px-3 py-2 rounded text-sm transition-colors ${
              showExpiring ? "bg-yellow-600 hover:bg-yellow-500" : "bg-slate-700 hover:bg-slate-600"
            }`}
          >
            {showExpiring ? "Show All" : "Expiring Soon"}
          </button>
          <button
            onClick={openCreate}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm transition-colors"
          >
            Add Document
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <p className="text-sm text-slate-500 mb-3">
        {total} document{total !== 1 ? "s" : ""}
        {showExpiring && " expiring within 30 days"}
      </p>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="w-8 h-8" />
        </div>
      ) : docs.length === 0 ? (
        <p className="text-slate-600 text-center py-12">
          {showExpiring ? "No expiring documents." : "No documents yet."}
        </p>
      ) : (
        <div className="space-y-3">
          {docs.map((doc) => (
            <div key={doc.id} className="bg-slate-900 border border-slate-800 rounded-lg p-4 flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium truncate">{doc.title}</h3>
                  <Badge color={doc.is_expired ? "red" : doc.days_until_expiry != null && doc.days_until_expiry <= 30 ? "yellow" : "green"}>
                    {doc.is_expired
                      ? "Expired"
                      : doc.days_until_expiry != null
                        ? `${doc.days_until_expiry}d left`
                        : "No expiry"}
                  </Badge>
                </div>
                <div className="text-xs text-slate-500 space-x-3">
                  <span>Company: {doc.company_key}</span>
                  <span>Type: {doc.document_type}</span>
                  {doc.issuer && <span>Issuer: {doc.issuer}</span>}
                  {doc.expiry_date && <span>Expires: {doc.expiry_date}</span>}
                </div>
                {doc.notes && <p className="text-sm text-slate-400 mt-1">{doc.notes}</p>}
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => openEdit(doc)} className="text-xs text-blue-400 hover:text-blue-300">
                  Edit
                </button>
                <button onClick={() => handleDelete(doc.id)} className="text-xs text-red-400 hover:text-red-300">
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editId != null ? "Edit Document" : "Add Document"}>
        <form onSubmit={handleSave} className="space-y-3">
          {([
            ["company_key", "Company Key", "text", true],
            ["title", "Title", "text", true],
            ["document_type", "Document Type", "text", false],
            ["issuer", "Issuer", "text", false],
            ["issued_date", "Issued Date", "date", false],
            ["expiry_date", "Expiry Date", "date", false],
            ["notes", "Notes", "text", false],
          ] as const).map(([key, label, type, required]) => (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">{label}</label>
              <input
                type={type}
                value={form[key] ?? ""}
                onChange={(e) => setField(key, e.target.value)}
                required={required}
                className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-600"
              />
            </div>
          ))}
          <button
            type="submit"
            disabled={saving}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm transition-colors flex items-center justify-center gap-2"
          >
            {saving && <Spinner />}
            {editId != null ? "Update" : "Create"}
          </button>
        </form>
      </Modal>
    </div>
  );
}
