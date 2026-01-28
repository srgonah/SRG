import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { health, invoices, reminders, companyDocuments } from "../api/client";
import type { HealthResponse, InvoiceListResponse, ReminderListResponse, CompanyDocumentListResponse } from "../types/api";
import Spinner from "../components/Spinner";

interface Stats {
  health?: HealthResponse;
  invoiceCount?: number;
  reminderCount?: number;
  expiringDocs?: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      health.check(),
      invoices.list(1, 0),
      reminders.upcoming(30, 1),
      companyDocuments.expiring(30, 1),
    ]).then(([h, inv, rem, docs]) => {
      setStats({
        health: h.status === "fulfilled" ? h.value : undefined,
        invoiceCount: inv.status === "fulfilled" ? (inv.value as InvoiceListResponse).total : undefined,
        reminderCount: rem.status === "fulfilled" ? (rem.value as ReminderListResponse).total : undefined,
        expiringDocs: docs.status === "fulfilled" ? (docs.value as CompanyDocumentListResponse).total : undefined,
      });
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  const cards: { label: string; value: string | number; to: string; color: string }[] = [
    {
      label: "System Status",
      value: stats.health?.status ?? "unknown",
      to: "/docs",
      color: stats.health?.status === "healthy" ? "border-green-500/40" : "border-red-500/40",
    },
    {
      label: "Total Invoices",
      value: stats.invoiceCount ?? "—",
      to: "/invoices",
      color: "border-blue-500/40",
    },
    {
      label: "Upcoming Reminders",
      value: stats.reminderCount ?? "—",
      to: "/reminders",
      color: "border-yellow-500/40",
    },
    {
      label: "Expiring Documents",
      value: stats.expiringDocs ?? "—",
      to: "/company-documents",
      color: stats.expiringDocs && stats.expiringDocs > 0 ? "border-red-500/40" : "border-slate-700",
    },
  ];

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((c) => (
          <Link
            key={c.label}
            to={c.to}
            className={`bg-slate-900 border ${c.color} rounded-lg p-5 hover:bg-slate-800/60 transition-colors`}
          >
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">{c.label}</p>
            <p className="text-2xl font-bold">{c.value}</p>
          </Link>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <section className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">Quick Actions</h2>
          <div className="space-y-2">
            <Link to="/invoices" className="block px-3 py-2 rounded bg-blue-600 hover:bg-blue-500 text-sm text-center transition-colors">
              Upload Invoice
            </Link>
            <Link to="/catalog" className="block px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-sm text-center transition-colors">
              Browse Catalog
            </Link>
            <Link to="/reminders" className="block px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-sm text-center transition-colors">
              View Reminders
            </Link>
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">System Info</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Version</dt>
              <dd>{stats.health?.version ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Uptime</dt>
              <dd>{stats.health ? `${Math.round(stats.health.uptime_seconds / 60)} min` : "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Database</dt>
              <dd className={stats.health?.database?.available ? "text-green-400" : "text-red-400"}>
                {stats.health?.database?.available ? "Connected" : "Unavailable"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">LLM</dt>
              <dd className={stats.health?.llm?.available ? "text-green-400" : "text-slate-500"}>
                {stats.health?.llm?.available ? "Available" : "Offline"}
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  );
}
