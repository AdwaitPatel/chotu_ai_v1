import React from 'react';
import { money } from '../api';

export default function SettlementsModal({ isOpen, onClose, dashboard }) {
  if (!isOpen) return null;
  const transactions = dashboard?.recent_transactions || [];
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"><div className="w-full max-w-md rounded-lg border border-[#1f1f1f] bg-[#0a0a0a] p-5 text-xs"><div className="flex justify-between border-b border-[#1f1f1f] pb-3"><h2 className="font-medium text-white">Settlement activity</h2><button onClick={onClose}>✕</button></div><p className="mt-4 text-[#888888]">Today's recorded collections</p><p className="mt-1 font-mono text-2xl text-white">{money(dashboard?.metrics?.today_collections)}</p><p className="mt-4 text-[#888888]">Payment settlement is managed by the payment provider. This view shows live, recorded order activity; no settlement records are fabricated.</p><div className="mt-4 max-h-48 overflow-auto rounded border border-[#1f1f1f]">{transactions.map(t => <div key={t.id} className="flex justify-between border-b border-[#1f1f1f] p-3 last:border-0"><span className="text-[#888888]">{t.invoice_number}</span><span className="font-mono text-white">{money(t.amount)}</span></div>)}{!transactions.length && <p className="p-4 text-center text-[#666666]">No recorded activity.</p>}</div><button onClick={onClose} className="mt-4 w-full rounded bg-white py-2 text-black">Done</button></div></div>;
}
