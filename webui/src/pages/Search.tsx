import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Link from "@mui/material/Link";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import ClearIcon from "@mui/icons-material/Clear";
import DescriptionIcon from "@mui/icons-material/Description";
import SearchIcon from "@mui/icons-material/Search";
import { search } from "../api/client";
import type { SearchResponse, SearchResult } from "../types/api";

type SearchMode = "hybrid" | "semantic" | "keyword";

interface CacheStats {
  hits?: number;
  misses?: number;
  size?: number;
}

export default function Search() {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Fetch cache stats on mount
  useEffect(() => {
    search.cacheStats().then(setCacheStats).catch(() => {
      // Silently ignore cache stats errors
    });
  }, []);

  const executeSearch = useCallback(async () => {
    if (!query.trim()) return;

    try {
      setLoading(true);
      setError(null);
      setHasSearched(true);

      const response = await search.hybrid({
        query: query.trim(),
        search_type: searchMode,
        top_k: 10,
        use_reranker: true,
        use_cache: true,
      });

      setResults(response);

      // Refresh cache stats
      search.cacheStats().then(setCacheStats).catch(() => {});
    } catch (err) {
      const message = err instanceof Error ? err.message : "Search failed";
      setError(message);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [query, searchMode]);

  const handleSearchModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newMode: SearchMode | null
  ) => {
    if (newMode !== null) {
      setSearchMode(newMode);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") {
      executeSearch();
    }
  };

  const handleClear = () => {
    setQuery("");
    setResults(null);
    setHasSearched(false);
    setError(null);
  };

  const highlightSearchTerms = (text: string, searchQuery: string): React.ReactNode => {
    if (!searchQuery.trim()) return text;

    const terms = searchQuery.toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return text;

    // Create a regex pattern that matches any of the search terms
    const pattern = new RegExp(`(${terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    const parts = text.split(pattern);

    return parts.map((part, index) => {
      const isMatch = terms.some(term => part.toLowerCase() === term);
      if (isMatch) {
        return (
          <Box
            key={index}
            component="span"
            sx={{
              backgroundColor: "warning.light",
              color: "warning.contrastText",
              px: 0.5,
              borderRadius: 0.5,
            }}
          >
            {part}
          </Box>
        );
      }
      return part;
    });
  };

  const formatScore = (score: number): string => {
    return (score * 100).toFixed(1) + "%";
  };

  const getScoreColor = (score: number): "success" | "warning" | "default" => {
    if (score >= 0.7) return "success";
    if (score >= 0.4) return "warning";
    return "default";
  };

  // Render search result card
  const renderResultCard = (result: SearchResult, index: number) => (
    <Card key={result.chunk_id || index} sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <DescriptionIcon fontSize="small" color="action" />
            <Typography variant="subtitle1" component="span" sx={{ fontWeight: 500 }}>
              {result.file_name || `Document ${result.document_id}`}
            </Typography>
            {result.page_number && (
              <Chip label={`Page ${result.page_number}`} size="small" variant="outlined" />
            )}
          </Box>
          <Chip
            label={`Score: ${formatScore(result.score)}`}
            size="small"
            color={getScoreColor(result.score)}
          />
        </Box>

        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: 2,
            display: "-webkit-box",
            WebkitLineClamp: 4,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
            lineHeight: 1.6,
          }}
        >
          {highlightSearchTerms(result.content, query)}
        </Typography>

        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Typography variant="caption" color="text.secondary">
            Chunk ID: {result.chunk_id}
          </Typography>
          <Link
            href={`/documents/${result.document_id}`}
            underline="hover"
            sx={{ fontSize: "0.875rem" }}
          >
            View Document
          </Link>
        </Box>
      </CardContent>
    </Card>
  );

  // Loading skeleton for results
  const renderLoadingSkeleton = () => (
    <Box>
      {[1, 2, 3].map((i) => (
        <Card key={i} sx={{ mb: 2 }}>
          <CardContent>
            <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
              <Skeleton variant="text" width={200} />
              <Skeleton variant="rectangular" width={80} height={24} />
            </Box>
            <Skeleton variant="text" />
            <Skeleton variant="text" />
            <Skeleton variant="text" width="60%" />
          </CardContent>
        </Card>
      ))}
    </Box>
  );

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        Search Documents
      </Typography>

      {/* Search bar */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", md: "row" } }}>
          <TextField
            fullWidth
            placeholder="Enter your search query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon color="action" />
                </InputAdornment>
              ),
              endAdornment: query && (
                <InputAdornment position="end">
                  <IconButton size="small" onClick={handleClear}>
                    <ClearIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
          <Box sx={{ display: "flex", gap: 1, flexShrink: 0 }}>
            <ToggleButtonGroup
              value={searchMode}
              exclusive
              onChange={handleSearchModeChange}
              size="small"
            >
              <ToggleButton value="hybrid">Hybrid</ToggleButton>
              <ToggleButton value="semantic">Semantic</ToggleButton>
              <ToggleButton value="keyword">Keyword</ToggleButton>
            </ToggleButtonGroup>
            <Button
              variant="contained"
              onClick={executeSearch}
              disabled={!query.trim() || loading}
              sx={{ minWidth: 100 }}
            >
              Search
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* Error state */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Results area */}
      {loading ? (
        <>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
            <Skeleton variant="text" width={150} />
          </Box>
          {renderLoadingSkeleton()}
        </>
      ) : hasSearched ? (
        results && results.results.length > 0 ? (
          <>
            {/* Results meta info */}
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Found {results.total} result{results.total !== 1 ? "s" : ""} in {results.took_ms.toFixed(0)}ms
                {results.cache_hit && (
                  <Chip label="Cache hit" size="small" color="info" sx={{ ml: 1 }} />
                )}
                {results.reranked && (
                  <Chip label="Reranked" size="small" variant="outlined" sx={{ ml: 1 }} />
                )}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Search type: {results.search_type}
              </Typography>
            </Box>

            {/* Results list */}
            {results.results.map((result, index) => renderResultCard(result, index))}
          </>
        ) : (
          /* Empty results state */
          <Paper sx={{ p: 4, textAlign: "center" }}>
            <SearchIcon sx={{ fontSize: 48, color: "text.secondary", mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No results found
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Try adjusting your search terms or changing the search mode
            </Typography>
          </Paper>
        )
      ) : (
        /* Initial state - no search yet */
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <SearchIcon sx={{ fontSize: 48, color: "text.secondary", mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Enter a search query
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Search across all indexed documents using hybrid, semantic, or keyword search
          </Typography>
        </Paper>
      )}

      {/* Cache stats */}
      {cacheStats && (
        <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: "divider" }}>
          <Typography variant="caption" color="text.secondary">
            Cache stats: {cacheStats.hits ?? 0} hits / {cacheStats.misses ?? 0} misses
            {cacheStats.size !== undefined && ` | Size: ${cacheStats.size}`}
          </Typography>
        </Box>
      )}
    </Box>
  );
}
