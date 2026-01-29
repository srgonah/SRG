import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Collapse from "@mui/material/Collapse";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
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
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";

import { sales, inventory, catalog } from "../api/client";
import type {
  LocalSalesInvoice,
  InventoryItem,
  Material,
  CreateSalesInvoiceRequest,
  CreateSalesItemRequest,
} from "../types/api";

interface SnackbarState {
  open: boolean;
  message: string;
  severity: "success" | "error";
}

interface SaleItemForm {
  id: string; // unique key for React
  material_id: string;
  description: string;
  quantity: string;
  unit_price: string;
}

interface SaleForm {
  invoice_number: string;
  customer_name: string;
  sale_date: string;
  tax_amount: string;
  notes: string;
  items: SaleItemForm[];
}

const createEmptyItem = (): SaleItemForm => ({
  id: crypto.randomUUID(),
  material_id: "",
  description: "",
  quantity: "",
  unit_price: "",
});

export default function Sales() {
  // Data state
  const [invoices, setInvoices] = useState<LocalSalesInvoice[]>([]);
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Expanded rows for line item detail
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  // Dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [saleForm, setSaleForm] = useState<SaleForm>({
    invoice_number: "",
    customer_name: "",
    sale_date: new Date().toISOString().split("T")[0] ?? "",
    tax_amount: "0",
    notes: "",
    items: [createEmptyItem()],
  });
  const [submitting, setSubmitting] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState<number | null>(null);

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
      const [salesRes, invRes, catalogRes] = await Promise.all([
        sales.list(100, 0),
        inventory.status(500, 0),
        catalog.list({ limit: 500 }),
      ]);
      setInvoices(salesRes.invoices);
      setInventoryItems(invRes.items);
      setMaterials(catalogRes.materials);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sales data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Calculate stats
  const totalSales = invoices.length;
  const totalRevenue = invoices.reduce((sum, inv) => sum + inv.total_amount, 0);
  const totalProfit = invoices.reduce((sum, inv) => sum + inv.total_profit, 0);

  // Toggle row expansion
  const handleRowToggle = (invoiceId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(invoiceId)) {
      newExpanded.delete(invoiceId);
    } else {
      newExpanded.add(invoiceId);
    }
    setExpandedRows(newExpanded);
  };

  // Get material name by ID
  const getMaterialName = (materialId: string) => {
    const material = materials.find((m) => m.id === materialId);
    return material?.name ?? materialId;
  };

  // Get inventory item by material ID
  const getInventoryItem = (materialId: string) => {
    return inventoryItems.find((item) => item.material_id === materialId);
  };

  // Handle form item changes
  const handleItemChange = (
    index: number,
    field: keyof SaleItemForm,
    value: string
  ) => {
    setSaleForm((prev) => {
      const newItems = [...prev.items];
      const currentItem = newItems[index];
      if (currentItem) {
        newItems[index] = { ...currentItem, [field]: value };
      }
      return { ...prev, items: newItems };
    });
  };

  // Handle material selection for an item
  const handleMaterialSelect = (index: number, materialId: string | null) => {
    if (!materialId) {
      handleItemChange(index, "material_id", "");
      handleItemChange(index, "description", "");
      return;
    }

    const material = materials.find((m) => m.id === materialId);
    setSaleForm((prev) => {
      const newItems = [...prev.items];
      const currentItem = newItems[index];
      if (currentItem) {
        newItems[index] = {
          ...currentItem,
          material_id: materialId,
          description: material?.name ?? materialId,
        };
      }
      return { ...prev, items: newItems };
    });
  };

  // Add new item row
  const handleAddItem = () => {
    setSaleForm((prev) => ({
      ...prev,
      items: [...prev.items, createEmptyItem()],
    }));
  };

  // Remove item row
  const handleRemoveItem = (index: number) => {
    setSaleForm((prev) => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== index),
    }));
  };

  // Calculate line totals and summary
  const calculateLineTotal = (item: SaleItemForm): number => {
    const qty = parseFloat(item.quantity) || 0;
    const price = parseFloat(item.unit_price) || 0;
    return qty * price;
  };

  const calculateLineCost = (item: SaleItemForm): number => {
    const qty = parseFloat(item.quantity) || 0;
    const invItem = getInventoryItem(item.material_id);
    return qty * (invItem?.avg_cost ?? 0);
  };

  const summarySubtotal = saleForm.items.reduce(
    (sum, item) => sum + calculateLineTotal(item),
    0
  );

  const summaryCost = saleForm.items.reduce(
    (sum, item) => sum + calculateLineCost(item),
    0
  );

  const summaryProfit = summarySubtotal - summaryCost;

  // Handle create sale
  const handleCreateSubmit = async () => {
    // Validate
    if (!saleForm.invoice_number || !saleForm.customer_name) {
      setSnackbar({
        open: true,
        message: "Invoice number and customer name are required",
        severity: "error",
      });
      return;
    }

    const validItems = saleForm.items.filter(
      (item) =>
        item.material_id &&
        item.description &&
        parseFloat(item.quantity) > 0 &&
        parseFloat(item.unit_price) >= 0
    );

    if (validItems.length === 0) {
      setSnackbar({
        open: true,
        message: "At least one valid item is required",
        severity: "error",
      });
      return;
    }

    setSubmitting(true);
    try {
      const items: CreateSalesItemRequest[] = validItems.map((item) => ({
        material_id: item.material_id,
        description: item.description,
        quantity: parseFloat(item.quantity),
        unit_price: parseFloat(item.unit_price),
      }));

      const request: CreateSalesInvoiceRequest = {
        invoice_number: saleForm.invoice_number,
        customer_name: saleForm.customer_name,
        sale_date: saleForm.sale_date || undefined,
        tax_amount: parseFloat(saleForm.tax_amount) || 0,
        notes: saleForm.notes || undefined,
        items,
      };

      await sales.create(request);
      setSnackbar({
        open: true,
        message: "Sale created successfully",
        severity: "success",
      });
      setCreateDialogOpen(false);
      // Reset form
      setSaleForm({
        invoice_number: "",
        customer_name: "",
        sale_date: new Date().toISOString().split("T")[0] ?? "",
        tax_amount: "0",
        notes: "",
        items: [createEmptyItem()],
      });
      // Refresh data
      fetchData();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to create sale",
        severity: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Handle PDF download
  const handleDownloadPdf = async (invoiceId: number, invoiceNumber: string) => {
    setDownloadingPdf(invoiceId);
    try {
      const blob = await sales.downloadPdf(invoiceId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `sale-${invoiceNumber}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to download PDF",
        severity: "error",
      });
    } finally {
      setDownloadingPdf(null);
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
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString();
  };

  // Calculate margin percentage
  const calculateMargin = (revenue: number, cost: number): string => {
    if (revenue === 0) return "0.0%";
    const margin = ((revenue - cost) / revenue) * 100;
    return `${margin.toFixed(1)}%`;
  };

  if (loading) {
    return (
      <Box>
        <Typography variant="h5" sx={{ mb: 3 }}>
          Sales
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
          Sales
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
        <Typography variant="h5">Sales</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateDialogOpen(true)}
          disabled={inventoryItems.length === 0}
        >
          New Sale
        </Button>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Sales
              </Typography>
              <Typography variant="h4">{totalSales}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Revenue
              </Typography>
              <Typography variant="h4">{formatCurrency(totalRevenue)}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Total Profit
              </Typography>
              <Typography
                variant="h4"
                color={totalProfit >= 0 ? "success.main" : "error.main"}
              >
                {formatCurrency(totalProfit)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Sales Table */}
      {invoices.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">
            No sales invoices found. Create your first sale to get started.
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ width: 50 }} />
                <TableCell>Invoice #</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell align="right">Items</TableCell>
                <TableCell align="right">Revenue</TableCell>
                <TableCell align="right">Cost</TableCell>
                <TableCell align="right">Profit</TableCell>
                <TableCell align="right">Margin</TableCell>
                <TableCell sx={{ width: 60 }} />
              </TableRow>
            </TableHead>
            <TableBody>
              {invoices.map((invoice) => (
                <SalesRow
                  key={invoice.id}
                  invoice={invoice}
                  expanded={expandedRows.has(invoice.id)}
                  onToggle={() => handleRowToggle(invoice.id)}
                  onDownloadPdf={() => handleDownloadPdf(invoice.id, invoice.invoice_number)}
                  downloading={downloadingPdf === invoice.id}
                  formatCurrency={formatCurrency}
                  formatDate={formatDate}
                  calculateMargin={calculateMargin}
                />
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Create Sale Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>New Sale</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 3, pt: 1 }}>
            {/* Customer Info */}
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 2 }}>
                Customer Information
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Invoice Number"
                    required
                    fullWidth
                    value={saleForm.invoice_number}
                    onChange={(e) =>
                      setSaleForm((prev) => ({ ...prev, invoice_number: e.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Customer Name"
                    required
                    fullWidth
                    value={saleForm.customer_name}
                    onChange={(e) =>
                      setSaleForm((prev) => ({ ...prev, customer_name: e.target.value }))
                    }
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Sale Date"
                    type="date"
                    fullWidth
                    value={saleForm.sale_date}
                    onChange={(e) =>
                      setSaleForm((prev) => ({ ...prev, sale_date: e.target.value }))
                    }
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Tax Amount"
                    type="number"
                    fullWidth
                    value={saleForm.tax_amount}
                    onChange={(e) =>
                      setSaleForm((prev) => ({ ...prev, tax_amount: e.target.value }))
                    }
                    inputProps={{ min: 0, step: "0.01" }}
                  />
                </Grid>
              </Grid>
            </Box>

            <Divider />

            {/* Items */}
            <Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
                <Typography variant="subtitle2">Items</Typography>
                <Button size="small" startIcon={<AddIcon />} onClick={handleAddItem}>
                  Add Item
                </Button>
              </Box>

              {saleForm.items.map((item, index) => (
                <Box
                  key={item.id}
                  sx={{
                    display: "flex",
                    gap: 1,
                    mb: 2,
                    alignItems: "flex-start",
                  }}
                >
                  <Autocomplete
                    sx={{ flex: 2 }}
                    options={inventoryItems}
                    getOptionLabel={(option) =>
                      `${getMaterialName(option.material_id)} (Avail: ${option.quantity_on_hand})`
                    }
                    value={inventoryItems.find((i) => i.material_id === item.material_id) ?? null}
                    onChange={(_, newValue) =>
                      handleMaterialSelect(index, newValue?.material_id ?? null)
                    }
                    renderInput={(params) => (
                      <TextField {...params} label="Item" size="small" required />
                    )}
                    isOptionEqualToValue={(option, value) =>
                      option.material_id === value.material_id
                    }
                  />
                  <TextField
                    sx={{ flex: 1 }}
                    label="Qty"
                    type="number"
                    size="small"
                    required
                    value={item.quantity}
                    onChange={(e) => handleItemChange(index, "quantity", e.target.value)}
                    inputProps={{ min: 0, step: "any" }}
                    helperText={
                      item.material_id
                        ? `Avail: ${getInventoryItem(item.material_id)?.quantity_on_hand ?? 0}`
                        : undefined
                    }
                  />
                  <TextField
                    sx={{ flex: 1 }}
                    label="Sell Price"
                    type="number"
                    size="small"
                    required
                    value={item.unit_price}
                    onChange={(e) => handleItemChange(index, "unit_price", e.target.value)}
                    inputProps={{ min: 0, step: "0.01" }}
                  />
                  <Typography
                    sx={{
                      flex: 1,
                      display: "flex",
                      alignItems: "center",
                      minHeight: 40,
                      px: 1,
                    }}
                    variant="body2"
                    color="text.secondary"
                  >
                    = {formatCurrency(calculateLineTotal(item))}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={() => handleRemoveItem(index)}
                    disabled={saleForm.items.length <= 1}
                    color="error"
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Box>
              ))}
            </Box>

            <Divider />

            {/* Summary */}
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 2 }}>
                Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    Subtotal
                  </Typography>
                  <Typography variant="h6">{formatCurrency(summarySubtotal)}</Typography>
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    Estimated Cost
                  </Typography>
                  <Typography variant="h6">{formatCurrency(summaryCost)}</Typography>
                </Grid>
                <Grid size={{ xs: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    Estimated Profit
                  </Typography>
                  <Typography
                    variant="h6"
                    color={summaryProfit >= 0 ? "success.main" : "error.main"}
                  >
                    {formatCurrency(summaryProfit)}
                  </Typography>
                </Grid>
              </Grid>
            </Box>

            {/* Notes */}
            <TextField
              label="Notes"
              multiline
              rows={2}
              fullWidth
              value={saleForm.notes}
              onChange={(e) => setSaleForm((prev) => ({ ...prev, notes: e.target.value }))}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateSubmit}
            disabled={submitting || !saleForm.invoice_number || !saleForm.customer_name}
          >
            {submitting ? "Creating..." : "Create"}
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
interface SalesRowProps {
  invoice: LocalSalesInvoice;
  expanded: boolean;
  onToggle: () => void;
  onDownloadPdf: () => void;
  downloading: boolean;
  formatCurrency: (value: number) => string;
  formatDate: (dateStr: string) => string;
  calculateMargin: (revenue: number, cost: number) => string;
}

function SalesRow({
  invoice,
  expanded,
  onToggle,
  onDownloadPdf,
  downloading,
  formatCurrency,
  formatDate,
  calculateMargin,
}: SalesRowProps) {
  return (
    <>
      <TableRow sx={{ "& > *": { borderBottom: "unset" } }} hover>
        <TableCell>
          <IconButton size="small" onClick={onToggle}>
            {expanded ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell>{invoice.invoice_number}</TableCell>
        <TableCell>{formatDate(invoice.sale_date)}</TableCell>
        <TableCell>{invoice.customer_name}</TableCell>
        <TableCell align="right">{invoice.items.length}</TableCell>
        <TableCell align="right">{formatCurrency(invoice.total_amount)}</TableCell>
        <TableCell align="right">{formatCurrency(invoice.total_cost)}</TableCell>
        <TableCell
          align="right"
          sx={{ color: invoice.total_profit >= 0 ? "success.main" : "error.main" }}
        >
          {formatCurrency(invoice.total_profit)}
        </TableCell>
        <TableCell align="right">
          {calculateMargin(invoice.total_amount, invoice.total_cost)}
        </TableCell>
        <TableCell>
          <IconButton
            size="small"
            onClick={onDownloadPdf}
            disabled={downloading}
            title="Download PDF"
          >
            <DownloadIcon fontSize="small" />
          </IconButton>
        </TableCell>
      </TableRow>
      <TableRow>
        <TableCell sx={{ py: 0 }} colSpan={10}>
          <Collapse in={expanded} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Line Items
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Item Name</TableCell>
                    <TableCell align="right">Qty</TableCell>
                    <TableCell align="right">Unit Cost</TableCell>
                    <TableCell align="right">Sell Price</TableCell>
                    <TableCell align="right">Total</TableCell>
                    <TableCell align="right">Profit</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {invoice.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.description}</TableCell>
                      <TableCell align="right">{item.quantity}</TableCell>
                      <TableCell align="right">{formatCurrency(item.cost_basis)}</TableCell>
                      <TableCell align="right">{formatCurrency(item.unit_price)}</TableCell>
                      <TableCell align="right">{formatCurrency(item.line_total)}</TableCell>
                      <TableCell
                        align="right"
                        sx={{ color: item.profit >= 0 ? "success.main" : "error.main" }}
                      >
                        {formatCurrency(item.profit)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {invoice.notes && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  Notes: {invoice.notes}
                </Typography>
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}
