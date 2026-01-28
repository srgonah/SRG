import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { health } from "../api/client";

const NAV: { to: string; label: string }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/invoices", label: "Invoices" },
  { to: "/catalog", label: "Catalog" },
  { to: "/prices", label: "Prices" },
  { to: "/company-documents", label: "Documents" },
  { to: "/reminders", label: "Reminders" },
];

export default function Layout() {
  const [status, setStatus] = useState<"ok" | "err" | "loading">("loading");

  useEffect(() => {
    health
      .check()
      .then((h) => setStatus(h.status === "healthy" ? "ok" : "err"))
      .catch(() => setStatus("err"));
  }, []);

  const dot =
    status === "ok"
      ? "bg-green-500"
      : status === "err"
        ? "bg-red-500"
        : "bg-slate-500 animate-pulse";

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <NavLink to="/" className="text-lg font-semibold">
            <span className="text-blue-500">SRG</span>{" "}
            <span className="hidden sm:inline text-slate-300">Invoice Processing</span>
          </NavLink>
          <nav className="flex gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm transition-colors ${
                    isActive
                      ? "bg-slate-800 text-white"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className={`w-2 h-2 rounded-full ${dot}`} />
          {status === "ok" ? "Healthy" : status === "err" ? "Unhealthy" : "..."}
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="ml-3 text-slate-500 hover:text-blue-400 transition-colors"
          >
            API Docs
          </a>
        </div>
      </header>

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        <Outlet />
      </main>

      <footer className="text-center py-4 text-xs text-slate-600 border-t border-slate-800">
        SRG v1.0.0
      </footer>
    </div>
  );
}
