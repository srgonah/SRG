import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/api/client';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { HealthResponse, Invoice, Session } from '@/api/types';

export function DashboardPage() {
  useDocumentTitle('Dashboard');

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [healthRes, invoicesRes, sessionsRes] = await Promise.all([
          api.health.get(),
          api.invoices.list(5, 0),
          api.sessions.list(),
        ]);
        setHealth(healthRes);
        setInvoices(invoicesRes.invoices || []);
        setSessions(sessionsRes.sessions || []);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" role="status">
        <div className="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full"></div>
        <span className="sr-only">Loading dashboard data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-gray-400 mt-1">Overview of your SRG instance</p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="API Status"
          value={health?.status === 'healthy' ? 'Healthy' : 'Unhealthy'}
          icon="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          color={health?.status === 'healthy' ? 'green' : 'red'}
        />
        <StatusCard
          title="LLM Provider"
          value={health?.llm?.available ? 'Available' : 'Offline'}
          icon="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          color={health?.llm?.available ? 'green' : 'yellow'}
        />
        <StatusCard
          title="Invoices"
          value={String(invoices.length)}
          icon="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          color="blue"
        />
        <StatusCard
          title="Chat Sessions"
          value={String(sessions.length)}
          icon="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          color="purple"
        />
      </div>

      {/* Quick Actions */}
      <section aria-labelledby="quick-actions-heading">
        <h2 id="quick-actions-heading" className="sr-only">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            to="/upload"
            className="card hover:border-primary-500/50 transition-colors group"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-primary-600/20 rounded-lg flex items-center justify-center group-hover:bg-primary-600/30 transition-colors">
                <svg className="w-6 h-6 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-white">Upload Invoice</h3>
                <p className="text-sm text-gray-400">Parse and audit a new invoice</p>
              </div>
            </div>
          </Link>

          <Link
            to="/search"
            className="card hover:border-primary-500/50 transition-colors group"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-green-600/20 rounded-lg flex items-center justify-center group-hover:bg-green-600/30 transition-colors">
                <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-white">Search Documents</h3>
                <p className="text-sm text-gray-400">Find information across invoices</p>
              </div>
            </div>
          </Link>

          <Link
            to="/chat"
            className="card hover:border-primary-500/50 transition-colors group"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-purple-600/20 rounded-lg flex items-center justify-center group-hover:bg-purple-600/30 transition-colors">
                <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-white">Start Chat</h3>
                <p className="text-sm text-gray-400">Ask questions with RAG</p>
              </div>
            </div>
          </Link>
        </div>
      </section>

      {/* Recent Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Invoices */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Recent Invoices</h2>
            <Link to="/invoices" className="text-sm text-primary-400 hover:text-primary-300">
              View all
            </Link>
          </div>
          {invoices.length === 0 ? (
            <p className="text-gray-400 text-sm">No invoices yet</p>
          ) : (
            <ul className="space-y-3">
              {invoices.slice(0, 5).map((inv) => (
                <li key={inv.id}>
                  <Link
                    to={`/invoices/${inv.id}`}
                    className="flex items-center justify-between p-3 rounded-lg bg-dark-900 hover:bg-dark-700 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-white">
                        {inv.invoice_number || 'Unknown'}
                      </p>
                      <p className="text-xs text-gray-400">{inv.vendor_name || 'Unknown vendor'}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-white">
                        {inv.currency} {inv.total_amount?.toFixed(2) || '0.00'}
                      </p>
                      <p className="text-xs text-gray-400">
                        {Math.round(inv.confidence * 100)}% confidence
                      </p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Recent Sessions */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Recent Chats</h2>
            <Link to="/chat" className="text-sm text-primary-400 hover:text-primary-300">
              New chat
            </Link>
          </div>
          {sessions.length === 0 ? (
            <p className="text-gray-400 text-sm">No chat sessions yet</p>
          ) : (
            <ul className="space-y-3">
              {sessions.slice(0, 5).map((session) => (
                <li key={session.id}>
                  <Link
                    to={`/chat/${session.id}`}
                    className="flex items-center justify-between p-3 rounded-lg bg-dark-900 hover:bg-dark-700 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-white">{session.title || 'Untitled'}</p>
                      <p className="text-xs text-gray-400">{session.message_count} messages</p>
                    </div>
                    <p className="text-xs text-gray-400">
                      {new Date(session.updated_at).toLocaleDateString()}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: string;
  icon: string;
  color: 'green' | 'red' | 'yellow' | 'blue' | 'purple';
}) {
  const colorClasses = {
    green: 'bg-green-600/20 text-green-400',
    red: 'bg-red-600/20 text-red-400',
    yellow: 'bg-yellow-600/20 text-yellow-400',
    blue: 'bg-blue-600/20 text-blue-400',
    purple: 'bg-purple-600/20 text-purple-400',
  };

  return (
    <div className="card">
      <div className="flex items-center gap-4">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorClasses[color]}`}>
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
          </svg>
        </div>
        <div>
          <p className="text-sm text-gray-400">{title}</p>
          <p className="text-lg font-semibold text-white">{value}</p>
        </div>
      </div>
    </div>
  );
}
