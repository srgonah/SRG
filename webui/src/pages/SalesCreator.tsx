import { useCallback, useEffect, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import Snackbar from "@mui/material/Snackbar";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import Stepper from "@mui/material/Stepper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import DownloadIcon from "@mui/icons-material/Download";
import PreviewIcon from "@mui/icons-material/Preview";

import { templates, creators } from "../api/client";
import type {
  PdfTemplate,
  PartyInfo,
  BankDetails,
  CreatorItem,
  CreateSalesDocumentRequest,
} from "../types/api";

const STEPS = ["Seller", "Buyer", "Bank Details", "Template", "Items", "Generate"];

interface SnackbarState {
  open: boolean;
  message: string;
  severity: "success" | "error" | "info";
}

interface ItemForm {
  id: string;
  description: string;
  quantity: string;
  unit: string;
  unit_price: string;
}

const createEmptyItem = (): ItemForm => ({
  id: crypto.randomUUID(),
  description: "",
  quantity: "1",
  unit: "pcs",
  unit_price: "",
});

export default function SalesCreator() {
  // Wizard state
  const [activeStep, setActiveStep] = useState(0);

  // Form state
  const [documentNumber, setDocumentNumber] = useState("");
  const [documentDate, setDocumentDate] = useState(new Date().toISOString().split("T")[0] ?? "");
  const [currency, setCurrency] = useState("AED");
  const [taxRate, setTaxRate] = useState("0");
  const [notes, setNotes] = useState("");
  const [terms, setTerms] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");

  // Seller info
  const [seller, setSeller] = useState<PartyInfo>({
    name: "",
    address: "",
    phone: "",
    email: "",
    tax_id: "",
  });

  // Buyer info
  const [buyer, setBuyer] = useState<PartyInfo>({
    name: "",
    address: "",
    phone: "",
    email: "",
    tax_id: "",
  });

  // Bank details
  const [bankDetails, setBankDetails] = useState<BankDetails>({
    bank_name: "",
    account_name: "",
    account_number: "",
    iban: "",
    swift_code: "",
  });

  // Template selection
  const [availableTemplates, setAvailableTemplates] = useState<PdfTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Items
  const [items, setItems] = useState<ItemForm[]>([createEmptyItem()]);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  // Snackbar
  const [snackbar, setSnackbar] = useState<SnackbarState>({
    open: false,
    message: "",
    severity: "success",
  });

  // Load templates on mount
  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const response = await templates.list({ template_type: "sales", active_only: true });
      setAvailableTemplates(response.templates);
      // Auto-select default template
      const defaultTpl = response.templates.find((t) => t.is_default);
      if (defaultTpl) {
        setSelectedTemplateId(defaultTpl.id);
      }
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to load templates",
        severity: "error",
      });
    } finally {
      setLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Calculate totals
  const calculateLineTotal = (item: ItemForm): number => {
    const qty = parseFloat(item.quantity) || 0;
    const price = parseFloat(item.unit_price) || 0;
    return qty * price;
  };

  const subtotal = items.reduce((sum, item) => sum + calculateLineTotal(item), 0);
  const taxAmount = subtotal * (parseFloat(taxRate) / 100);
  const total = subtotal + taxAmount;

  // Format currency
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  // Handle item changes
  const handleItemChange = (index: number, field: keyof ItemForm, value: string) => {
    setItems((prev) => {
      const newItems = [...prev];
      const currentItem = newItems[index];
      if (currentItem) {
        newItems[index] = { ...currentItem, [field]: value };
      }
      return newItems;
    });
  };

  const handleAddItem = () => {
    setItems((prev) => [...prev, createEmptyItem()]);
  };

  const handleRemoveItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  // Build request data
  const buildRequest = (): CreateSalesDocumentRequest => {
    const validItems: CreatorItem[] = items
      .filter((item) => item.description && parseFloat(item.quantity) > 0 && parseFloat(item.unit_price) >= 0)
      .map((item) => ({
        description: item.description,
        quantity: parseFloat(item.quantity),
        unit: item.unit || undefined,
        unit_price: parseFloat(item.unit_price),
      }));

    return {
      template_id: selectedTemplateId ?? undefined,
      document_number: documentNumber,
      document_date: documentDate,
      seller,
      buyer,
      bank_details: bankDetails.bank_name ? bankDetails : undefined,
      items: validItems,
      currency,
      tax_rate: parseFloat(taxRate) || 0,
      notes: notes || undefined,
      terms: terms || undefined,
      payment_terms: paymentTerms || undefined,
      save_as_document: true,
    };
  };

  // Handle preview
  const handlePreview = async () => {
    setPreviewing(true);
    try {
      const blob = await creators.previewSales(buildRequest());
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to generate preview",
        severity: "error",
      });
    } finally {
      setPreviewing(false);
    }
  };

  // Handle generate
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await creators.createSales(buildRequest());
      setSnackbar({
        open: true,
        message: result.message || "Sales invoice created successfully",
        severity: "success",
      });
      // Download the PDF
      if (result.document?.id) {
        const blob = await creators.downloadDocument(result.document.id);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `sales-invoice-${documentNumber}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      setSnackbar({
        open: true,
        message: err instanceof Error ? err.message : "Failed to generate sales invoice",
        severity: "error",
      });
    } finally {
      setGenerating(false);
    }
  };

  // Validate current step
  const isStepValid = (step: number): boolean => {
    switch (step) {
      case 0: // Seller
        return Boolean(seller.name);
      case 1: // Buyer
        return Boolean(buyer.name);
      case 2: // Bank details (optional)
        return true;
      case 3: // Template (optional)
        return true;
      case 4: // Items
        return items.some(
          (item) => item.description && parseFloat(item.quantity) > 0 && parseFloat(item.unit_price) >= 0
        );
      case 5: // Generate
        return Boolean(documentNumber && documentDate);
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (isStepValid(activeStep)) {
      setActiveStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  // Render step content
  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Seller Information
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Company Name"
                    required
                    fullWidth
                    value={seller.name}
                    onChange={(e) => setSeller({ ...seller, name: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Tax ID / VAT"
                    fullWidth
                    value={seller.tax_id}
                    onChange={(e) => setSeller({ ...seller, tax_id: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <TextField
                    label="Address"
                    fullWidth
                    multiline
                    rows={2}
                    value={seller.address}
                    onChange={(e) => setSeller({ ...seller, address: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Phone"
                    fullWidth
                    value={seller.phone}
                    onChange={(e) => setSeller({ ...seller, phone: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Email"
                    fullWidth
                    type="email"
                    value={seller.email}
                    onChange={(e) => setSeller({ ...seller, email: e.target.value })}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        );

      case 1:
        return (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Buyer Information
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Company/Client Name"
                    required
                    fullWidth
                    value={buyer.name}
                    onChange={(e) => setBuyer({ ...buyer, name: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Tax ID / VAT"
                    fullWidth
                    value={buyer.tax_id}
                    onChange={(e) => setBuyer({ ...buyer, tax_id: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <TextField
                    label="Address"
                    fullWidth
                    multiline
                    rows={2}
                    value={buyer.address}
                    onChange={(e) => setBuyer({ ...buyer, address: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Phone"
                    fullWidth
                    value={buyer.phone}
                    onChange={(e) => setBuyer({ ...buyer, phone: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Email"
                    fullWidth
                    type="email"
                    value={buyer.email}
                    onChange={(e) => setBuyer({ ...buyer, email: e.target.value })}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        );

      case 2:
        return (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Bank Details (Optional)
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Bank Name"
                    fullWidth
                    value={bankDetails.bank_name}
                    onChange={(e) => setBankDetails({ ...bankDetails, bank_name: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Account Name"
                    fullWidth
                    value={bankDetails.account_name}
                    onChange={(e) => setBankDetails({ ...bankDetails, account_name: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Account Number"
                    fullWidth
                    value={bankDetails.account_number}
                    onChange={(e) => setBankDetails({ ...bankDetails, account_number: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="IBAN"
                    fullWidth
                    value={bankDetails.iban}
                    onChange={(e) => setBankDetails({ ...bankDetails, iban: e.target.value })}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="SWIFT/BIC Code"
                    fullWidth
                    value={bankDetails.swift_code}
                    onChange={(e) => setBankDetails({ ...bankDetails, swift_code: e.target.value })}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        );

      case 3:
        return (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Select Template (Optional)
              </Typography>
              {loadingTemplates ? (
                <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
                  <CircularProgress />
                </Box>
              ) : availableTemplates.length === 0 ? (
                <Alert severity="info">
                  No templates available. The document will use default formatting.
                </Alert>
              ) : (
                <Grid container spacing={2}>
                  {availableTemplates.map((tpl) => (
                    <Grid size={{ xs: 12, sm: 6, md: 4 }} key={tpl.id}>
                      <Card
                        variant={selectedTemplateId === tpl.id ? "elevation" : "outlined"}
                        sx={{
                          cursor: "pointer",
                          border: selectedTemplateId === tpl.id ? 2 : 1,
                          borderColor: selectedTemplateId === tpl.id ? "primary.main" : "divider",
                        }}
                        onClick={() => setSelectedTemplateId(tpl.id)}
                      >
                        <CardContent>
                          <Typography variant="subtitle1" fontWeight="bold">
                            {tpl.name}
                          </Typography>
                          {tpl.description && (
                            <Typography variant="body2" color="text.secondary">
                              {tpl.description}
                            </Typography>
                          )}
                          {tpl.is_default && (
                            <Typography variant="caption" color="primary">
                              Default
                            </Typography>
                          )}
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              )}
            </CardContent>
          </Card>
        );

      case 4:
        return (
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3 }}>
                <Typography variant="h6">Items</Typography>
                <Button size="small" startIcon={<AddIcon />} onClick={handleAddItem}>
                  Add Item
                </Button>
              </Box>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: "40%" }}>Description</TableCell>
                      <TableCell sx={{ width: "12%" }}>Qty</TableCell>
                      <TableCell sx={{ width: "12%" }}>Unit</TableCell>
                      <TableCell sx={{ width: "15%" }}>Unit Price</TableCell>
                      <TableCell sx={{ width: "15%" }}>Total</TableCell>
                      <TableCell sx={{ width: "6%" }} />
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((item, index) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            placeholder="Item description"
                            value={item.description}
                            onChange={(e) => handleItemChange(index, "description", e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            fullWidth
                            value={item.quantity}
                            onChange={(e) => handleItemChange(index, "quantity", e.target.value)}
                            inputProps={{ min: 0, step: "any" }}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            value={item.unit}
                            onChange={(e) => handleItemChange(index, "unit", e.target.value)}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            fullWidth
                            value={item.unit_price}
                            onChange={(e) => handleItemChange(index, "unit_price", e.target.value)}
                            inputProps={{ min: 0, step: "0.01" }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {formatCurrency(calculateLineTotal(item))}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => handleRemoveItem(index)}
                            disabled={items.length <= 1}
                            color="error"
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <Divider sx={{ my: 3 }} />
              <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
                <Box sx={{ width: 300 }}>
                  <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                    <Typography>Subtotal:</Typography>
                    <Typography>{currency} {formatCurrency(subtotal)}</Typography>
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
                    <Typography>Tax Rate:</Typography>
                    <TextField
                      size="small"
                      type="number"
                      value={taxRate}
                      onChange={(e) => setTaxRate(e.target.value)}
                      sx={{ width: 100 }}
                      InputProps={{ endAdornment: "%" }}
                      inputProps={{ min: 0, step: "0.1" }}
                    />
                  </Box>
                  {taxAmount > 0 && (
                    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
                      <Typography>Tax:</Typography>
                      <Typography>{currency} {formatCurrency(taxAmount)}</Typography>
                    </Box>
                  )}
                  <Divider sx={{ my: 1 }} />
                  <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                    <Typography fontWeight="bold">Total:</Typography>
                    <Typography fontWeight="bold">{currency} {formatCurrency(total)}</Typography>
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        );

      case 5:
        return (
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 3 }}>
                Document Details & Generate
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Invoice Number"
                    required
                    fullWidth
                    value={documentNumber}
                    onChange={(e) => setDocumentNumber(e.target.value)}
                    placeholder="INV-001"
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Invoice Date"
                    type="date"
                    required
                    fullWidth
                    value={documentDate}
                    onChange={(e) => setDocumentDate(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <FormControl fullWidth>
                    <InputLabel>Currency</InputLabel>
                    <Select
                      value={currency}
                      label="Currency"
                      onChange={(e) => setCurrency(e.target.value)}
                    >
                      <MenuItem value="AED">AED</MenuItem>
                      <MenuItem value="USD">USD</MenuItem>
                      <MenuItem value="EUR">EUR</MenuItem>
                      <MenuItem value="GBP">GBP</MenuItem>
                      <MenuItem value="SAR">SAR</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <TextField
                    label="Notes"
                    fullWidth
                    multiline
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Terms & Conditions"
                    fullWidth
                    multiline
                    rows={2}
                    value={terms}
                    onChange={(e) => setTerms(e.target.value)}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label="Payment Terms"
                    fullWidth
                    multiline
                    rows={2}
                    value={paymentTerms}
                    onChange={(e) => setPaymentTerms(e.target.value)}
                    placeholder="e.g., Due within 30 days"
                  />
                </Grid>
              </Grid>

              <Divider sx={{ my: 3 }} />

              {/* Summary */}
              <Typography variant="subtitle1" sx={{ mb: 2 }}>
                Summary
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Seller
                    </Typography>
                    <Typography fontWeight="bold">{seller.name}</Typography>
                    {seller.address && <Typography variant="body2">{seller.address}</Typography>}
                  </Paper>
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Buyer
                    </Typography>
                    <Typography fontWeight="bold">{buyer.name}</Typography>
                    {buyer.address && <Typography variant="body2">{buyer.address}</Typography>}
                  </Paper>
                </Grid>
                <Grid size={{ xs: 12 }}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      Items: {items.filter((i) => i.description).length} | Total: {currency} {formatCurrency(total)}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              <Box sx={{ display: "flex", gap: 2, mt: 3, justifyContent: "center" }}>
                <Button
                  variant="outlined"
                  size="large"
                  startIcon={previewing ? <CircularProgress size={20} /> : <PreviewIcon />}
                  onClick={handlePreview}
                  disabled={previewing || generating || !documentNumber}
                >
                  Preview
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={generating ? <CircularProgress size={20} color="inherit" /> : <DownloadIcon />}
                  onClick={handleGenerate}
                  disabled={generating || previewing || !documentNumber}
                >
                  Generate & Download
                </Button>
              </Box>
            </CardContent>
          </Card>
        );

      default:
        return null;
    }
  };

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        Create Sales Invoice
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {renderStepContent()}

      <Box sx={{ display: "flex", justifyContent: "space-between", mt: 3 }}>
        <Button disabled={activeStep === 0} onClick={handleBack}>
          Back
        </Button>
        {activeStep < STEPS.length - 1 && (
          <Button variant="contained" onClick={handleNext} disabled={!isStepValid(activeStep)}>
            Next
          </Button>
        )}
      </Box>

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
