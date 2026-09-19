import React from 'react';
export default function Header({ 
  setActiveTab, 
  onOpenSettlement
}) {
  return (
    <header className="fixed top-0 inset-x-0 z-50 h-12 bg-black border-b border-[#1f1f1f] px-4 flex items-center justify-between text-xs">
      
      {/* Left: Project Breadcrumb */}
      <div className="flex items-center gap-2 text-[#ededed]">
        <div 
          onClick={() => setActiveTab('overview')}
          className="flex items-center gap-2 cursor-pointer hover:opacity-85 transition-opacity"
        >
          <span className="font-medium text-[#ededed] text-[13px]">
            chotu-ai
          </span>
        </div>
      </div>

      {/* Right: Soundbox Status & Quick Settlement Trigger */}
      <div className="flex items-center gap-2.5">
        
        {/* Quick Settle Button */}
        <button
          onClick={onOpenSettlement}
          className="px-2.5 py-1 rounded-md bg-[#111111] hover:bg-[#1a1a1a] border border-[#2e2e2e] hover:border-[#444444] text-[#ededed] text-xs font-medium transition-all flex items-center gap-1.5"
        >
          <span className="material-symbols-outlined text-[14px] text-[#888888]">account_balance_wallet</span>
          <span>Settle</span>
        </button>

      </div>

    </header>
  );
}
