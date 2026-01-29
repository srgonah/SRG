import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Container from "@mui/material/Container";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import MenuIcon from "@mui/icons-material/Menu";
import { health } from "../api/client";

const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/", label: "Dashboard" },
  { to: "/invoices", label: "Invoices" },
  { to: "/catalog", label: "Catalog" },
  { to: "/prices", label: "Prices" },
  { to: "/inventory", label: "Inventory" },
  { to: "/sales", label: "Sales" },
  { to: "/company-documents", label: "Company Docs" },
  { to: "/reminders", label: "Reminders" },
  { to: "/documents", label: "Documents" },
  { to: "/search", label: "Search" },
  { to: "/chat", label: "Chat" },
  { to: "/amazon-import", label: "Amazon Import" },
];

export default function Layout() {
  const [status, setStatus] = useState<"ok" | "err" | "loading">("loading");
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    health
      .check()
      .then((h) => setStatus(h.status === "healthy" ? "ok" : "err"))
      .catch(() => setStatus("err"));
  }, []);

  const statusColor =
    status === "ok"
      ? "success.main"
      : status === "err"
        ? "error.main"
        : "grey.500";

  const handleDrawerToggle = () => {
    setDrawerOpen((prev) => !prev);
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar variant="dense" sx={{ gap: 1 }}>
          {/* Mobile hamburger */}
          <IconButton
            edge="start"
            color="inherit"
            aria-label="open navigation menu"
            onClick={handleDrawerToggle}
            sx={{ display: { md: "none" } }}
          >
            <MenuIcon />
          </IconButton>

          {/* App title */}
          <Typography
            variant="h6"
            component={NavLink}
            to="/"
            sx={{
              textDecoration: "none",
              color: "primary.main",
              fontWeight: 700,
              mr: 2,
            }}
          >
            SRG
          </Typography>

          {/* Desktop navigation */}
          <Box
            component="nav"
            sx={{
              display: { xs: "none", md: "flex" },
              gap: 0.5,
              flexGrow: 1,
            }}
          >
            {NAV_ITEMS.map((item) => (
              <Button
                key={item.to}
                component={NavLink}
                to={item.to}
                end={item.to === "/"}
                size="small"
                sx={{
                  textTransform: "none",
                  color: "text.secondary",
                  "&.active": {
                    color: "primary.main",
                    bgcolor: "action.selected",
                  },
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>

          {/* Spacer for mobile */}
          <Box sx={{ flexGrow: 1, display: { md: "none" } }} />

          {/* Health status and API docs */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                bgcolor: statusColor,
                ...(status === "loading" && {
                  animation: "pulse 1.5s infinite",
                  "@keyframes pulse": {
                    "0%, 100%": { opacity: 1 },
                    "50%": { opacity: 0.4 },
                  },
                }),
              }}
            />
            <Typography variant="caption" color="text.secondary">
              {status === "ok"
                ? "Healthy"
                : status === "err"
                  ? "Unhealthy"
                  : "..."}
            </Typography>
            <Button
              href="/docs"
              target="_blank"
              rel="noreferrer"
              size="small"
              sx={{ textTransform: "none", ml: 1 }}
            >
              API Docs
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {/* Mobile drawer */}
      <Drawer
        anchor="left"
        open={drawerOpen}
        onClose={handleDrawerToggle}
        sx={{ display: { md: "none" } }}
      >
        <Box sx={{ width: 250 }} role="presentation">
          <Typography
            variant="h6"
            sx={{ px: 2, py: 1.5, fontWeight: 700, color: "primary.main" }}
          >
            SRG
          </Typography>
          <List>
            {NAV_ITEMS.map((item) => (
              <ListItem key={item.to} disablePadding>
                <ListItemButton
                  component={NavLink}
                  to={item.to}
                  end={item.to === "/"}
                  onClick={handleDrawerToggle}
                  sx={{
                    "&.active": {
                      bgcolor: "action.selected",
                      color: "primary.main",
                    },
                  }}
                >
                  <ListItemText primary={item.label} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>

      {/* Main content */}
      <Container maxWidth="xl" component="main" sx={{ flexGrow: 1, py: 3 }}>
        <Outlet />
      </Container>

      {/* Footer */}
      <Box
        component="footer"
        sx={{
          textAlign: "center",
          py: 2,
          borderTop: 1,
          borderColor: "divider",
        }}
      >
        <Typography variant="caption" color="text.secondary">
          SRG v1.0.0
        </Typography>
      </Box>
    </Box>
  );
}
