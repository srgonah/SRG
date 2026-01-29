import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Grid from "@mui/material/Grid2";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import CategoryIcon from "@mui/icons-material/Category";
import NotificationsIcon from "@mui/icons-material/Notifications";
import InventoryIcon from "@mui/icons-material/Inventory";
import SearchIcon from "@mui/icons-material/Search";
import ChatIcon from "@mui/icons-material/Chat";
import {
  health,
  invoices,
  reminders,
  companyDocuments,
  inventory,
} from "../api/client";
import type {
  HealthResponse,
  InvoiceListResponse,
  ReminderListResponse,
  CompanyDocumentListResponse,
  InventoryStatusResponse,
} from "../types/api";

interface Stats {
  health?: HealthResponse;
  invoiceCount?: number;
  reminderCount?: number;
  expiringDocs?: number;
  inventoryItems?: number;
}

interface StatCardProps {
  label: string;
  value: string | number;
  to: string;
  statusColor?: "success" | "error" | "warning" | "info" | "default";
  loading?: boolean;
}

function StatCard({ label, value, to, statusColor, loading }: StatCardProps) {
  const borderColorMap: Record<string, string> = {
    success: "success.main",
    error: "error.main",
    warning: "warning.main",
    info: "info.main",
    default: "divider",
  };

  const borderColor = borderColorMap[statusColor ?? "default"];

  if (loading) {
    return (
      <Card
        sx={{
          height: "100%",
          borderLeft: 4,
          borderLeftColor: "divider",
        }}
      >
        <CardContent>
          <Skeleton variant="text" width="60%" height={20} />
          <Skeleton variant="text" width="40%" height={40} sx={{ mt: 1 }} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      component={RouterLink}
      to={to}
      sx={{
        height: "100%",
        borderLeft: 4,
        borderLeftColor: borderColor,
        textDecoration: "none",
        transition: "background-color 0.2s",
        "&:hover": {
          bgcolor: "action.hover",
        },
      }}
    >
      <CardContent>
        <Typography
          variant="overline"
          color="text.secondary"
          sx={{ display: "block", mb: 0.5 }}
        >
          {label}
        </Typography>
        <Typography variant="h4" component="p" fontWeight={600}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      health.check(),
      invoices.list(1, 0),
      reminders.upcoming(30, 1),
      companyDocuments.expiring(30, 1),
      inventory.status(1, 0),
    ]).then(([h, inv, rem, docs, inv_status]) => {
      const errors: string[] = [];

      if (h.status === "rejected") {
        errors.push("Failed to fetch health status");
      }

      setStats({
        health: h.status === "fulfilled" ? h.value : undefined,
        invoiceCount:
          inv.status === "fulfilled"
            ? (inv.value as InvoiceListResponse).total
            : undefined,
        reminderCount:
          rem.status === "fulfilled"
            ? (rem.value as ReminderListResponse).total
            : undefined,
        expiringDocs:
          docs.status === "fulfilled"
            ? (docs.value as CompanyDocumentListResponse).total
            : undefined,
        inventoryItems:
          inv_status.status === "fulfilled"
            ? (inv_status.value as InventoryStatusResponse).total
            : undefined,
      });

      if (errors.length > 0) {
        setError(errors.join(". "));
      }

      setLoading(false);
    });
  }, []);

  const getHealthStatusColor = (): "success" | "error" | "default" => {
    if (!stats.health) return "default";
    return stats.health.status === "healthy" ? "success" : "error";
  };

  const quickActions = [
    { to: "/invoices", label: "Upload Invoice", icon: <UploadFileIcon /> },
    { to: "/catalog", label: "Browse Catalog", icon: <CategoryIcon /> },
    { to: "/reminders", label: "View Reminders", icon: <NotificationsIcon /> },
    { to: "/inventory", label: "Inventory Status", icon: <InventoryIcon /> },
    { to: "/search", label: "Search Documents", icon: <SearchIcon /> },
    { to: "/chat", label: "Chat with AI", icon: <ChatIcon /> },
  ];

  return (
    <Box>
      <Typography variant="h5" component="h1" fontWeight={600} sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      {error && (
        <Alert severity="warning" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Stats Cards */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            label="System Health"
            value={stats.health?.status ?? "unknown"}
            to="/docs"
            statusColor={getHealthStatusColor()}
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            label="Total Invoices"
            value={stats.invoiceCount ?? "-"}
            to="/invoices"
            statusColor="info"
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            label="Upcoming Reminders"
            value={stats.reminderCount ?? "-"}
            to="/reminders"
            statusColor="warning"
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            label="Expiring Documents"
            value={stats.expiringDocs ?? "-"}
            to="/company-documents"
            statusColor={
              stats.expiringDocs && stats.expiringDocs > 0 ? "error" : "default"
            }
            loading={loading}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            label="Inventory Items"
            value={stats.inventoryItems ?? "-"}
            to="/inventory"
            statusColor="default"
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Quick Actions and System Info */}
      <Grid container spacing={3}>
        {/* Quick Actions */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ mb: 2 }}
              >
                Quick Actions
              </Typography>
              <List disablePadding>
                {quickActions.map((action) => (
                  <ListItem key={action.to} disablePadding>
                    <ListItemButton
                      component={RouterLink}
                      to={action.to}
                      sx={{ borderRadius: 1, mb: 0.5 }}
                    >
                      <ListItemIcon sx={{ minWidth: 40 }}>
                        {action.icon}
                      </ListItemIcon>
                      <ListItemText primary={action.label} />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        {/* System Info */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Typography
                variant="subtitle2"
                color="text.secondary"
                sx={{ mb: 2 }}
              >
                System Info
              </Typography>
              {loading ? (
                <Box>
                  {[1, 2, 3, 4].map((i) => (
                    <Skeleton
                      key={i}
                      variant="text"
                      height={32}
                      sx={{ mb: 1 }}
                    />
                  ))}
                </Box>
              ) : (
                <Paper variant="outlined" sx={{ overflow: "hidden" }}>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell
                          component="th"
                          scope="row"
                          sx={{ color: "text.secondary", width: "40%" }}
                        >
                          Version
                        </TableCell>
                        <TableCell align="right">
                          {stats.health?.version ?? "-"}
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell
                          component="th"
                          scope="row"
                          sx={{ color: "text.secondary" }}
                        >
                          Uptime
                        </TableCell>
                        <TableCell align="right">
                          {stats.health
                            ? `${Math.round(stats.health.uptime_seconds / 60)} min`
                            : "-"}
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell
                          component="th"
                          scope="row"
                          sx={{ color: "text.secondary" }}
                        >
                          Database
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={
                              stats.health?.database?.available
                                ? "Connected"
                                : "Unavailable"
                            }
                            color={
                              stats.health?.database?.available
                                ? "success"
                                : "error"
                            }
                            size="small"
                            variant="outlined"
                          />
                        </TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell
                          component="th"
                          scope="row"
                          sx={{ color: "text.secondary", borderBottom: 0 }}
                        >
                          LLM
                        </TableCell>
                        <TableCell align="right" sx={{ borderBottom: 0 }}>
                          <Chip
                            label={
                              stats.health?.llm?.available
                                ? "Available"
                                : "Offline"
                            }
                            color={
                              stats.health?.llm?.available
                                ? "success"
                                : "default"
                            }
                            size="small"
                            variant="outlined"
                          />
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </Paper>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
