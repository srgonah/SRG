import { useEffect, useState, useCallback } from "react";
import { catalog as api } from "../api/client";
import type {
  Material,
  PreviewIngestResponse,
  BatchIngestItemResult,
} from "../types/api";
import Modal from "../components/Modal";

// MUI imports
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Skeleton from "@mui/material/Skeleton";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import Divider from "@mui/material/Divider";
import CircularProgress from "@mui/material/CircularProgress";

// MUI icons
import SearchIcon from "@mui/icons-material/Search";
import AddLinkIcon from "@mui/icons-material/AddLink";
import PlaylistAddIcon from "@mui/icons-material/PlaylistAdd";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import CloseIcon from "@mui/icons-material/Close";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";

export default function Catalog() {
  // Materials state
  const [materials, setMaterials] = useState<Material[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  // Detail drawer state
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Ingest from URL dialog state
  const [ingestOpen, setIngestOpen] = useState(false);
  const [ingestUrl, setIngestUrl] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState("");
  const [ingestMsgType, setIngestMsgType] = useState<"success" | "error">("success");
  const [previewData, setPreviewData] = useState<PreviewIngestResponse | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // Batch ingest dialog state
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchUrls, setBatchUrls] = useState("");
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchResults, setBatchResults] = useState<BatchIngestItemResult[]>([]);

  // Export menu state
  const [exportAnchor, setExportAnchor] = useState<HTMLElement | null>(null);

  const load = useCallback((q?: string) => {
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
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(search);
  };

  const handleRowClick = (material: Material) => {
    setSelectedMaterial(material);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
    setSelectedMaterial(null);
  };

  // Preview ingest
  const handlePreview = async () => {
    if (!ingestUrl.trim()) return;
    setPreviewing(true);
    setPreviewData(null);
    setIngestMsg("");
    try {
      const preview = await api.ingestPreview(ingestUrl.trim());
      setPreviewData(preview);
    } catch (e: unknown) {
      setIngestMsg(e instanceof Error ? e.message : "Preview failed");
      setIngestMsgType("error");
    } finally {
      setPreviewing(false);
    }
  };

  // Import (ingest)
  const handleIngest = async () => {
    if (!ingestUrl.trim()) return;
    setIngesting(true);
    setIngestMsg("");
    try {
      const res = await api.ingest({ url: ingestUrl.trim() });
      setIngestMsg(
        `${res.created ? "Created" : "Updated"}: ${res.material.name}` +
          (res.origin_country ? ` (origin: ${res.origin_country})` : "")
      );
      setIngestMsgType("success");
      setIngestUrl("");
      setPreviewData(null);
      load(search);
    } catch (e: unknown) {
      setIngestMsg(e instanceof Error ? e.message : "Ingest failed");
      setIngestMsgType("error");
    } finally {
      setIngesting(false);
    }
  };

  const handleCloseIngestDialog = () => {
    setIngestOpen(false);
    setIngestUrl("");
    setIngestMsg("");
    setPreviewData(null);
  };

  // Batch ingest
  const handleBatchIngest = async () => {
    const urls = batchUrls
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u.length > 0);
    if (urls.length === 0) return;

    setBatchLoading(true);
    setBatchResults([]);
    try {
      const res = await api.ingestBatch(urls);
      setBatchResults(res.results);
      load(search);
    } catch (e: unknown) {
      setBatchResults([
        {
          url: "batch",
          status: "error",
          error: e instanceof Error ? e.message : "Batch ingest failed",
        },
      ]);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleCloseBatchDialog = () => {
    setBatchOpen(false);
    setBatchUrls("");
    setBatchResults([]);
  };

  // Export handlers
  const handleExportClick = (event: React.MouseEvent<HTMLElement>) => {
    setExportAnchor(event.currentTarget);
  };

  const handleExportClose = () => {
    setExportAnchor(null);
  };

  const handleExportJson = async () => {
    handleExportClose();
    try {
      const data = await api.exportJson();
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "catalog.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  const handleExportCsv = async () => {
    handleExportClose();
    try {
      const blob = await api.exportCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "catalog.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  // Render skeleton rows for loading state
  const renderSkeletonRows = () => {
    return Array.from({ length: 5 }).map((_, idx) => (
      <TableRow key={idx}>
        <TableCell>
          <Skeleton variant="text" width="80%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="60%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="50%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="40%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="60%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="text" width="30%" />
        </TableCell>
        <TableCell>
          <Skeleton variant="rectangular" width={100} height={24} />
        </TableCell>
      </TableRow>
    ));
  };

  return (
    <Box>
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          mb: 3,
        }}
      >
        <Typography variant="h5" component="h1" fontWeight={600}>
          Materials Catalog
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddLinkIcon />}
            onClick={() => setIngestOpen(true)}
          >
            Ingest from URL
          </Button>
          <Button
            variant="outlined"
            startIcon={<PlaylistAddIcon />}
            onClick={() => setBatchOpen(true)}
          >
            Batch Ingest
          </Button>
          <Button
            variant="outlined"
            startIcon={<FileDownloadIcon />}
            onClick={handleExportClick}
          >
            Export
          </Button>
          <Menu
            anchorEl={exportAnchor}
            open={Boolean(exportAnchor)}
            onClose={handleExportClose}
          >
            <MenuItem onClick={handleExportJson}>Export as JSON</MenuItem>
            <MenuItem onClick={handleExportCsv}>Export as CSV</MenuItem>
          </Menu>
        </Box>
      </Box>

      {/* Search bar */}
      <Box component="form" onSubmit={handleSearch} sx={{ mb: 3 }}>
        <TextField
          fullWidth
          placeholder="Search materials..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
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
      {error && (
        <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Total count */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {total} material{total !== 1 ? "s" : ""}
      </Typography>

      {/* Materials table */}
      {loading ? (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Brand</TableCell>
                <TableCell>Origin Country</TableCell>
                <TableCell>HS Code</TableCell>
                <TableCell>Unit</TableCell>
                <TableCell>Synonyms</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>{renderSkeletonRows()}</TableBody>
          </Table>
        </TableContainer>
      ) : materials.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 6, textAlign: "center" }}>
          <Typography color="text.secondary">No materials found.</Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Brand</TableCell>
                <TableCell>Origin Country</TableCell>
                <TableCell>HS Code</TableCell>
                <TableCell>Unit</TableCell>
                <TableCell>Synonyms</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {materials.map((m) => (
                <TableRow
                  key={m.id}
                  hover
                  onClick={() => handleRowClick(m)}
                  sx={{ cursor: "pointer" }}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {m.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {m.normalized_name}
                    </Typography>
                  </TableCell>
                  <TableCell>{m.category ?? "-"}</TableCell>
                  <TableCell>{m.brand ?? "-"}</TableCell>
                  <TableCell>{m.origin_country ?? "-"}</TableCell>
                  <TableCell>{m.hs_code ?? "-"}</TableCell>
                  <TableCell>{m.unit ?? "-"}</TableCell>
                  <TableCell>
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                      {m.synonyms.slice(0, 3).map((s) => (
                        <Chip
                          key={s.id}
                          label={s.synonym}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                      {m.synonyms.length > 3 && (
                        <Chip
                          label={`+${m.synonyms.length - 3}`}
                          size="small"
                          color="default"
                        />
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Material detail drawer */}
      <Drawer anchor="right" open={drawerOpen} onClose={handleCloseDrawer}>
        <Box sx={{ width: 400, p: 3 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              mb: 2,
            }}
          >
            <Typography variant="h6">Material Details</Typography>
            <IconButton onClick={handleCloseDrawer} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
          <Divider sx={{ mb: 2 }} />

          {selectedMaterial && (
            <Box>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                {selectedMaterial.name}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                gutterBottom
              >
                {selectedMaterial.normalized_name}
              </Typography>

              <List dense>
                <ListItem disableGutters>
                  <ListItemText
                    primary="ID"
                    secondary={selectedMaterial.id}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Category"
                    secondary={selectedMaterial.category ?? "-"}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Brand"
                    secondary={selectedMaterial.brand ?? "-"}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Origin Country"
                    secondary={selectedMaterial.origin_country ?? "-"}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Origin Confidence"
                    secondary={selectedMaterial.origin_confidence}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="HS Code"
                    secondary={selectedMaterial.hs_code ?? "-"}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Unit"
                    secondary={selectedMaterial.unit ?? "-"}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Description"
                    secondary={selectedMaterial.description ?? "-"}
                  />
                </ListItem>
                {selectedMaterial.source_url && (
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Source URL"
                      secondary={
                        <Typography
                          variant="body2"
                          component="a"
                          href={selectedMaterial.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          sx={{ color: "primary.main" }}
                        >
                          {selectedMaterial.source_url}
                        </Typography>
                      }
                    />
                  </ListItem>
                )}
                <ListItem disableGutters>
                  <ListItemText
                    primary="Created At"
                    secondary={new Date(
                      selectedMaterial.created_at
                    ).toLocaleString()}
                  />
                </ListItem>
                <ListItem disableGutters>
                  <ListItemText
                    primary="Updated At"
                    secondary={new Date(
                      selectedMaterial.updated_at
                    ).toLocaleString()}
                  />
                </ListItem>
              </List>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" gutterBottom>
                Synonyms ({selectedMaterial.synonyms.length})
              </Typography>
              {selectedMaterial.synonyms.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No synonyms
                </Typography>
              ) : (
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                  {selectedMaterial.synonyms.map((s) => (
                    <Chip
                      key={s.id}
                      label={`${s.synonym} (${s.language})`}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                </Box>
              )}
            </Box>
          )}
        </Box>
      </Drawer>

      {/* Ingest from URL dialog */}
      <Modal
        open={ingestOpen}
        title="Ingest Material from URL"
        onClose={handleCloseIngestDialog}
        actions={
          <>
            <Button onClick={handleCloseIngestDialog}>Cancel</Button>
            <Button
              onClick={handlePreview}
              disabled={previewing || !ingestUrl.trim()}
              startIcon={
                previewing ? <CircularProgress size={16} /> : undefined
              }
            >
              Preview
            </Button>
            <Button
              variant="contained"
              onClick={handleIngest}
              disabled={ingesting || !ingestUrl.trim()}
              startIcon={
                ingesting ? <CircularProgress size={16} /> : undefined
              }
            >
              Import
            </Button>
          </>
        }
      >
        <TextField
          fullWidth
          label="Product URL"
          placeholder="https://amazon.ae/dp/..."
          value={ingestUrl}
          onChange={(e) => setIngestUrl(e.target.value)}
          size="small"
          sx={{ mb: 2 }}
        />

        {ingestMsg && (
          <Alert
            severity={ingestMsgType}
            sx={{ mb: 2 }}
            onClose={() => setIngestMsg("")}
          >
            {ingestMsg}
          </Alert>
        )}

        {previewData && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Preview Data
            </Typography>
            <List dense>
              <ListItem disableGutters>
                <ListItemText primary="Title" secondary={previewData.title} />
              </ListItem>
              {previewData.brand && (
                <ListItem disableGutters>
                  <ListItemText primary="Brand" secondary={previewData.brand} />
                </ListItem>
              )}
              {previewData.category && (
                <ListItem disableGutters>
                  <ListItemText
                    primary="Category"
                    secondary={previewData.category}
                  />
                </ListItem>
              )}
              {previewData.origin_country && (
                <ListItem disableGutters>
                  <ListItemText
                    primary="Origin Country"
                    secondary={`${previewData.origin_country} (${previewData.origin_confidence})`}
                  />
                </ListItem>
              )}
              {previewData.description && (
                <ListItem disableGutters>
                  <ListItemText
                    primary="Description"
                    secondary={previewData.description}
                  />
                </ListItem>
              )}
              {previewData.suggested_synonyms.length > 0 && (
                <ListItem disableGutters>
                  <ListItemText
                    primary="Suggested Synonyms"
                    secondary={
                      <Box
                        sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mt: 0.5 }}
                      >
                        {previewData.suggested_synonyms.map((syn, idx) => (
                          <Chip key={idx} label={syn} size="small" />
                        ))}
                      </Box>
                    }
                  />
                </ListItem>
              )}
              {previewData.price && (
                <ListItem disableGutters>
                  <ListItemText primary="Price" secondary={previewData.price} />
                </ListItem>
              )}
              {previewData.rating !== undefined && (
                <ListItem disableGutters>
                  <ListItemText
                    primary="Rating"
                    secondary={`${previewData.rating} (${previewData.num_ratings ?? 0} ratings)`}
                  />
                </ListItem>
              )}
            </List>
          </Paper>
        )}
      </Modal>

      {/* Batch ingest dialog */}
      <Modal
        open={batchOpen}
        title="Batch Ingest Materials"
        onClose={handleCloseBatchDialog}
        actions={
          <>
            <Button onClick={handleCloseBatchDialog}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleBatchIngest}
              disabled={batchLoading || !batchUrls.trim()}
              startIcon={
                batchLoading ? <CircularProgress size={16} /> : undefined
              }
            >
              Import All
            </Button>
          </>
        }
      >
        <TextField
          fullWidth
          label="Product URLs (one per line)"
          placeholder={"https://amazon.ae/dp/...\nhttps://amazon.ae/dp/..."}
          value={batchUrls}
          onChange={(e) => setBatchUrls(e.target.value)}
          multiline
          rows={6}
          size="small"
          sx={{ mb: 2 }}
        />

        {batchResults.length > 0 && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Results
            </Typography>
            <List dense>
              {batchResults.map((r, idx) => (
                <ListItem key={idx} disableGutters>
                  {r.status === "success" ? (
                    <Chip
                      icon={<CheckCircleIcon />}
                      label={r.material_id ?? r.url}
                      color="success"
                      size="small"
                      sx={{ mr: 1 }}
                    />
                  ) : (
                    <Chip
                      icon={<ErrorIcon />}
                      label={r.error ?? r.url}
                      color="error"
                      size="small"
                      sx={{ mr: 1 }}
                    />
                  )}
                  <Typography variant="caption" color="text.secondary" noWrap>
                    {r.url}
                  </Typography>
                </ListItem>
              ))}
            </List>
          </Box>
        )}
      </Modal>
    </Box>
  );
}
