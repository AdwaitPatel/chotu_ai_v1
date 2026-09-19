import React from 'react';
export default function Sidebar({ activeTab, setActiveTab, onOpenSettlement, storeName = 'Store' }) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: 'dashboard' },
    { id: 'inventory', label: 'Inventory', icon: 'inventory_2' },
    { id: 'store-growth', label: 'Store Growth', icon: 'trending_up' },
    { id: 'settlements', label: 'Settlements', icon: 'account_balance_wallet', isAction: true, onClick: onOpenSettlement },
  ];

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-black border-r border-[#1f1f1f] flex flex-col justify-between z-40 text-xs">
      
      {/* Top Workspace Header */}
      <div>
        <div className="h-12 border-b border-[#1f1f1f] px-4 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-5 h-5 rounded-full bg-[#1c1c1c] border border-[#333333] flex items-center justify-center text-[10px] font-bold text-[#ededed] flex-shrink-0">
              S
            </div>
            <span className="font-medium text-[#ededed] text-[13px] truncate">
              {storeName}'s store
            </span>
          </div>

          <span className="px-1.5 py-0.5 rounded bg-[#161616] border border-[#262626] text-[#888888] text-[10px] font-medium">
            Active
          </span>
        </div>

        {/* Navigation List */}
        <div className="p-3 flex flex-col gap-1">
          <span className="text-[10px] font-medium text-[#666666] px-2.5 py-1 uppercase tracking-wider">
            Menu
          </span>

          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.isAction && item.onClick) {
                    item.onClick();
                  } else {
                    setActiveTab(item.id);
                  }
                }}
                className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] transition-colors text-left ${
                  isActive
                    ? 'bg-[#1a1a1a] text-white font-medium border border-[#2a2a2a]'
                    : 'text-[#888888] hover:text-[#ededed] hover:bg-[#111111]'
                }`}
              >
                <span className={`material-symbols-outlined text-[17px] ${isActive ? 'text-white' : 'text-[#888888]'}`}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      

    </aside>
  );
}
