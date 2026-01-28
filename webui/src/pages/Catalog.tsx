import { useEffect, useState, useCallback } from "react";
import { catalog as api } from "../api/client";
import type { Material } from "../types/api";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";
import Badge from "../components/Badge";
import Modal from "../components/Modal";

export default function Catalog() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [ingestOpen, setIngestOpen] = useState(false);
  const [ingestUrl, setIngestUrl] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState("");

  const load = useCallback(
    (q?: string) => {
      setLoading(true);
      setError("");
      api
        .list({ q: q || undefined, limit: 100 })
        .then((r) => {
          setMaterials(r.materials);
          setTotal(r.total);
        })
        .catch((e: Error) => setError(e.message))
        .finally(() => setLoading(false));
    },
    [],
  );

  useEffect(() => {
    load();
  }, [load]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(search);
  };

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ingestUrl.trim()) return;
    setIngesting(true);
    setIngestMsg("");
    try {
      const res = await api.ingest({ url: ingestUrl.trim() });
      setIngestMsg(
        `${res.created ? "Created" : "Updated"}: ${res.material.name}` +
          (res.origin_country ? ` (origin: ${res.origin_country})` : ""),
      );
      setIngestUrl("");
      load(search);
    } catch (e: unknown) {
      setIngestMsg(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">Materials Catalog</h1>
        <button
          onClick={() => setIngestOpen(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm transition-colors"
        >
          Ingest from URL
        </button>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="Search materials..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-600"
        />
        <button type="submit" className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors">
          Search
        </button>
      </form>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      <p className="text-sm text-slate-500 mb-3">{total} material{total !== 1 ? "s" : ""}</p>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="w-8 h-8" />
        </div>
      ) : materials.length === 0 ? (
        <p className="text-slate-600 text-center py-12">No materials found.</p>
      ) : (
        <div className="grid gap-3">
          {materials.map((m) => (
            <div key={m.id} className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium truncate">{m.name}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {m.normalized_name}
                    {m.hs_code && <span className="ml-2">HS: {m.hs_code}</span>}
                  </p>
                  {m.synonyms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {m.synonyms.map((s) => (
                        <Badge key={s.id} color="slate">{s.synonym}</Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-right text-xs text-slate-500 shrink-0 space-y-1">
                  {m.category && <Badge color="blue">{m.category}</Badge>}
                  {m.brand && <p>Brand: {m.brand}</p>}
                  {m.origin_country && <p>Origin: {m.origin_country}</p>}
                  {m.unit && <p>Unit: {m.unit}</p>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Ingest modal */}
      <Modal open={ingestOpen} onClose={() => setIngestOpen(false)} title="Ingest Material from URL">
        <form onSubmit={handleIngest} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Product URL (Amazon)</label>
            <input
              type="url"
              value={ingestUrl}
              onChange={(e) => setIngestUrl(e.target.value)}
              placeholder="https://amazon.ae/dp/..."
              className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-600"
              required
            />
          </div>
          {ingestMsg && (
            <p className={`text-sm ${ingestMsg.startsWith("Created") || ingestMsg.startsWith("Updated") ? "text-green-400" : "text-red-400"}`}>
              {ingestMsg}
            </p>
          )}
          <button
            type="submit"
            disabled={ingesting}
            className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm transition-colors flex items-center justify-center gap-2"
          >
            {ingesting && <Spinner />}
            Ingest
          </button>
        </form>
      </Modal>
    </div>
  );
}
