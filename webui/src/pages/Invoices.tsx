import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import LinearProgress from "@mui/material/LinearProgress";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Snackbar from "@mui/material/Snackbar";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TablePagination from "@mui/material/TablePagination";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import { invoices as api } from "../api/client";
import type { Invoice } from "../types/api";
import ErrorBanner from "../components/ErrorBanner";

export default function Invoices() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [items, setItems] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

  // Pagination state
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    api
      .list(rowsPerPage, page * rowsPerPage)
      .then((r) => {
        setItems(r.invoices);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, rowsPerPage]);

  useEffect(load, [load]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadProgress(0);
    setError("");

    // Simulate progress since fetch doesn't support upload progress
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => Math.min(prev + 10, 90));
    }, 200);

    try {
      const res = await api.upload(file);
      clearInterval(progressInterval);
      setUploadProgress(100);

      setSnackbar({
        open: true,
        message: `Uploaded: ${res.invoice.invoice_number ?? res.invoice_id} (confidence: ${(res.confidence * 100).toFixed(0)}%)`,
        severity: "success",
      });

      // Reset to first page and reload
      setPage(0);
      load();
    } catch (e: unknown) {
      clearInterval(progressInterval);
      setSnackbar({
        open: true,
        message: e instanceof Error ? e.message : "Upload failed",
        severity: "error",
      });
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    e.target.value = "";
  };

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleRowClick = (invoiceId: string) => {
    navigate(`/invoices/${invoiceId}`);
  };

  const getConfidenceColor = (
    confidence: number
  ): "success" | "warning" | "error" => {
    if (confidence >= 0.8) return "success";
    if (confidence >= 0.5) return "warning";
    return "error";
  };

  const handleCloseSnackbar = () => {
    setSnackbar((prev) => ({ ...prev, open: false }));
  };

  return (
    <Box>
      <Typography variant="h5" component="h1" fontWeight={600} sx={{ mb: 3 }}>
        Invoices
      </Typography>

      {/* Upload Area */}
      <Paper
        sx={{
          p: 4,
          mb: 3,
          textAlign: "center",
          border: "2px dashed",
          borderColor: dragOver ? "primary.main" : "divider",
          bgcolor: dragOver ? "action.hover" : "background.paper",
          cursor: uploading ? "default" : "pointer",
          transition: "all 0.2s",
          "&:hover": {
            borderColor: uploading ? "divider" : "primary.light",
            bgcolor: uploading ? "background.paper" : "action.hover",
          },
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={uploading ? undefined : onDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
      >
        {uploading ? (
          <Box sx={{ width: "100%", maxWidth: 400, mx: "auto" }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1 }}>
              <CloudUploadIcon color="primary" />
              <Typography color="primary">Uploading...</Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={uploadProgress}
              sx={{ height: 8, borderRadius: 1 }}
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
              {uploadProgress}%
            </Typography>
          </Box>
        ) : (
          <>
            <CloudUploadIcon
              sx={{ fontSize: 48, color: "text.secondary", mb: 1 }}
            />
            <Typography color="text.secondary" sx={{ mb: 0.5 }}>
              Drag and drop a PDF invoice here, or click to browse
            </Typography>
            <Typography variant="caption" color="text.disabled">
              PDF files accepted
            </Typography>
            <Box sx={{ mt: 2 }}>
              <Button variant="outlined" size="small" component="span">
                Select File
              </Button>
            </Box>
          </>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          style={{ display: "none" }}
          onChange={onFileInput}
        />
      </Paper>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {/* Invoice Count */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {total} invoice{total !== 1 ? "s" : ""}
      </Typography>

      {/* Invoice Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Invoice #</TableCell>
              <TableCell>Vendor</TableCell>
              <TableCell>Date</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell align="center">Items</TableCell>
              <TableCell align="center">Confidence</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              // Skeleton rows for loading state
              Array.from({ length: rowsPerPage }).map((_, index) => (
                <TableRow key={index}>
                  <TableCell>
                    <Skeleton variant="text" width={100} />
                  </TableCell>
                  <TableCell>
                    <Skeleton variant="text" width={150} />
                  </TableCell>
                  <TableCell>
                    <Skeleton variant="text" width={80} />
                  </TableCell>
                  <TableCell align="right">
                    <Skeleton variant="text" width={80} />
                  </TableCell>
                  <TableCell align="center">
                    <Skeleton variant="text" width={30} />
                  </TableCell>
                  <TableCell align="center">
                    <Skeleton
                      variant="rounded"
                      width={50}
                      height={24}
                      sx={{ mx: "auto" }}
                    />
                  </TableCell>
                </TableRow>
              ))
            ) : items.length === 0 ? (
              // Empty state
              <TableRow>
                <TableCell colSpan={6}>
                  <Box sx={{ py: 8, textAlign: "center" }}>
                    <Typography color="text.secondary">
                      No invoices yet. Upload one above.
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              // Invoice rows
              items.map((inv) => (
                <TableRow
                  key={inv.id}
                  hover
                  onClick={() => handleRowClick(inv.id)}
                  sx={{ cursor: "pointer" }}
                >
                  <TableCell>
                    <Typography
                      color="primary"
                      sx={{ fontWeight: 500 }}
                    >
                      {inv.invoice_number ?? inv.id.slice(0, 8)}
                    </Typography>
                  </TableCell>
                  <TableCell>{inv.vendor_name ?? "-"}</TableCell>
                  <TableCell>{inv.invoice_date ?? "-"}</TableCell>
                  <TableCell align="right" sx={{ fontFamily: "monospace" }}>
                    {inv.total_amount != null
                      ? `${inv.total_amount.toLocaleString()} ${inv.currency}`
                      : "-"}
                  </TableCell>
                  <TableCell align="center">{inv.line_items.length}</TableCell>
                  <TableCell align="center">
                    <Chip
                      label={`${(inv.confidence * 100).toFixed(0)}%`}
                      color={getConfidenceColor(inv.confidence)}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        {!loading && items.length > 0 && (
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 25, 50]}
          />
        )}
      </TableContainer>

      {/* Snackbar for upload feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
