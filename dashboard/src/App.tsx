import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/Layout';
import { DashboardPage } from '@/pages/Dashboard';
import { UploadPage } from '@/pages/Upload';
import { InvoicesPage } from '@/pages/Invoices';
import { InvoiceDetailPage } from '@/pages/InvoiceDetail';
import { SearchPage } from '@/pages/Search';
import { ChatPage } from '@/pages/Chat';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/invoices" element={<InvoicesPage />} />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/chat/:sessionId" element={<ChatPage />} />
      </Routes>
    </Layout>
  );
}
