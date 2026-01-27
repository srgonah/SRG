import { Link, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '@/api/client';

const navItems = [
  { path: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { path: '/upload', label: 'Upload', icon: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12' },
  { path: '/invoices', label: 'Invoices', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { path: '/search', label: 'Search', icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
  { path: '/chat', label: 'Chat', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await api.health.get();
        setIsHealthy(true);
      } catch {
        setIsHealthy(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-dark-950 flex">
      {/* Skip navigation link */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-primary-600 focus:text-white focus:rounded-lg focus:top-4 focus:left-4"
      >
        Skip to main content
      </a>

      {/* Sidebar */}
      <aside className="w-64 bg-dark-900 border-r border-dark-700 flex flex-col" aria-label="Main sidebar">
        <div className="p-6 border-b border-dark-700">
          <p className="text-xl font-bold text-white flex items-center gap-3">
            <span className="w-8 h-8 bg-gradient-to-br from-primary-500 to-purple-600 rounded-lg" aria-hidden="true"></span>
            SRG Dashboard
          </p>
        </div>

        <nav className="flex-1 p-4" aria-label="Main navigation">
          <ul className="space-y-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    aria-current={isActive ? 'page' : undefined}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-primary-600/20 text-primary-400 border border-primary-600/30'
                        : 'text-gray-400 hover:bg-dark-800 hover:text-gray-200'
                    }`}
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d={item.icon}
                      />
                    </svg>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="p-4 border-t border-dark-700">
          <div className="flex items-center gap-2 text-sm" role="status" aria-live="polite">
            <span
              className={`w-2 h-2 rounded-full ${
                isHealthy === null
                  ? 'bg-yellow-500'
                  : isHealthy
                    ? 'bg-green-500'
                    : 'bg-red-500'
              }`}
              aria-hidden="true"
            ></span>
            <span className="text-gray-400">
              {isHealthy === null ? 'Connecting...' : isHealthy ? 'Connected' : 'Offline'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main id="main-content" className="flex-1 overflow-auto">
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
