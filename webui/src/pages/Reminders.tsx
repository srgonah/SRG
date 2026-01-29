import { useEffect, useState, useCallback } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Fab from "@mui/material/Fab";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import InfoIcon from "@mui/icons-material/Info";
import LightbulbIcon from "@mui/icons-material/Lightbulb";
import WarningIcon from "@mui/icons-material/Warning";
import { reminders as api } from "../api/client";
import type { Reminder, CreateReminderRequest, InsightResponse } from "../types/api";
import Modal from "../components/Modal";

type TabValue = 0 | 1 | 2;

interface FormData {
  title: string;
  due_date: string;
  message: string;
}

const EMPTY_FORM: FormData = {
  title: "",
  due_date: "",
  message: "",
};

function getReminderStatus(reminder: Reminder): { color: "error" | "warning" | "info" | "default"; label: string } {
  if (reminder.is_done) {
    return { color: "default", label: "Done" };
  }
  if (reminder.is_overdue) {
    return { color: "error", label: "Overdue" };
  }
  const today = new Date().toISOString().split("T")[0];
  if (reminder.due_date === today) {
    return { color: "warning", label: "Due Today" };
  }
  return { color: "info", label: "Upcoming" };
}

function getInsightIcon(severity: string) {
  switch (severity) {
    case "error":
    case "high":
      return <WarningIcon color="error" />;
    case "warning":
    case "medium":
      return <WarningIcon color="warning" />;
    default:
      return <InfoIcon color="info" />;
  }
}

export default function Reminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tabValue, setTabValue] = useState<TabValue>(0);
  const [modalOpen, setModalOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);
  const [insights, setInsights] = useState<InsightResponse[]>([]);
  const [insightsLoading, setInsightsLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    let req;
    switch (tabValue) {
      case 0: // Active
        req = api.list({ include_done: false, limit: 100 });
        break;
      case 1: // Upcoming 7d
        req = api.upcoming(7);
        break;
      case 2: // All
        req = api.list({ include_done: true, limit: 100 });
        break;
      default:
        req = api.list({ include_done: false, limit: 100 });
    }
    req
      .then((r) => {
        setItems(r.reminders);
        setTotal(r.total);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tabValue]);

  const loadInsights = useCallback(() => {
    setInsightsLoading(true);
    api.insights({ auto_create: false })
      .then((r) => {
        setInsights(r.insights);
      })
      .catch(() => {
        // Silently fail for insights
      })
      .finally(() => setInsightsLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadInsights();
  }, [loadInsights]);

  const openCreate = () => {
    setEditId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (r: Reminder) => {
    setEditId(r.id);
    setForm({
      title: r.title,
      due_date: r.due_date,
      message: r.message,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const body: CreateReminderRequest = {
        title: form.title,
        due_date: form.due_date,
        message: form.message || undefined,
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

  const toggleDone = async (r: Reminder) => {
    try {
      await api.update(r.id, { is_done: !r.is_done });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Update failed");
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

  const handleTabChange = (_: React.SyntheticEvent, newValue: TabValue) => {
    setTabValue(newValue);
  };

  const handleFieldChange = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const renderSkeletonList = () => (
    <List>
      {[1, 2, 3, 4, 5].map((i) => (
        <ListItem key={i}>
          <ListItemIcon>
            <Skeleton variant="rectangular" width={24} height={24} />
          </ListItemIcon>
          <ListItemText
            primary={<Skeleton variant="text" width="60%" />}
            secondary={<Skeleton variant="text" width="40%" />}
          />
        </ListItem>
      ))}
    </List>
  );

  return (
    <Box sx={{ position: "relative", pb: 10 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 3 }}>
        <Typography variant="h5" component="h1" fontWeight={600}>
          Reminders
        </Typography>
      </Box>

      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant="fullWidth">
          <Tab label="Active" />
          <Tab label="Upcoming 7d" />
          <Tab label="All" />
        </Tabs>
      </Paper>

      {error && (
        <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {total} reminder{total !== 1 ? "s" : ""}
      </Typography>

      {loading ? (
        <Paper>{renderSkeletonList()}</Paper>
      ) : items.length === 0 ? (
        <Paper sx={{ p: 6, textAlign: "center" }}>
          <Typography color="text.secondary">
            No reminders found.
          </Typography>
        </Paper>
      ) : (
        <Paper>
          <List>
            {items.map((r, index) => {
              const status = getReminderStatus(r);
              return (
                <Box key={r.id}>
                  {index > 0 && <Divider component="li" />}
                  <ListItem
                    sx={{
                      ...(r.is_done && {
                        textDecoration: "line-through",
                        opacity: 0.6,
                      }),
                    }}
                    secondaryAction={
                      <Box sx={{ display: "flex", gap: 0.5 }}>
                        <IconButton
                          size="small"
                          onClick={() => openEdit(r)}
                          aria-label="edit reminder"
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          onClick={() => openDeleteDialog(r.id)}
                          aria-label="delete reminder"
                          color="error"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    }
                  >
                    <ListItemIcon>
                      <Checkbox
                        edge="start"
                        checked={r.is_done}
                        onChange={() => toggleDone(r)}
                        inputProps={{ "aria-label": `Mark ${r.title} as ${r.is_done ? "not done" : "done"}` }}
                      />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <Typography
                            component="span"
                            sx={{
                              ...(r.is_done && { textDecoration: "line-through" }),
                            }}
                          >
                            {r.title}
                          </Typography>
                          <Chip
                            label={status.label}
                            color={status.color}
                            size="small"
                            sx={{
                              ...(r.is_done && { textDecoration: "line-through" }),
                            }}
                          />
                        </Box>
                      }
                      secondary={
                        <Box component="span" sx={{ display: "block" }}>
                          <Typography variant="body2" component="span" color="text.secondary">
                            Due: {r.due_date}
                          </Typography>
                          {r.message && (
                            <Typography variant="body2" component="span" display="block" color="text.secondary">
                              {r.message}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  </ListItem>
                </Box>
              );
            })}
          </List>
        </Paper>
      )}

      {/* Insights Panel */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
            <LightbulbIcon color="warning" />
            <Typography variant="h6">AI-Detected Insights</Typography>
          </Box>
          {insightsLoading ? (
            <Box>
              {[1, 2, 3].map((i) => (
                <Box key={i} sx={{ mb: 2 }}>
                  <Skeleton variant="text" width="80%" />
                  <Skeleton variant="text" width="60%" />
                </Box>
              ))}
            </Box>
          ) : insights.length === 0 ? (
            <Typography color="text.secondary">
              No insights available at the moment.
            </Typography>
          ) : (
            <List disablePadding>
              {insights.map((insight, index) => (
                <Box key={`${insight.category}-${index}`}>
                  {index > 0 && <Divider sx={{ my: 1 }} />}
                  <ListItem disablePadding sx={{ py: 1 }}>
                    <ListItemIcon sx={{ minWidth: 40 }}>
                      {getInsightIcon(insight.severity)}
                    </ListItemIcon>
                    <ListItemText
                      primary={insight.title}
                      secondary={insight.message}
                      primaryTypographyProps={{ fontWeight: 500 }}
                    />
                  </ListItem>
                </Box>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      {/* Floating Action Button */}
      <Fab
        color="primary"
        aria-label="add reminder"
        onClick={openCreate}
        sx={{
          position: "fixed",
          bottom: 24,
          right: 24,
        }}
      >
        <AddIcon />
      </Fab>

      {/* Create / Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editId != null ? "Edit Reminder" : "New Reminder"}
        actions={
          <>
            <Button onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={saving || !form.title || !form.due_date}
            >
              {saving ? "Saving..." : "Save"}
            </Button>
          </>
        }
      >
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label="Title"
            value={form.title}
            onChange={handleFieldChange("title")}
            required
            fullWidth
            size="small"
          />
          <TextField
            label="Due Date"
            type="date"
            value={form.due_date}
            onChange={handleFieldChange("due_date")}
            required
            fullWidth
            size="small"
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="Message"
            value={form.message}
            onChange={handleFieldChange("message")}
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
        <DialogTitle>Delete Reminder</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this reminder? This action cannot be undone.
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
