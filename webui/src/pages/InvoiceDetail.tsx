import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Tab from "@mui/material/Tab";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tabs from "@mui/material/Tabs";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DownloadIcon from "@mui/icons-material/Download";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import LinkIcon from "@mui/icons-material/Link";
import { invoices as api } from "../api/client";
import type { Invoice, AuditResult, AuditFinding } from "../types/api";
import ErrorBanner from "../components/ErrorBanner";

interface TabPanelProps {
  children?: React.ReactNode;
  value: number;
  index: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <Box
      role="tabpanel"
      hidden={value !== index}
      id={`invoice-tabpanel-${index}`}
      aria-labelledby={`invoice-tab-${index}`}
      sx={{ py: 3 }}
    >
      {value === index && children}
    </Box>
  );
}

function a11yProps(index: number) {
  return {
    id: `invoice-tab-${index}`,
    "aria-controls": `invoice-tabpanel-${index}`,
  };
}

function getSeverityColor(
  severity: AuditFinding["severity"]
): "error" | "warning" | "info" {
  switch (severity) {
    case "error":
      return "error";
    case "warning":
      return "warning";
    default:
      return "info";
  }
}

function getSeverityBorderColor(severity: AuditFinding["severity"]): string {
  switch (severity) {
    case "error":
      return "error.main";
    case "warning":
      return "warning.main";
    default:
      return "info.main";
  }
}

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [audits, setAudits] = useState<AuditResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [tabValue, setTabValue] = useState(0);

  const load = useCallback(() => {
    if (!id) return;
    setLoading(true);
    setError("");
    Promise.all([api.get(id), api.audits(id).catch(() => [])])
      .then(([inv, aud]) => {
        setInvoice(inv);
        setAudits(aud);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(load, [load]);

  const downloadPdf = async () => {
    if (!id) return;
    setPdfLoading(true);
    try {
      const blob = await api.proformaPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `proforma-${invoice?.invoice_number ?? id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "PDF generation failed");
    } finally {
      setPdfLoading(false);
    }
  };

  const runAudit = async () => {
    if (!id) return;
    setAuditLoading(true);
    try {
      const result = await api.audit(id);
      setAudits((prev) => [result, ...prev]);
      // Switch to Audits tab to show results
      setTabValue(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Audit failed");
    } finally {
      setAuditLoading(false);
    }
  };

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleMatchItem = async (itemIndex: number) => {
    if (!id || !invoice) return;
    // Navigate to catalog with item info for matching
    // This is a placeholder - actual implementation would depend on your matching flow
    console.log("Match item:", itemIndex, invoice.line_items[itemIndex]);
  };

  // Loading state
  if (loading) {
    return (
      <Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 3 }}>
          <Skeleton variant="circular" width={40} height={40} />
          <Skeleton variant="text" width={300} height={40} />
        </Box>
        <Skeleton variant="rectangular" height={200} sx={{ mb: 2 }} />
        <Skeleton variant="rectangular" height={400} />
      </Box>
    );
  }

  // Error state when invoice not found
  if (!invoice) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate("/invoices")}
          sx={{ mb: 2 }}
        >
          Back to Invoices
        </Button>
        <Alert severity="error">{error || "Invoice not found"}</Alert>
      </Box>
    );
  }

  const latestAudit = audits[0];

  return (
    <Box>
      {/* Header with back navigation */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          mb: 3,
          flexWrap: "wrap",
        }}
      >
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate("/invoices")}
          size="small"
        >
          Invoices
        </Button>
        <Typography variant="h5" component="h1" fontWeight={600}>
          Invoice {invoice.invoice_number ?? invoice.id.slice(0, 8)}
        </Typography>
        <Chip
          label={`${(invoice.confidence * 100).toFixed(0)}% confidence`}
          color={invoice.confidence >= 0.8 ? "success" : "warning"}
          size="small"
          variant="outlined"
        />
      </Box>

      {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

      {/* Actions Bar */}
      <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
        <Button
          variant="contained"
          startIcon={
            pdfLoading ? <CircularProgress size={16} color="inherit" /> : <DownloadIcon />
          }
          onClick={downloadPdf}
          disabled={pdfLoading}
        >
          Download Proforma PDF
        </Button>
        <Button
          variant="outlined"
          startIcon={
            auditLoading ? <CircularProgress size={16} /> : <FactCheckIcon />
          }
          onClick={runAudit}
          disabled={auditLoading}
        >
          Run Audit
        </Button>
      </Box>

      {/* Tabs */}
      <Paper sx={{ width: "100%" }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          aria-label="Invoice detail tabs"
          sx={{ borderBottom: 1, borderColor: "divider", px: 2 }}
        >
          <Tab label="Details" {...a11yProps(0)} />
          <Tab
            label={`Line Items (${invoice.line_items.length})`}
            {...a11yProps(1)}
          />
          <Tab label={`Audits (${audits.length})`} {...a11yProps(2)} />
        </Tabs>

        {/* Details Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ px: 2 }}>
            <Grid container spacing={3}>
              {/* Invoice Metadata */}
              <Grid size={{ xs: 12, md: 6 }}>
                <Card>
                  <CardContent>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      sx={{ mb: 2 }}
                    >
                      Invoice Details
                    </Typography>
                    <Grid container spacing={2}>
                      {[
                        { label: "Vendor", value: invoice.vendor_name },
                        { label: "Buyer", value: invoice.buyer_name },
                        { label: "Invoice Date", value: invoice.invoice_date },
                        { label: "Due Date", value: invoice.due_date },
                        { label: "Currency", value: invoice.currency },
                        { label: "Parser Used", value: invoice.parser_used },
                        { label: "Source File", value: invoice.source_file },
                      ].map((item) => (
                        <Grid size={{ xs: 6 }} key={item.label}>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            display="block"
                          >
                            {item.label}
                          </Typography>
                          <Typography variant="body2">
                            {item.value ?? "-"}
                          </Typography>
                        </Grid>
                      ))}
                    </Grid>
                  </CardContent>
                </Card>
              </Grid>

              {/* Totals */}
              <Grid size={{ xs: 12, md: 6 }}>
                <Card>
                  <CardContent>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      sx={{ mb: 2 }}
                    >
                      Totals
                    </Typography>
                    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <Typography variant="body2" color="text.secondary">
                          Subtotal
                        </Typography>
                        <Typography variant="body2" fontFamily="monospace">
                          {invoice.subtotal?.toLocaleString() ?? "-"}
                        </Typography>
                      </Box>
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <Typography variant="body2" color="text.secondary">
                          Tax
                        </Typography>
                        <Typography variant="body2" fontFamily="monospace">
                          {invoice.tax_amount?.toLocaleString() ?? "-"}
                        </Typography>
                      </Box>
                      <Divider />
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <Typography variant="body2" fontWeight={600}>
                          Total
                        </Typography>
                        <Typography
                          variant="body2"
                          fontFamily="monospace"
                          fontWeight={600}
                        >
                          {invoice.total_amount?.toLocaleString() ?? "-"}{" "}
                          {invoice.currency}
                        </Typography>
                      </Box>
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <Typography variant="body2" color="text.secondary">
                          Calculated Total
                        </Typography>
                        <Typography variant="body2" fontFamily="monospace">
                          {invoice.calculated_total.toLocaleString()}
                        </Typography>
                      </Box>
                    </Box>
                  </CardContent>
                </Card>

                {/* Latest Audit Summary */}
                {latestAudit && (
                  <Card sx={{ mt: 2 }}>
                    <CardContent>
                      <Typography
                        variant="subtitle2"
                        color="text.secondary"
                        sx={{ mb: 2 }}
                      >
                        Latest Audit
                      </Typography>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mb: 1,
                        }}
                      >
                        <Chip
                          label={latestAudit.passed ? "PASSED" : "FAILED"}
                          color={latestAudit.passed ? "success" : "error"}
                          size="small"
                        />
                        <Typography variant="caption" color="text.secondary">
                          {new Date(latestAudit.audited_at).toLocaleString()}
                        </Typography>
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        {latestAudit.summary ?? "No summary"}
                      </Typography>
                      <Box sx={{ display: "flex", gap: 2, mt: 1 }}>
                        <Typography variant="caption" color="error.main">
                          {latestAudit.error_count} errors
                        </Typography>
                        <Typography variant="caption" color="warning.main">
                          {latestAudit.warning_count} warnings
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                )}
              </Grid>
            </Grid>
          </Box>
        </TabPanel>

        {/* Line Items Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ px: 2 }}>
            {invoice.line_items.length === 0 ? (
              <Box sx={{ py: 4, textAlign: "center" }}>
                <Typography color="text.secondary">
                  No line items parsed.
                </Typography>
              </Box>
            ) : (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Item Name</TableCell>
                      <TableCell align="right">Qty</TableCell>
                      <TableCell>Unit</TableCell>
                      <TableCell align="right">Unit Price</TableCell>
                      <TableCell align="right">Total</TableCell>
                      <TableCell align="center">Catalog Match</TableCell>
                      <TableCell align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {invoice.line_items.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell
                          sx={{
                            maxWidth: 250,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          <Tooltip title={item.description}>
                            <span>{item.description}</span>
                          </Tooltip>
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "monospace" }}>
                          {item.quantity}
                        </TableCell>
                        <TableCell>{item.unit ?? "-"}</TableCell>
                        <TableCell align="right" sx={{ fontFamily: "monospace" }}>
                          {item.unit_price.toLocaleString()}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: "monospace" }}>
                          {item.total_price.toLocaleString()}
                        </TableCell>
                        <TableCell align="center">
                          {item.matched_material_id ? (
                            <Chip
                              label="Matched"
                              color="success"
                              size="small"
                              variant="outlined"
                            />
                          ) : item.needs_catalog ? (
                            <Chip
                              label="Needs Match"
                              color="warning"
                              size="small"
                              variant="outlined"
                            />
                          ) : (
                            <Typography variant="body2" color="text.disabled">
                              -
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell align="center">
                          {!item.matched_material_id && item.needs_catalog && (
                            <Tooltip title="Match to catalog">
                              <IconButton
                                size="small"
                                onClick={() => handleMatchItem(index)}
                              >
                                <LinkIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        </TabPanel>

        {/* Audits Tab */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ px: 2 }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", mb: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Audit History
              </Typography>
              <Button
                variant="outlined"
                size="small"
                startIcon={
                  auditLoading ? (
                    <CircularProgress size={16} />
                  ) : (
                    <FactCheckIcon />
                  )
                }
                onClick={runAudit}
                disabled={auditLoading}
              >
                Run Audit
              </Button>
            </Box>

            {audits.length === 0 ? (
              <Box sx={{ py: 4, textAlign: "center" }}>
                <Typography color="text.secondary">
                  No audits yet. Run an audit to check this invoice.
                </Typography>
              </Box>
            ) : (
              <List disablePadding>
                {audits.map((audit) => (
                  <Card key={audit.id} sx={{ mb: 2 }}>
                    <CardContent>
                      {/* Audit Header */}
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mb: 2,
                        }}
                      >
                        <Chip
                          label={audit.passed ? "PASS" : "FAIL"}
                          color={audit.passed ? "success" : "error"}
                          size="small"
                        />
                        <Typography variant="caption" color="text.secondary">
                          {new Date(audit.audited_at).toLocaleString()}
                        </Typography>
                        {audit.duration_ms != null && (
                          <Typography variant="caption" color="text.secondary">
                            ({audit.duration_ms}ms)
                          </Typography>
                        )}
                      </Box>

                      {/* Findings */}
                      {audit.findings.length === 0 ? (
                        <Typography variant="body2" color="text.secondary">
                          No issues found.
                        </Typography>
                      ) : (
                        <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                          {audit.findings.map((finding, fIndex) => (
                            <Card
                              key={fIndex}
                              variant="outlined"
                              sx={{
                                borderLeft: 4,
                                borderLeftColor: getSeverityBorderColor(
                                  finding.severity
                                ),
                              }}
                            >
                              <ListItem>
                                <ListItemText
                                  primary={
                                    <Box
                                      sx={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: 1,
                                      }}
                                    >
                                      <Chip
                                        label={finding.severity.toUpperCase()}
                                        color={getSeverityColor(finding.severity)}
                                        size="small"
                                        variant="outlined"
                                      />
                                      <Typography
                                        variant="body2"
                                        fontFamily="monospace"
                                        color="text.secondary"
                                      >
                                        [{finding.code}]
                                      </Typography>
                                    </Box>
                                  }
                                  secondary={
                                    <>
                                      <Typography
                                        variant="body2"
                                        component="span"
                                        display="block"
                                        sx={{ mt: 0.5 }}
                                      >
                                        {finding.message}
                                      </Typography>
                                      {finding.field && (
                                        <Typography
                                          variant="caption"
                                          color="text.secondary"
                                        >
                                          Field: {finding.field}
                                        </Typography>
                                      )}
                                    </>
                                  }
                                />
                              </ListItem>
                            </Card>
                          ))}
                        </Box>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </List>
            )}
          </Box>
        </TabPanel>
      </Paper>
    </Box>
  );
}
