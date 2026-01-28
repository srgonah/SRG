import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import InvoiceDetail from "./pages/InvoiceDetail";
import Catalog from "./pages/Catalog";
import Prices from "./pages/Prices";
import CompanyDocuments from "./pages/CompanyDocuments";
import Reminders from "./pages/Reminders";

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
      </Route>
    </Routes>
  );
}
