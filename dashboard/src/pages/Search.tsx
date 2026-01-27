import { useState } from 'react';
import { api } from '@/api/client';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { SearchResponse, SearchResult } from '@/api/types';

export function SearchPage() {
  useDocumentTitle('Search Documents');

  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic' | 'keyword'>('hybrid');
  const [topK, setTopK] = useState(10);
  const [useReranker, setUseReranker] = useState(true);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const res = await api.search.query({
        query: query.trim(),
        top_k: topK,
        search_type: searchType,
        use_reranker: useReranker,
      });
      setResults(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Search Documents</h1>
        <p className="text-gray-400 mt-1">Find information across your indexed invoices and documents</p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="card" role="search" aria-label="Document search">
        <div className="flex gap-4">
          <div className="flex-1">
            <label htmlFor="search-query" className="sr-only">Search documents</label>
            <input
              id="search-query"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for invoices, vendors, items..."
              className="input text-lg"
              aria-label="Search documents"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="btn btn-primary px-8 disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Options */}
        <div className="flex flex-wrap items-center gap-6 mt-4 pt-4 border-t border-dark-700">
          <div className="flex items-center gap-2">
            <label htmlFor="search-type" className="text-sm text-gray-400">Type:</label>
            <select
              id="search-type"
              value={searchType}
              onChange={(e) => setSearchType(e.target.value as typeof searchType)}
              className="bg-dark-900 border border-dark-700 rounded px-3 py-1 text-sm text-gray-300"
            >
              <option value="hybrid">Hybrid</option>
              <option value="semantic">Semantic</option>
              <option value="keyword">Keyword</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label htmlFor="search-results-count" className="text-sm text-gray-400">Results:</label>
            <select
              id="search-results-count"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="bg-dark-900 border border-dark-700 rounded px-3 py-1 text-sm text-gray-300"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useReranker}
              onChange={(e) => setUseReranker(e.target.checked)}
              className="w-4 h-4 accent-primary-500"
            />
            <span className="text-sm text-gray-400">Use Reranker</span>
          </label>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div role="alert" className="p-4 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-4" aria-live="polite">
          {/* Stats */}
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <span>{results.total} results</span>
            <span>in {results.took_ms.toFixed(0)}ms</span>
            <span>{results.search_type} search</span>
            {results.reranked && <span className="text-primary-400">reranked</span>}
            {results.cache_hit && <span className="text-green-400">cached</span>}
          </div>

          {/* Results List */}
          {results.results.length === 0 ? (
            <div className="card text-center py-12">
              <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <p className="text-gray-400">No results found for &ldquo;{results.query}&rdquo;</p>
            </div>
          ) : (
            <div className="space-y-4">
              {results.results.map((result, i) => (
                <SearchResultCard key={result.chunk_id} result={result} rank={i + 1} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Initial State */}
      {!results && !error && (
        <div className="card text-center py-16">
          <svg className="w-20 h-20 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p className="text-gray-400 text-lg">Enter a search query to find documents</p>
          <p className="text-gray-400 text-sm mt-2">
            Try searching for vendor names, product descriptions, or invoice numbers
          </p>
        </div>
      )}
    </div>
  );
}

function SearchResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card hover:border-dark-600 transition-colors">
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 w-8 h-8 bg-dark-700 rounded-full flex items-center justify-center text-sm font-medium text-gray-400" aria-hidden="true">
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <p className="font-medium text-white">{result.file_name || 'Unknown document'}</p>
              {result.page_number && (
                <span className="text-xs text-gray-400 bg-dark-700 px-2 py-0.5 rounded">
                  Page {result.page_number}
                </span>
              )}
            </div>
            <span
              className={`text-sm font-medium ${
                result.score >= 0.8
                  ? 'text-green-400'
                  : result.score >= 0.5
                    ? 'text-yellow-400'
                    : 'text-gray-400'
              }`}
              aria-label={`Relevance score: ${Math.round(result.score * 100)}%`}
            >
              {Math.round(result.score * 100)}%
            </span>
          </div>

          <div className={`text-gray-400 text-sm ${expanded ? '' : 'line-clamp-3'}`}>
            {result.highlight || result.content}
          </div>

          {result.content.length > 200 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-primary-400 text-xs mt-2 hover:text-primary-300"
              aria-expanded={expanded}
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}

          {/* Metadata */}
          {Object.keys(result.metadata).length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {Object.entries(result.metadata).slice(0, 4).map(([key, value]) => (
                <span
                  key={key}
                  className="text-xs bg-dark-700 text-gray-400 px-2 py-1 rounded"
                >
                  {key}: {String(value)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
