import { useEffect, useState, useCallback } from "react";
import { prices as api } from "../api/client";
import type { PriceStats, PriceHistoryEntry } from "../types/api";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";

type Tab = "stats" | "history";

export default function Prices() {
  const [tab, setTab] = useState<Tab>("stats");
  const [stats, setStats] = useState<PriceStats[]>([]);
  const [history, setHistory] = useState<PriceHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [itemFilter, setItemFilter] = useState("");

  const loadStats = useCallback(() => {
    setLoading(true);
    setError("");
    api
      .stats({ item: itemFilter || undefined })
      .then((r) => setStats(r.stats))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [itemFilter]);

  const loadHistory = useCallback(() => {
    setLoading(true);
    setError("");
    api
      .history({ item: itemFilter || undefined, limit: 200 })
      .then((r) => setHistory(r.entries))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [itemFilter]);

  useEffect(() => {
    if (tab === "stats") loadStats();
    else loadHistory();
  }, [tab, loadStats, loadHistory]);

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    if (tab === "stats") loadStats();
    else loadHistory();
  };

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">Price Intelligence</h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {(["stats", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded text-sm transition-colors ${
              tab === t ? "bg-slate-700 text-white" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            {t === "stats" ? "Price Stats" : "Price History"}
          </button>
        ))}
      </div>

      {/* Filter */}
      <form onSubmit={handleFilter} className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="Filter by item name..."
          value={itemFilter}
          onChange={(e) => setItemFilter(e.target.value)}
          className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-slate-600"
        />
        <button type="submit" className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors">
          Filter
        </button>
      </form>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="w-8 h-8" />
        </div>
      ) : tab === "stats" ? (
        stats.length === 0 ? (
          <p className="text-slate-600 text-center py-12">No price data available.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-slate-500">
                  <th className="py-2 pr-4">Item</th>
                  <th className="py-2 pr-4">Seller</th>
                  <th className="py-2 pr-4 text-right">Count</th>
                  <th className="py-2 pr-4 text-right">Min</th>
                  <th className="py-2 pr-4 text-right">Avg</th>
                  <th className="py-2 pr-4 text-right">Max</th>
                  <th className="py-2 pr-4">Trend</th>
                  <th className="py-2">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((s, i) => (
                  <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-900/50">
                    <td className="py-2 pr-4">{s.item_name}</td>
                    <td className="py-2 pr-4 text-slate-400">{s.seller_name ?? "—"}</td>
                    <td className="py-2 pr-4 text-right font-mono">{s.occurrence_count}</td>
                    <td className="py-2 pr-4 text-right font-mono">{s.min_price.toFixed(2)}</td>
                    <td className="py-2 pr-4 text-right font-mono font-medium">{s.avg_price.toFixed(2)}</td>
                    <td className="py-2 pr-4 text-right font-mono">{s.max_price.toFixed(2)}</td>
                    <td className="py-2 pr-4">
                      {s.price_trend === "up" ? (
                        <span className="text-red-400">&#9650; Up</span>
                      ) : s.price_trend === "down" ? (
                        <span className="text-green-400">&#9660; Down</span>
                      ) : (
                        <span className="text-slate-500">&#8212; Stable</span>
                      )}
                    </td>
                    <td className="py-2 text-slate-400 text-xs">{s.last_seen ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : history.length === 0 ? (
        <p className="text-slate-600 text-center py-12">No price history available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-slate-500">
                <th className="py-2 pr-4">Item</th>
                <th className="py-2 pr-4">Seller</th>
                <th className="py-2 pr-4">Date</th>
                <th className="py-2 pr-4 text-right">Qty</th>
                <th className="py-2 pr-4 text-right">Unit Price</th>
                <th className="py-2">Currency</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-900/50">
                  <td className="py-2 pr-4">{h.item_name}</td>
                  <td className="py-2 pr-4 text-slate-400">{h.seller_name ?? "—"}</td>
                  <td className="py-2 pr-4 text-slate-400">{h.invoice_date ?? "—"}</td>
                  <td className="py-2 pr-4 text-right font-mono">{h.quantity}</td>
                  <td className="py-2 pr-4 text-right font-mono">{h.unit_price.toFixed(2)}</td>
                  <td className="py-2 text-slate-400">{h.currency}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
