import React from 'react';
import { money } from '../api';
import { soundbox } from '../utils/soundboxAudio';

const dateTime = (value) => value ? new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—';

export default function DashboardView({ dashboard, loading, onNavigate, onRefresh }) {
  if (loading) return <div className="py-20 text-center text-sm text-[#888888]">Loading live store data…</div>;
  if (!dashboard) return <div className="py-20 text-center text-sm text-[#888888]">Dashboard data is unavailable.</div>;
  const { merchant, metrics, low_stock: lowStock, recent_transactions: transactions } = dashboard;
  return <div className="max-w-7xl mx-auto flex flex-col gap-6 text-xs">
    <div className="rounded-lg border border-[#1f1f1f] bg-[#0a0a0a] p-6 flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3"><div><p className="text-[#888888]">Live store operations</p><h1 className="mt-1 text-xl font-semibold text-white">{merchant.name}</h1></div><button onClick={onRefresh} className="rounded-md border border-[#2e2e2e] px-3 py-1.5 hover:bg-[#161616]">Refresh</button></div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><Metric label="Today's collections" value={money(metrics.today_collections)} /><Metric label="Transactions today" value={metrics.transaction_count} /><Metric label="Average ticket" value={money(metrics.average_ticket)} /></div>
      <div className="rounded-md border border-[#1f1f1f] bg-black p-4 flex items-center justify-between gap-4"><div><p className="font-mono text-[#888888]">SOUNDBOX STATUS</p><p className="mt-1 text-sm text-[#00e599]">Online</p></div><button onClick={() => soundbox.playChime()} className="rounded-md bg-white px-3 py-1.5 text-black font-medium">Test chime</button></div>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <section className="md:col-span-2 rounded-lg border border-[#1f1f1f] overflow-hidden"><div className="p-4 border-b border-[#1f1f1f] flex justify-between"><h2 className="font-medium text-white">Recent transactions</h2><span className="text-[#888888]">Live from orders</span></div><table className="w-full text-left"><thead className="bg-[#0a0a0a] text-[#888888]"><tr><th className="p-3">Customer</th><th className="p-3">Method</th><th className="p-3">Time</th><th className="p-3 text-right">Amount</th></tr></thead><tbody>{transactions.map(t => <tr key={t.id} onClick={() => soundbox.announcePayment(Number(t.amount), 'hi')} className="border-t border-[#1f1f1f] hover:bg-[#0a0a0a] cursor-pointer"><td className="p-3 text-white">{t.payer}</td><td className="p-3 text-[#888888] capitalize">{t.method}</td><td className="p-3 text-[#666666]">{dateTime(t.created_at)}</td><td className="p-3 text-right font-mono text-white">{money(t.amount)}</td></tr>)}{!transactions.length && <tr><td colSpan="4" className="p-8 text-center text-[#666666]">No transactions recorded yet.</td></tr>}</tbody></table></section>
      <section className="rounded-lg border border-[#1f1f1f] p-4"><div className="flex justify-between"><h2 className="font-medium text-white">Stock guard</h2><button onClick={() => onNavigate('inventory')} className="text-[#0070f3]">View inventory</button></div><p className="mt-2 text-[#888888]">{metrics.low_stock_count} item(s) need attention.</p><div className="mt-4 space-y-3">{lowStock.map(item => <div key={item.id}><p className="text-white">{item.name}</p><p className="text-[#ff0055]">{item.stock} {item.unit} remaining</p></div>)}{!lowStock.length && <p className="text-[#00e599]">All stock levels are healthy.</p>}</div></section>
    </div>
  </div>;
}
function Metric({ label, value }) { return <div className="rounded-md border border-[#1f1f1f] bg-black p-4"><p className="text-[#888888]">{label}</p><p className="mt-2 font-mono text-2xl font-semibold text-white">{value}</p></div>; }
