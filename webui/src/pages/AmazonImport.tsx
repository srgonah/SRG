import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import FormControl from "@mui/material/FormControl";
import Grid from "@mui/material/Grid2";
import InputLabel from "@mui/material/InputLabel";
import LinearProgress from "@mui/material/LinearProgress";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import Snackbar from "@mui/material/Snackbar";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CloudDownloadIcon from "@mui/icons-material/CloudDownload";
import ErrorIcon from "@mui/icons-material/Error";
import PreviewIcon from "@mui/icons-material/Preview";
import SearchIcon from "@mui/icons-material/Search";
import SkipNextIcon from "@mui/icons-material/SkipNext";
import { amazonImport } from "../api/client";
import type { AmazonImportItem, AmazonImportResponse } from "../types/api";

interface SnackbarState {
  open: boolean;
  message: string;
  severity: "success" | "error" | "info" | "warning";
}

export default function AmazonImport() {
  // Form state
  const [categories, setCategories] = useState<Record<string, string[]>>({});
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedSubcategory, setSelectedSubcategory] = useState("all");
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(20);
  const [unit, setUnit] = useState("");

  // Results state
  const [results, setResults] = useState<AmazonImportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Snackbar
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: "",
    severity: "info",
  });

  // Fetch categories on mount
  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await amazonImport.categories();
        setCategories(response.categories);
        // Set default category
        const cats = Object.keys(response.categories);
        const firstCat = cats[0];
        if (firstCat) {
          setSelectedCategory(firstCat);
        }
      } catch (err) {
        console.error("Failed to load categories:", err);
      }
    };
    fetchCategories();
  }, []);

  // Get subcategories for selected category
  const subcategories = categories[selectedCategory] || [];

  // Handle preview
  const handlePreview = useCallback(async () => {
    if (!selectedCategory) {
      setError("Please select a category");
      return;
    }

    setError(null);
    setPreviewing(true);
    setResults(null);

    try {
      const response = await amazonImport.preview({
        category: selectedCategory,
        subcategory: selectedSubcategory,
        query: query || undefined,
        limit,
        unit: unit || undefined,
      });

      setResults(response);

      if (response.items_found === 0) {
        setSnackbar({
          open: true,
          message: "No products found for this search",
          severity: "warning",
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Preview failed";
      setError(message);
    } finally {
      setPreviewing(false);
    }
  }, [selectedCategory, selectedSubcategory, query, limit, unit]);

  // Handle import
  const handleImport = useCallback(async () => {
    if (!selectedCategory) {
      setError("Please select a category");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const response = await amazonImport.import({
        category: selectedCategory,
        subcategory: selectedSubcategory,
        query: query || undefined,
        limit,
        unit: unit || undefined,
      });

      setResults(response);

      setSnackbar({
        open: true,
        message: `Imported ${response.items_saved} materials (${response.items_skipped} duplicates skipped)`,
        severity: "success",
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Import failed";
      setError(message);
      setSnackbar({
        open: true,
        message,
        severity: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, selectedSubcategory, query, limit, unit]);

  // Get status chip for item
  const getStatusChip = (item: AmazonImportItem) => {
    switch (item.status) {
      case "saved":
        return (
          <Chip
            icon={<CheckCircleIcon />}
            label="Saved"
            color="success"
            size="small"
          />
        );
      case "skipped_duplicate":
        return (
          <Chip
            icon={<SkipNextIcon />}
            label="Duplicate"
            color="warning"
            size="small"
          />
        );
      case "error":
        return (
          <Chip
            icon={<ErrorIcon />}
            label="Error"
            color="error"
            size="small"
          />
        );
      case "pending":
        return (
          <Chip
            label="Will Import"
            color="info"
            size="small"
            variant="outlined"
          />
        );
      default:
        return <Chip label={item.status} size="small" />;
    }
  };

  const handleSnackbarClose = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        Amazon Import
      </Typography>

      {/* Form */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Grid container spacing={3}>
          {/* Category */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel>Category</InputLabel>
              <Select
                value={selectedCategory}
                label="Category"
                onChange={(e) => {
                  setSelectedCategory(e.target.value);
                  setSelectedSubcategory("all");
                }}
              >
                {Object.keys(categories).map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {cat}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Subcategory */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel>Subcategory</InputLabel>
              <Select
                value={selectedSubcategory}
                label="Subcategory"
                onChange={(e) => setSelectedSubcategory(e.target.value)}
              >
                {subcategories.map((sub) => (
                  <MenuItem key={sub} value={sub}>
                    {sub}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          {/* Search Query */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              label="Search Query (optional)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., cable, safety gloves"
            />
          </Grid>

          {/* Limit */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              type="number"
              label="Limit"
              value={limit}
              onChange={(e) => setLimit(Math.min(50, Math.max(1, parseInt(e.target.value) || 20)))}
              inputProps={{ min: 1, max: 50 }}
            />
          </Grid>

          {/* Unit */}
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <FormControl fullWidth>
              <InputLabel>Unit (optional)</InputLabel>
              <Select
                value={unit}
                label="Unit (optional)"
                onChange={(e) => setUnit(e.target.value)}
              >
                <MenuItem value="">None</MenuItem>
                <MenuItem value="PCS">PCS</MenuItem>
                <MenuItem value="M">M (Meter)</MenuItem>
                <MenuItem value="KG">KG</MenuItem>
                <MenuItem value="L">L (Liter)</MenuItem>
                <MenuItem value="SET">SET</MenuItem>
                <MenuItem value="BOX">BOX</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          {/* Buttons */}
          <Grid size={{ xs: 12, sm: 6, md: 6 }}>
            <Box sx={{ display: "flex", gap: 2, height: "100%", alignItems: "center" }}>
              <Button
                variant="outlined"
                startIcon={previewing ? <CircularProgress size={20} /> : <PreviewIcon />}
                onClick={handlePreview}
                disabled={loading || previewing || !selectedCategory}
              >
                Preview
              </Button>
              <Button
                variant="contained"
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <CloudDownloadIcon />}
                onClick={handleImport}
                disabled={loading || previewing || !selectedCategory}
              >
                Import
              </Button>
            </Box>
          </Grid>
        </Grid>

        {/* Progress indicator */}
        {(loading || previewing) && (
          <LinearProgress sx={{ mt: 2 }} />
        )}
      </Paper>

      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Results summary */}
      {results && (
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Found
                </Typography>
                <Typography variant="h4">{results.items_found}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Saved
                </Typography>
                <Typography variant="h4" color="success.main">
                  {results.items_saved}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Skipped (Duplicates)
                </Typography>
                <Typography variant="h4" color="warning.main">
                  {results.items_skipped}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Errors
                </Typography>
                <Typography variant="h4" color="error.main">
                  {results.items_error}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Results table */}
      {results && results.items.length > 0 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>ASIN</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Brand</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Material ID</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {results.items.map((item) => (
                <TableRow key={item.asin} hover>
                  <TableCell>
                    <Link
                      href={item.product_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{ fontFamily: "monospace" }}
                    >
                      {item.asin}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 300 }}>
                      {item.title}
                    </Typography>
                  </TableCell>
                  <TableCell>{item.brand || "-"}</TableCell>
                  <TableCell align="right">
                    {item.price || "-"}
                  </TableCell>
                  <TableCell>{getStatusChip(item)}</TableCell>
                  <TableCell>
                    {item.material_id ? (
                      <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                        {item.material_id.substring(0, 8)}...
                      </Typography>
                    ) : item.existing_material_id ? (
                      <Typography variant="body2" color="text.secondary" sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                        (existing: {item.existing_material_id.substring(0, 8)}...)
                      </Typography>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Empty state */}
      {results && results.items.length === 0 && (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <SearchIcon sx={{ fontSize: 48, color: "text.secondary", mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No products found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your search criteria
          </Typography>
        </Paper>
      )}

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: "100%" }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
