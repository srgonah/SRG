import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import Skeleton from "@mui/material/Skeleton";
import Snackbar from "@mui/material/Snackbar";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Paper from "@mui/material/Paper";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import AddIcon from "@mui/icons-material/Add";
import RemoveIcon from "@mui/icons-material/Remove";

import { inventory, catalog } from "../api/client";
import type {
  InventoryItem,
  StockMovement,
  Material,
  ReceiveStockRequest,
  IssueStockRequest,
} from "../types/api";

const LOW_STOCK_THRESHOLD = 10;

interface SnackbarState {
  open: boolean;
  message: string;
  severity: "success" | "error";
}

interface ReceiveFormData {
  material_id: string;
  quantity: string;
  unit_cost: string;
  reference: string;
  notes: string;
}

interface IssueFormData {
  material_id: string;
  quantity: string;
  reference: string;
  notes: string;
}

export default function Inventory() {
  // Data state
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [lowStockItems, setLowStockItems] = useState<InventoryItem[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expanded rows for movement history
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [movementsByItem, setMovementsByItem] = useState<Record<number, StockMovement[]>>({});
  const [loadingMovements, setLoadingMovements] = useState<Set<number>>(new Set());

  // Dialog state
  const [receiveDialogOpen, setReceiveDialogOpen] = useState(false);
  const [issueDialogOpen, setIssueDialogOpen] = useState(false);
  const [receiveForm, setReceiveForm] = useState<ReceiveFormData>({
    material_id: "",
    quantity: "",
    unit_cost: "",
    reference: "",
    notes: "",
  });
  const [issueForm, setIssueForm] = useState<IssueFormData>({
    material_id: "",
    quantity: "",
    reference: "",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);

  // Snackbar state
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: "",
    severity: "success",
  });

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusRes, lowStockRes, catalogRes] = await Promise.all([
        inventory.status(100, 0),
        inventory.lowStock(LOW_STOCK_THRESHOLD, 100, 0),
        catalog.list({ limit: 500 }),
      ]);
      setItems(statusRes.items);
      setLowStockItems(lowStockRes.items);
      setMaterials(catalogRes.materials);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inventory");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Calculate stats
  const totalItems = items.length;
  const totalValue = items.reduce((sum, item) => sum + item.total_value, 0);
  const lowStockCount = lowStockItems.length;

  // Toggle row expansion and fetch movements
  const handleRowToggle = async (itemId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId);
    } else {
      newExpanded.add(itemId);
      // Fetch movements if not already loaded
      if (!movementsByItem[itemId]) {
        setLoadingMovements((prev) => new Set(prev).add(itemId));
        try {
          const movements = await inventory.movements(itemId, 50, 0);
          setMovementsByItem((prev) => ({ ...prev, [itemId]: movements }));
        } catch (err) {
          console.error("Failed to fetch movements:", err);
        } finally {
          setLoadingMovements((prev) => {
            const next = new Set(prev);
            next.delete(itemId);
            return next;
          });
        }
      }
    }
    setExpandedRows(newExpanded);
  };

  // Handle receive stock
  const handleReceiveSubmit = async () => {
    if (!receiveForm.material_id || !receiveForm.quantity || !receiveForm.unit_cost) {
      return;
    }
    setSubmitting(true);
    try {
      const request: ReceiveStockRequest = {
        material_id: receiveForm.material_id,
        quantity: parseFloat(receiveForm.quantity),
        unit_cost: parseFloat(receiveForm.unit_cost),
        reference: receiveForm.reference || undefined,
        notes: receiveForm.notes || undefined,
      };
      await inventory.receive(request);
      setSnackbar({
        open: true,
        message: "Stock received successfully",
        severity: "success",
      });
      setReceiveDialogOpen(false);
      setReceiveForm({
        material_id: "",
        quantity: "",
        unit_cost: "",
        reference: "",
        notes: "",
      });
      // Refresh data
      fetchData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to receive stock",
        severity: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Handle issue stock
  const handleIssueSubmit = async () => {
    if (!issueForm.material_id || !issueForm.quantity) {
      return;
    }
    setIssueError(null);

    // Client-side validation: check quantity against available stock
    const selectedItem = items.find((i) => i.material_id === issueForm.material_id);
    const requestedQty = parseFloat(issueForm.quantity);
    if (selectedItem && requestedQty > selectedItem.quantity_on_hand) {
      setIssueError(
        `Requested quantity (${requestedQty}) exceeds available stock (${selectedItem.quantity_on_hand})`
      );
      return;
    }

    setSubmitting(true);
    try {
      const request: IssueStockRequest = {
        material_id: issueForm.material_id,
        quantity: requestedQty,
        reference: issueForm.reference || undefined,
        notes: issueForm.notes || undefined,
      };
      await inventory.issue(request);
      setSnackbar({
        open: true,
        message: "Stock issued successfully",
        severity: "success",
      });
      setIssueDialogOpen(false);
      setIssueForm({
        material_id: "",
        quantity: "",
        reference: "",
        notes: "",
      });
      // Refresh data
      fetchData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to issue stock",
        severity: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Format currency
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(value);
  };

  // Format date
  const formatDate = (dateStr: string | undefined | null) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleDateString();
  };

  // Check if item is low stock
  const isLowStock = (qty: number) => qty <= LOW_STOCK_THRESHOLD;

  // Get material name by ID
  const getMaterialName = (materialId: string) => {
    const material = materials.find((m) => m.id === materialId);
    return material?.name ?? materialId;
  };

  // Get material unit by ID
  const getMaterialUnit = (materialId: string) => {
    const material = materials.find((m) => m.id === materialId);
    return material?.unit ?? "PCS";
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>
          Inventory
        </Typography>
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {[1, 2, 3].map((i) => (
            <Grid size={{ xs: 12, sm: 4 }} key={i}>
              <Card>
                <CardContent>
                  <Skeleton variant="text" width="60%" />
                  <Skeleton variant="text" width="40%" height={40} />
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
        <Paper>
          <Skeleton variant="rectangular" height={400} />
        </Paper>
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>
          Inventory
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
        <Typography variant="h5">Inventory</Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setReceiveDialogOpen(true)}
          >
            Receive Stock
          </Button>
          <Button
            variant="outlined"
            startIcon={<RemoveIcon />}
            onClick={() => setIssueDialogOpen(true)}
            disabled={items.length === 0}
          >
            Issue Stock
          </Button>
        </Box>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Items
              </Typography>
              <Typography variant="h4">{totalItems}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Value
              </Typography>
              <Typography variant="h4">{formatCurrency(totalValue)}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Low Stock Items
              </Typography>
              <Typography variant="h4" color={lowStockCount > 0 ? "warning.main" : "inherit"}>
                {lowStockCount}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Inventory Table */}
      {items.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">
            No inventory items found. Start by receiving stock.
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 50 }} />
                <TableCell>Item Name</TableCell>
                <TableCell>Unit</TableCell>
                <TableCell align="right">Quantity</TableCell>
                <TableCell align="right">WAC</TableCell>
                <TableCell align="right">Total Value</TableCell>
                <TableCell>Last Updated</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <InventoryRow
                  key={item.id}
                  item={item}
                  expanded={expandedRows.has(item.id)}
                  onToggle={() => handleRowToggle(item.id)}
                  movements={movementsByItem[item.id] ?? []}
                  loadingMovements={loadingMovements.has(item.id)}
                  isLowStock={isLowStock(item.quantity_on_hand)}
                  formatCurrency={formatCurrency}
                  formatDate={formatDate}
                  getMaterialName={getMaterialName}
                  getMaterialUnit={getMaterialUnit}
                />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Receive Stock Dialog */}
      <Dialog
        open={receiveDialogOpen}
        onClose={() => setReceiveDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Receive Stock</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
            <Autocomplete
              options={materials}
              getOptionLabel={(option) => option.name}
              value={materials.find((m) => m.id === receiveForm.material_id) ?? null}
              onChange={(_, newValue) =>
                setReceiveForm((prev) => ({ ...prev, material_id: newValue?.id ?? "" }))
              }
              renderInput={(params) => (
                <TextField {...params} label="Material" required fullWidth />
              )}
              isOptionEqualToValue={(option, value) => option.id === value.id}
            />
            <TextField
              label="Quantity"
              type="number"
              required
              value={receiveForm.quantity}
              onChange={(e) => setReceiveForm((prev) => ({ ...prev, quantity: e.target.value }))}
              inputProps={{ min: 0, step: "any" }}
            />
            <TextField
              label="Unit Cost"
              type="number"
              required
              value={receiveForm.unit_cost}
              onChange={(e) => setReceiveForm((prev) => ({ ...prev, unit_cost: e.target.value }))}
              inputProps={{ min: 0, step: "0.01" }}
            />
            <TextField
              label="Reference (PO/Invoice)"
              value={receiveForm.reference}
              onChange={(e) => setReceiveForm((prev) => ({ ...prev, reference: e.target.value }))}
            />
            <TextField
              label="Notes"
              multiline
              rows={2}
              value={receiveForm.notes}
              onChange={(e) => setReceiveForm((prev) => ({ ...prev, notes: e.target.value }))}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReceiveDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleReceiveSubmit}
            disabled={
              submitting || !receiveForm.material_id || !receiveForm.quantity || !receiveForm.unit_cost
            }
          >
            {submitting ? "Receiving..." : "Receive"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Issue Stock Dialog */}
      <Dialog
        open={issueDialogOpen}
        onClose={() => {
          setIssueDialogOpen(false);
          setIssueError(null);
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Issue Stock</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
            {issueError && (
              <Alert severity="error" onClose={() => setIssueError(null)}>
                {issueError}
              </Alert>
            )}
            <Autocomplete
              options={items}
              getOptionLabel={(option) =>
                `${getMaterialName(option.material_id)} (Available: ${option.quantity_on_hand})`
              }
              value={items.find((i) => i.material_id === issueForm.material_id) ?? null}
              onChange={(_, newValue) =>
                setIssueForm((prev) => ({ ...prev, material_id: newValue?.material_id ?? "" }))
              }
              renderInput={(params) => (
                <TextField {...params} label="Item" required fullWidth />
              )}
              isOptionEqualToValue={(option, value) => option.material_id === value.material_id}
            />
            <TextField
              label="Quantity"
              type="number"
              required
              value={issueForm.quantity}
              onChange={(e) => setIssueForm((prev) => ({ ...prev, quantity: e.target.value }))}
              inputProps={{ min: 0, step: "any" }}
              helperText={
                issueForm.material_id
                  ? `Available: ${items.find((i) => i.material_id === issueForm.material_id)?.quantity_on_hand ?? 0}`
                  : undefined
              }
            />
            <TextField
              label="Reference"
              value={issueForm.reference}
              onChange={(e) => setIssueForm((prev) => ({ ...prev, reference: e.target.value }))}
            />
            <TextField
              label="Reason/Notes"
              multiline
              rows={2}
              value={issueForm.notes}
              onChange={(e) => setIssueForm((prev) => ({ ...prev, notes: e.target.value }))}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setIssueDialogOpen(false);
              setIssueError(null);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleIssueSubmit}
            disabled={submitting || !issueForm.material_id || !issueForm.quantity}
          >
            {submitting ? "Issuing..." : "Issue"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          severity={snackbar.severity}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}

// Separate row component for better organization
interface InventoryRowProps {
  item: InventoryItem;
  expanded: boolean;
  onToggle: () => void;
  movements: StockMovement[];
  loadingMovements: boolean;
  isLowStock: boolean;
  formatCurrency: (value: number) => string;
  formatDate: (dateStr: string | undefined | null) => string;
  getMaterialName: (materialId: string) => string;
  getMaterialUnit: (materialId: string) => string;
}

function InventoryRow({
  item,
  expanded,
  onToggle,
  movements,
  loadingMovements,
  isLowStock,
  formatCurrency,
  formatDate,
  getMaterialName,
  getMaterialUnit,
}: InventoryRowProps) {
  return (
    <>
      <TableRow
        sx={{
          "& > *": { borderBottom: "unset" },
          ...(isLowStock && { backgroundColor: "warning.light" }),
        }}
        hover
      >
        <TableCell>
          <IconButton size="small" onClick={onToggle}>
            {expanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell>{getMaterialName(item.material_id)}</TableCell>
        <TableCell>{getMaterialUnit(item.material_id)}</TableCell>
        <TableCell align="right">
          {item.quantity_on_hand}
          {isLowStock && (
            <Chip
              label="Low"
              color="warning"
              size="small"
              sx={{ ml: 1 }}
            />
          )}
        </TableCell>
        <TableCell align="right">{formatCurrency(item.avg_cost)}</TableCell>
        <TableCell align="right">{formatCurrency(item.total_value)}</TableCell>
        <TableCell>{formatDate(item.last_movement_date)}</TableCell>
      </TableRow>
      <TableRow>
        <TableCell sx={{ py: 0 }} colSpan={7}>
          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Movement History
              </Typography>
              {loadingMovements ? (
                <Skeleton variant="rectangular" height={100} />
              ) : movements.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No movements recorded
                </Typography>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell align="right">Quantity</TableCell>
                      <TableCell align="right">Unit Cost</TableCell>
                      <TableCell>Reference</TableCell>
                      <TableCell>Notes</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {movements.map((movement) => (
                      <TableRow key={movement.id}>
                        <TableCell>{formatDate(movement.movement_date)}</TableCell>
                        <TableCell>
                          <Chip
                            label={movement.movement_type}
                            color={movement.movement_type === "IN" ? "success" : "error"}
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">{movement.quantity}</TableCell>
                        <TableCell align="right">{formatCurrency(movement.unit_cost)}</TableCell>
                        <TableCell>{movement.reference ?? "-"}</TableCell>
                        <TableCell>{movement.notes ?? "-"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}
