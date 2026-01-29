import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import CircularProgress from "@mui/material/CircularProgress";
import Box from "@mui/material/Box";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import InvoiceDetail from "./pages/InvoiceDetail";
import Catalog from "./pages/Catalog";
import Prices from "./pages/Prices";
import CompanyDocuments from "./pages/CompanyDocuments";
import Reminders from "./pages/Reminders";

// New pages — lazy-loaded
const Inventory = lazy(() => import("./pages/Inventory"));
const Sales = lazy(() => import("./pages/Sales"));
const Documents = lazy(() => import("./pages/Documents"));
const Search = lazy(() => import("./pages/Search"));
const Chat = lazy(() => import("./pages/Chat"));
const AmazonImport = lazy(() => import("./pages/AmazonImport"));
const ProformaCreator = lazy(() => import("./pages/ProformaCreator"));
const SalesCreator = lazy(() => import("./pages/SalesCreator"));

function LazyFallback() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
      <CircularProgress />
    </Box>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="invoices" element={<Invoices />} />
        <Route path="invoices/:id" element={<InvoiceDetail />} />
        <Route path="catalog" element={<Catalog />} />
        <Route path="prices" element={<Prices />} />
        <Route path="company-documents" element={<CompanyDocuments />} />
        <Route path="reminders" element={<Reminders />} />
        <Route
          path="inventory"
          element={
            <Suspense fallback={<LazyFallback />}>
              <Inventory />
            </Suspense>
          }
        />
        <Route
          path="sales"
          element={
            <Suspense fallback={<LazyFallback />}>
              <Sales />
            </Suspense>
          }
        />
        <Route
          path="documents"
          element={
            <Suspense fallback={<LazyFallback />}>
              <Documents />
            </Suspense>
          }
        />
        <Route
          path="search"
          element={
            <Suspense fallback={<LazyFallback />}>
              <Search />
            </Suspense>
          }
        />
        <Route
          path="chat"
          element={
            <Suspense fallback={<LazyFallback />}>
              <Chat />
            </Suspense>
          }
        />
        <Route
          path="amazon-import"
          element={
            <Suspense fallback={<LazyFallback />}>
              <AmazonImport />
            </Suspense>
          }
        />
        <Route
          path="creators/proforma"
          element={
            <Suspense fallback={<LazyFallback />}>
              <ProformaCreator />
            </Suspense>
          }
        />
        <Route
          path="creators/sales"
          element={
            <Suspense fallback={<LazyFallback />}>
              <SalesCreator />
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
