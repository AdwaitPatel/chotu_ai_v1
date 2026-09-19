import React, { useEffect, useState } from 'react';
import { api, money } from '../api';

export default function GrowthCenterView() {
  const [report, setReport] = useState(null); const [error, setError] = useState('');
  useEffect(() => { api('/api/analytics?period=week').then(setReport).catch(err => setError(err.message)); }, []);
  if (error) return <div className="py-20 text-center text-[#ffb3c9]">Could not load growth analytics: {error}</div>;
  if (!report) return <div className="py-20 text-center text-[#888888]">Loading live analytics…</div>;
  return <div className="max-w-5xl mx-auto flex flex-col gap-5 text-xs"><div><h1 className="text-xl font-semibold text-white">Store growth</h1><p className="mt-1 text-[#888888]">Insights calculated from your live orders and inventory.</p></div><div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><Card label="Weekly sales" value={money(report.sales_total)} /><Card label="Orders" value={report.order_count} /><Card label="Average bill" value={money(report.average_bill)} /></div><section className="rounded-lg border border-[#1f1f1f] p-5"><h2 className="font-medium text-white">Recommendations</h2><ul className="mt-3 space-y-2 text-[#888888]">{report.recommendations.map(item => <li key={item}>• {item}</li>)}{!report.recommendations.length && <li>More sales history is needed before recommendations can be calculated.</li>}</ul></section><section className="rounded-lg border border-[#1f1f1f] p-5"><h2 className="font-medium text-white">Top products this week</h2><div className="mt-3 space-y-2">{report.top_products.map(product => <div key={product.name} className="flex justify-between text-[#888888]"><span>{product.name} · {product.quantity} sold</span><span className="font-mono text-white">{money(product.sales_excluding_gst)}</span></div>)}{!report.top_products.length && <p className="text-[#888888]">No confirmed sales this week.</p>}</div></section></div>;
}
function Card({ label, value }) { return <div className="rounded-lg border border-[#1f1f1f] bg-[#0a0a0a] p-4"><p className="text-[#888888]">{label}</p><p className="mt-2 text-2xl font-mono text-white">{value}</p></div>; }
