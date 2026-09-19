import React, { useCallback, useEffect, useState } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import SettlementsModal from './components/SettlementsModal';
import DashboardView from './views/DashboardView';
import InventoryView from './views/InventoryView';
import GrowthCenterView from './views/GrowthCenterView';
import { api } from './api';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState('');
  const [settlementsOpen, setSettlementsOpen] = useState(false);
  const refreshDashboard = useCallback(async () => {
    try { setDashboard(await api('/api/dashboard')); setError(''); }
    catch (err) { setError(`Unable to reach the backend: ${err.message}`); }
  }, []);
  useEffect(() => { refreshDashboard(); }, [refreshDashboard]);
  return <div className="min-h-screen bg-black text-[#ededed] font-body antialiased flex flex-col">
    {error && <div className="fixed top-4 right-4 z-[60] max-w-sm rounded-md border border-[#ff0055]/40 bg-[#18050b] px-3 py-2 text-xs text-[#ffb3c9]">{error}</div>}
    <Header activeTab={activeTab} setActiveTab={setActiveTab} onOpenSettlement={() => setSettlementsOpen(true)} />
    <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} onOpenSettlement={() => setSettlementsOpen(true)} storeName={dashboard?.merchant?.name || 'Store'} />
    <div className="pl-60 flex-1"><main className="w-full min-h-screen pt-16 pb-14 px-6 md:px-10 bg-black">
      {activeTab === 'overview' && <DashboardView dashboard={dashboard} loading={!dashboard && !error} onNavigate={setActiveTab} onRefresh={refreshDashboard} />}
      {activeTab === 'inventory' && <InventoryView onInventoryChanged={refreshDashboard} />}
      {activeTab === 'store-growth' && <GrowthCenterView dashboard={dashboard} />}
    </main></div>
    <SettlementsModal isOpen={settlementsOpen} onClose={() => setSettlementsOpen(false)} dashboard={dashboard} />
  </div>;
}
