import { useEffect, useState, useCallback } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import { companyDocuments as api } from "../api/client";
import type { CompanyDocument, CreateCompanyDocumentRequest } from "../types/api";
import Modal from "../components/Modal";

interface FormData {
  company_key: string;
  title: string;
  document_type: string;
  issuer: string;
  issue_date: string;
  expiry_date: string;
  notes: string;
}

const EMPTY_FORM: FormData = {
  company_key: "",
  title: "",
  document_type: "",
  issuer: "",
  issue_date: "",
  expiry_date: "",
  notes: "",
};

type ViewMode = "all" | "expiring";

function getStatusChip(doc: CompanyDocument): { color: "error" | "warning" | "success" | "default"; label: string } {
  if (!doc.expiry_date) {
    return { color: "default", label: "No Expiry" };
  }
  if (doc.is_expired) {
    return { color: "error", label: "Expired" };
  }
  if (doc.days_until_expiry != null && doc.days_until_expiry <= 30) {
    return { color: "warning", label: "Expiring Soon" };
  }
  return { color: "success", label: "Valid" };
}

export default function CompanyDocuments() {
  const [docs, setDocs] = useState<CompanyDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    const req = viewMode === "expiring" ? api.expiring(30) : api.list({ limit: 100 });
    req
      .then((r) => {
        setDocs(r.documents);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [viewMode]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (doc: CompanyDocument) => {
    setEditId(doc.id);
    setForm({
      company_key: doc.company_key,
      title: doc.title,
      document_type: doc.document_type,
      issuer: doc.issuer ?? "",
      issue_date: doc.issued_date ?? "",
      expiry_date: doc.expiry_date ?? "",
      notes: doc.notes ?? "",
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const body: CreateCompanyDocumentRequest = {
        company_key: form.company_key,
        title: form.title,
        document_type: form.document_type || undefined,
        issued_date: form.issue_date || undefined,
        expiry_date: form.expiry_date || undefined,
        issuer: form.issuer || undefined,
        notes: form.notes || undefined,
      };
      if (editId != null) {
        await api.update(editId, body);
      } else {
        await api.create(body);
      }
      setModalOpen(false);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const openDeleteDialog = (id: number) => {
    setDeleteTargetId(id);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (deleteTargetId == null) return;
    try {
      await api.delete(deleteTargetId);
      setDeleteDialogOpen(false);
      setDeleteTargetId(null);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
      setDeleteDialogOpen(false);
    }
  };

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: ViewMode | null) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  const handleFieldChange = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const renderSkeletonRows = () => (
    <>
      {[1, 2, 3, 4, 5].map((i) => (
        <TableRow key={i}>
          <TableCell><Skeleton variant="text" /></TableCell>
          <TableCell><Skeleton variant="text" /></TableCell>
          <TableCell><Skeleton variant="text" /></TableCell>
          <TableCell><Skeleton variant="text" /></TableCell>
          <TableCell><Skeleton variant="text" /></TableCell>
          <TableCell><Skeleton variant="text" /></TableCell>
          <TableCell><Skeleton variant="rounded" width={80} height={24} /></TableCell>
          <TableCell><Skeleton variant="circular" width={32} height={32} /></TableCell>
        </TableRow>
      ))}
    </>
  );

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 3 }}>
        <Typography variant="h5" component="h1" fontWeight={600}>
          Company Documents
        </Typography>
        <Box sx={{ display: "flex", gap: 2, alignItems: "center" }}>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            size="small"
          >
            <ToggleButton value="all">All</ToggleButton>
            <ToggleButton value="expiring">Expiring Soon</ToggleButton>
          </ToggleButtonGroup>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={openCreate}
          >
            Add Document
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {total} document{total !== 1 ? "s" : ""}
        {viewMode === "expiring" && " expiring within 30 days"}
      </Typography>

      {!loading && docs.length === 0 ? (
        <Paper sx={{ p: 6, textAlign: "center" }}>
          <Typography color="text.secondary">
            {viewMode === "expiring" ? "No expiring documents." : "No documents yet."}
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Company Key</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Document Type</TableCell>
                <TableCell>Issuer</TableCell>
                <TableCell>Issue Date</TableCell>
                <TableCell>Expiry Date</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                renderSkeletonRows()
              ) : (
                docs.map((doc) => {
                  const status = getStatusChip(doc);
                  return (
                    <TableRow key={doc.id} hover>
                      <TableCell>{doc.company_key}</TableCell>
                      <TableCell>{doc.title}</TableCell>
                      <TableCell>{doc.document_type}</TableCell>
                      <TableCell>{doc.issuer ?? "-"}</TableCell>
                      <TableCell>{doc.issued_date ?? "-"}</TableCell>
                      <TableCell>{doc.expiry_date ?? "-"}</TableCell>
                      <TableCell>
                        <Chip
                          label={status.label}
                          color={status.color}
                          size="small"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={() => openEdit(doc)}
                          aria-label="edit document"
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={() => openDeleteDialog(doc.id)}
                          aria-label="delete document"
                          color="error"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Create / Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editId != null ? "Edit Document" : "Add Document"}
        actions={
          <>
            <Button onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={saving || !form.company_key || !form.title}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
          </>
        }
      >
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="Company Key"
            value={form.company_key}
            onChange={handleFieldChange("company_key")}
            required
            fullWidth
            size="small"
          />
          <TextField
            label="Title"
            value={form.title}
            onChange={handleFieldChange("title")}
            required
            fullWidth
            size="small"
          />
          <TextField
            label="Document Type"
            value={form.document_type}
            onChange={handleFieldChange("document_type")}
            fullWidth
            size="small"
          />
          <TextField
            label="Issuer"
            value={form.issuer}
            onChange={handleFieldChange("issuer")}
            fullWidth
            size="small"
          />
          <TextField
            label="Issue Date"
            type="date"
            value={form.issue_date}
            onChange={handleFieldChange("issue_date")}
            fullWidth
            size="small"
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="Expiry Date"
            type="date"
            value={form.expiry_date}
            onChange={handleFieldChange("expiry_date")}
            fullWidth
            size="small"
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="Notes"
            value={form.notes}
            onChange={handleFieldChange("notes")}
            fullWidth
            size="small"
            multiline
            rows={3}
          />
        </Box>
      </Modal>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Delete Document</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this document? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
