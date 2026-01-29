import { useCallback, useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Snackbar from "@mui/material/Snackbar";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import DeleteIcon from "@mui/icons-material/Delete";
import DescriptionIcon from "@mui/icons-material/Description";
import FolderIcon from "@mui/icons-material/Folder";
import RefreshIcon from "@mui/icons-material/Refresh";
import StorageIcon from "@mui/icons-material/Storage";
import { documents } from "../api/client";
import type { Document, IndexingStats } from "../types/api";

interface SnackbarState {
  open: boolean;
  message: string;
  severity: "success" | "error" | "info" | "warning";
}

export default function Documents() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [stats, setStats] = useState<IndexingStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [docToDelete, setDocToDelete] = useState<Document | null>(null);
  const [reindexingId, setReindexingId] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: "",
    severity: "info",
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [docsResponse, statsResponse] = await Promise.all([
        documents.list(100, 0),
        documents.stats(),
      ]);
      setDocs(docsResponse.documents);
      setStats(statsResponse);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load documents";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      setUploadProgress(0);

      // Simulate progress since fetch doesn't support progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 200);

      await documents.upload(file);

      clearInterval(progressInterval);
      setUploadProgress(100);

      setSnackbar({
        open: true,
        message: `Document "${file.name}" uploaded successfully`,
        severity: "success",
      });

      // Refresh the list
      await fetchData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setSnackbar({
        open: true,
        message,
        severity: "error",
      });
    } finally {
      setUploading(false);
      setUploadProgress(0);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleReindex = async (doc: Document) => {
    try {
      setReindexingId(doc.id);
      await documents.reindex(doc.id);
      setSnackbar({
        open: true,
        message: `Document "${doc.file_name}" reindexed successfully`,
        severity: "success",
      });
      await fetchData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Reindex failed";
      setSnackbar({
        open: true,
        message,
        severity: "error",
      });
    } finally {
      setReindexingId(null);
    }
  };

  const handleDeleteClick = (doc: Document) => {
    setDocToDelete(doc);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!docToDelete) return;

    try {
      await documents.remove(docToDelete.id);
      setSnackbar({
        open: true,
        message: `Document "${docToDelete.file_name}" deleted`,
        severity: "success",
      });
      setDeleteDialogOpen(false);
      setDocToDelete(null);
      await fetchData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Delete failed";
      setSnackbar({
        open: true,
        message,
        severity: "error",
      });
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setDocToDelete(null);
  };

  const handleSnackbarClose = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "-";
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusChip = (doc: Document) => {
    if (doc.indexed_at) {
      return <Chip label="Indexed" color="success" size="small" />;
    }
    return <Chip label="Pending" color="warning" size="small" />;
  };

  // Loading state
  if (loading && docs.length === 0) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>
          Documents
        </Typography>

        {/* Stats skeleton */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {[1, 2, 3].map((i) => (
            <Grid size={{ xs: 12, sm: 4 }} key={i}>
              <Card>
                <CardContent>
                  <Skeleton variant="text" width={100} />
                  <Skeleton variant="text" width={60} height={40} />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Table skeleton */}
        <Paper sx={{ p: 2 }}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} variant="rectangular" height={48} sx={{ mb: 1 }} />
          ))}
        </Paper>
      </Box>
    );
  }

  // Error state
  if (error && docs.length === 0) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>
          Documents
        </Typography>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="outlined" onClick={fetchData}>
          Retry
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
        <Typography variant="h5">Documents</Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<CloudUploadIcon />}
            onClick={handleUploadClick}
            disabled={uploading}
          >
            Upload Document
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.png,.jpg,.jpeg"
            style={{ display: "none" }}
            onChange={handleFileSelect}
          />
        </Box>
      </Box>

      {/* Upload progress */}
      {uploading && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Uploading document...
          </Typography>
          <LinearProgress variant="determinate" value={uploadProgress} />
        </Paper>
      )}

      {/* Stats cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <DescriptionIcon color="primary" />
                <Typography variant="body2" color="text.secondary">
                  Total Documents
                </Typography>
              </Box>
              <Typography variant="h4">{stats?.documents ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <FolderIcon color="primary" />
                <Typography variant="body2" color="text.secondary">
                  Total Chunks
                </Typography>
              </Box>
              <Typography variant="h4">{stats?.chunks ?? 0}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
                <StorageIcon color="primary" />
                <Typography variant="body2" color="text.secondary">
                  Total Vectors
                </Typography>
              </Box>
              <Typography variant="h4">{stats?.vectors ?? 0}</Typography>
              {stats && (
                <Chip
                  label={stats.index_synced ? "Synced" : "Out of sync"}
                  color={stats.index_synced ? "success" : "warning"}
                  size="small"
                  sx={{ mt: 1 }}
                />
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Documents table */}
      {docs.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <DescriptionIcon sx={{ fontSize: 48, color: "text.secondary", mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No documents yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Upload your first document to get started
          </Typography>
          <Button variant="contained" startIcon={<CloudUploadIcon />} onClick={handleUploadClick}>
            Upload Document
          </Button>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Filename</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Size</TableCell>
                <TableCell align="right">Pages</TableCell>
                <TableCell align="right">Chunks</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Indexed At</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {docs.map((doc) => (
                <TableRow key={doc.id} hover>
                  <TableCell>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                      <DescriptionIcon fontSize="small" color="action" />
                      <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                        {doc.file_name}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip label={doc.file_type} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell align="right">{formatFileSize(doc.file_size)}</TableCell>
                  <TableCell align="right">{doc.page_count}</TableCell>
                  <TableCell align="right">{doc.chunk_count}</TableCell>
                  <TableCell>{getStatusChip(doc)}</TableCell>
                  <TableCell>{formatDate(doc.indexed_at)}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Reindex">
                      <IconButton
                        size="small"
                        onClick={() => handleReindex(doc)}
                        disabled={reindexingId === doc.id}
                      >
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteClick(doc)}
                        color="error"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Document</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{docToDelete?.file_name}"? This action cannot be
            undone and will also remove the document from the search index.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for feedback */}
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
