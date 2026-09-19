import React from 'react';

export default function Footer() {
  return (
    <footer className="fixed bottom-0 inset-x-0 h-8 bg-surface/90 backdrop-blur-md border-t border-border-subtle flex items-center justify-between px-6 z-40 text-[11px] text-text-dim">
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-positive"></span>
        <span>All systems online &amp; synchronized</span>
      </div>
      <div>
        <span>Paytm Merchant Network • 256-bit Encrypted</span>
      </div>
    </footer>
  );
}
