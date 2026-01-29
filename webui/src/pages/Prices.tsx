import { useEffect, useState, useCallback } from "react";
import { prices as api } from "../api/client";
import type { PriceStats, PriceHistoryEntry } from "../types/api";

// MUI imports
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TableSortLabel from "@mui/material/TableSortLabel";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import InputAdornment from "@mui/material/InputAdornment";

// MUI icons
import SearchIcon from "@mui/icons-material/Search";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import TrendingFlatIcon from "@mui/icons-material/TrendingFlat";

type TabValue = "stats" | "history";

type SortDirection = "asc" | "desc";

interface StatsSort {
  field: keyof PriceStats;
  direction: SortDirection;
}

interface HistorySort {
  field: keyof PriceHistoryEntry;
  direction: SortDirection;
}

export default function Prices() {
  const [tab, setTab] = useState<TabValue>("stats");

  // Stats state
  const [stats, setStats] = useState<PriceStats[]>([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");
  const [statsFilter, setStatsFilter] = useState("");
  const [statsSort, setStatsSort] = useState<StatsSort>({
    field: "item_name",
    direction: "asc",
  });

  // History state
  const [history, setHistory] = useState<PriceHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [historyFilter, setHistoryFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [historySort, setHistorySort] = useState<HistorySort>({
    field: "invoice_date",
    direction: "desc",
  });

  const loadStats = useCallback(() => {
    setStatsLoading(true);
    setStatsError("");
    api
      .stats({ item: statsFilter || undefined })
      .then((r) => setStats(r.stats))
      .catch((e: Error) => setStatsError(e.message))
      .finally(() => setStatsLoading(false));
  }, [statsFilter]);

  const loadHistory = useCallback(() => {
    setHistoryLoading(true);
    setHistoryError("");
    api
      .history({
        item: historyFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 200,
      })
      .then((r) => setHistory(r.entries))
      .catch((e: Error) => setHistoryError(e.message))
      .finally(() => setHistoryLoading(false));
  }, [historyFilter, dateFrom, dateTo]);

  useEffect(() => {
    if (tab === "stats") {
      loadStats();
    } else {
      loadHistory();
    }
  }, [tab, loadStats, loadHistory]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: TabValue) => {
    setTab(newValue);
  };

  const handleStatsFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadStats();
  };

  const handleHistoryFilterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadHistory();
  };

  // Stats sorting
  const handleStatsSort = (field: keyof PriceStats) => {
    setStatsSort((prev) => ({
      field,
      direction: prev.field === field && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const sortedStats = [...stats].sort((a, b) => {
    const { field, direction } = statsSort;
    const aVal = a[field];
    const bVal = b[field];

    if (aVal === undefined || aVal === null) return 1;
    if (bVal === undefined || bVal === null) return -1;

    let comparison = 0;
    if (typeof aVal === "string" && typeof bVal === "string") {
      comparison = aVal.localeCompare(bVal);
    } else if (typeof aVal === "number" && typeof bVal === "number") {
      comparison = aVal - bVal;
    }

    return direction === "asc" ? comparison : -comparison;
  });

  // History sorting
  const handleHistorySort = (field: keyof PriceHistoryEntry) => {
    setHistorySort((prev) => ({
      field,
      direction: prev.field === field && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const sortedHistory = [...history].sort((a, b) => {
    const { field, direction } = historySort;
    const aVal = a[field];
    const bVal = b[field];

    if (aVal === undefined || aVal === null) return 1;
    if (bVal === undefined || bVal === null) return -1;

    let comparison = 0;
    if (typeof aVal === "string" && typeof bVal === "string") {
      comparison = aVal.localeCompare(bVal);
    } else if (typeof aVal === "number" && typeof bVal === "number") {
      comparison = aVal - bVal;
    }

    return direction === "asc" ? comparison : -comparison;
  });

  // Render skeleton rows
  const renderStatsSkeletonRows = () => {
    return Array.from({ length: 5 }).map((_, idx) => (
      <TableRow key={idx}>
        <TableCell>
          <Skeleton variant="text" width="80%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="60%" />
        </TableCell>
        <TableCell align="right">
          <Skeleton variant="text" width="40px" />
        </TableCell>
        <TableCell align="right">
          <Skeleton variant="text" width="60px" />
        </TableCell>
        <TableCell align="right">
          <Skeleton variant="text" width="60px" />
        </TableCell>
        <TableCell align="right">
          <Skeleton variant="text" width="60px" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="60px" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="80px" />
        </TableCell>
      </TableRow>
    ));
  };

  const renderHistorySkeletonRows = () => {
    return Array.from({ length: 5 }).map((_, idx) => (
      <TableRow key={idx}>
        <TableCell>
          <Skeleton variant="text" width="80%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="60%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="80px" />
        </TableCell>
        <TableCell align="right">
          <Skeleton variant="text" width="40px" />
        </TableCell>
        <TableCell align="right">
          <Skeleton variant="text" width="60px" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="40px" />
        </TableCell>
      </TableRow>
    ));
  };

  // Trend icon component
  const TrendIcon = ({ trend }: { trend: string | undefined }) => {
    if (trend === "up") {
      return (
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.5,
            color: "error.main",
          }}
        >
          <TrendingUpIcon fontSize="small" />
          <Typography variant="body2" color="error.main">
            Up
          </Typography>
        </Box>
      );
    }
    if (trend === "down") {
      return (
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.5,
            color: "success.main",
          }}
        >
          <TrendingDownIcon fontSize="small" />
          <Typography variant="body2" color="success.main">
            Down
          </Typography>
        </Box>
      );
    }
    return (
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          color: "text.secondary",
        }}
      >
        <TrendingFlatIcon fontSize="small" />
        <Typography variant="body2" color="text.secondary">
          Stable
        </Typography>
      </Box>
    );
  };

  return (
    <Box>
      <Typography variant="h5" component="h1" fontWeight={600} sx={{ mb: 3 }}>
        Price Intelligence
      </Typography>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: "divider", mb: 3 }}>
        <Tabs value={tab} onChange={handleTabChange}>
          <Tab label="Price Stats" value="stats" />
          <Tab label="Price History" value="history" />
        </Tabs>
      </Box>

      {/* Stats Tab */}
      {tab === "stats" && (
        <Box>
          {/* Filter */}
          <Box
            component="form"
            onSubmit={handleStatsFilterSubmit}
            sx={{ mb: 3 }}
          >
            <TextField
              fullWidth
              placeholder="Filter by item name..."
              value={statsFilter}
              onChange={(e) => setStatsFilter(e.target.value)}
              size="small"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
              }}
            />
          </Box>

          {/* Error alert */}
          {statsError && (
            <Alert
              severity="error"
              onClose={() => setStatsError("")}
              sx={{ mb: 2 }}
            >
              {statsError}
            </Alert>
          )}

          {/* Stats table */}
          {statsLoading ? (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Item</TableCell>
                    <TableCell>Seller</TableCell>
                    <TableCell align="right">Count</TableCell>
                    <TableCell align="right">Min</TableCell>
                    <TableCell align="right">Avg</TableCell>
                    <TableCell align="right">Max</TableCell>
                    <TableCell>Trend</TableCell>
                    <TableCell>Last Seen</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>{renderStatsSkeletonRows()}</TableBody>
              </Table>
            </TableContainer>
          ) : stats.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Typography color="text.secondary">
                No price data available.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>
                      <TableSortLabel
                        active={statsSort.field === "item_name"}
                        direction={
                          statsSort.field === "item_name"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("item_name")}
                      >
                        Item
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>
                      <TableSortLabel
                        active={statsSort.field === "seller_name"}
                        direction={
                          statsSort.field === "seller_name"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("seller_name")}
                      >
                        Seller
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={statsSort.field === "occurrence_count"}
                        direction={
                          statsSort.field === "occurrence_count"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("occurrence_count")}
                      >
                        Count
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={statsSort.field === "min_price"}
                        direction={
                          statsSort.field === "min_price"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("min_price")}
                      >
                        Min
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={statsSort.field === "avg_price"}
                        direction={
                          statsSort.field === "avg_price"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("avg_price")}
                      >
                        Avg
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={statsSort.field === "max_price"}
                        direction={
                          statsSort.field === "max_price"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("max_price")}
                      >
                        Max
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>Trend</TableCell>
                    <TableCell>
                      <TableSortLabel
                        active={statsSort.field === "last_seen"}
                        direction={
                          statsSort.field === "last_seen"
                            ? statsSort.direction
                            : "asc"
                        }
                        onClick={() => handleStatsSort("last_seen")}
                      >
                        Last Seen
                      </TableSortLabel>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sortedStats.map((s, i) => (
                    <TableRow key={i} hover>
                      <TableCell>{s.item_name}</TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {s.seller_name ?? "-"}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: "monospace" }}
                        >
                          {s.occurrence_count}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: "monospace" }}
                        >
                          {s.min_price.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          sx={{ fontFamily: "monospace" }}
                        >
                          {s.avg_price.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: "monospace" }}
                        >
                          {s.max_price.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <TrendIcon trend={s.price_trend} />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {s.last_seen ?? "-"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}

      {/* History Tab */}
      {tab === "history" && (
        <Box>
          {/* Filters */}
          <Box
            component="form"
            onSubmit={handleHistoryFilterSubmit}
            sx={{
              display: "flex",
              flexDirection: { xs: "column", sm: "row" },
              gap: 2,
              mb: 3,
            }}
          >
            <TextField
              placeholder="Filter by item name..."
              value={historyFilter}
              onChange={(e) => setHistoryFilter(e.target.value)}
              size="small"
              sx={{ flexGrow: 1 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              type="date"
              label="From"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: { xs: "100%", sm: 160 } }}
            />
            <TextField
              type="date"
              label="To"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              size="small"
              InputLabelProps={{ shrink: true }}
              sx={{ width: { xs: "100%", sm: 160 } }}
            />
          </Box>

          {/* Error alert */}
          {historyError && (
            <Alert
              severity="error"
              onClose={() => setHistoryError("")}
              sx={{ mb: 2 }}
            >
              {historyError}
            </Alert>
          )}

          {/* History table */}
          {historyLoading ? (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Item</TableCell>
                    <TableCell>Seller</TableCell>
                    <TableCell>Date</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Unit Price</TableCell>
                    <TableCell>Currency</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>{renderHistorySkeletonRows()}</TableBody>
              </Table>
            </TableContainer>
          ) : history.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
              <Typography color="text.secondary">
                No price history available.
              </Typography>
            </Paper>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>
                      <TableSortLabel
                        active={historySort.field === "item_name"}
                        direction={
                          historySort.field === "item_name"
                            ? historySort.direction
                            : "asc"
                        }
                        onClick={() => handleHistorySort("item_name")}
                      >
                        Item
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>
                      <TableSortLabel
                        active={historySort.field === "seller_name"}
                        direction={
                          historySort.field === "seller_name"
                            ? historySort.direction
                            : "asc"
                        }
                        onClick={() => handleHistorySort("seller_name")}
                      >
                        Seller
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>
                      <TableSortLabel
                        active={historySort.field === "invoice_date"}
                        direction={
                          historySort.field === "invoice_date"
                            ? historySort.direction
                            : "asc"
                        }
                        onClick={() => handleHistorySort("invoice_date")}
                      >
                        Date
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={historySort.field === "quantity"}
                        direction={
                          historySort.field === "quantity"
                            ? historySort.direction
                            : "asc"
                        }
                        onClick={() => handleHistorySort("quantity")}
                      >
                        Qty
                      </TableSortLabel>
                    </TableCell>
                    <TableCell align="right">
                      <TableSortLabel
                        active={historySort.field === "unit_price"}
                        direction={
                          historySort.field === "unit_price"
                            ? historySort.direction
                            : "asc"
                        }
                        onClick={() => handleHistorySort("unit_price")}
                      >
                        Unit Price
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>
                      <TableSortLabel
                        active={historySort.field === "currency"}
                        direction={
                          historySort.field === "currency"
                            ? historySort.direction
                            : "asc"
                        }
                        onClick={() => handleHistorySort("currency")}
                      >
                        Currency
                      </TableSortLabel>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {sortedHistory.map((h, i) => (
                    <TableRow key={i} hover>
                      <TableCell>{h.item_name}</TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {h.seller_name ?? "-"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {h.invoice_date ?? "-"}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: "monospace" }}
                        >
                          {h.quantity}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          sx={{ fontFamily: "monospace" }}
                        >
                          {h.unit_price.toFixed(2)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {h.currency}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}
    </Box>
  );
}
