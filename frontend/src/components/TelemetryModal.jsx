import React, { useState } from 'react';
import { soundbox } from '../utils/soundboxAudio';

export default function TelemetryModal({ isOpen, onClose }) {
  const [volume, setVolume] = useState(75);
  const [isPinging, setIsPinging] = useState(false);

  if (!isOpen) return null;

  const handleTestChime = () => {
    setIsPinging(true);
    soundbox.playChime();
    setTimeout(() => {
      soundbox.speak(`Soundbox volume set to ${volume} percent. Device operating optimally.`, 'en-IN');
      setIsPinging(false);
    }, 700);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
      <div className="w-full max-w-lg bg-surface-container rounded-2xl border border-surface-container-high shadow-2xl p-space-lg flex flex-col gap-space-md">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-container-high/40 pb-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[24px]">speaker</span>
            <h3 className="font-headline-sm text-base font-bold text-on-surface">Soundbox 4.0 Pro Telemetry</h3>
          </div>
          <button 
            onClick={onClose}
            className="w-8 h-8 rounded-lg hover:bg-surface-container-highest text-on-surface-variant flex items-center justify-center"
          >
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        {/* Device Info */}
        <div className="grid grid-cols-2 gap-space-sm">
          <div className="p-space-md rounded-xl bg-surface-container-low border border-surface-container-high/30 flex flex-col">
            <span className="text-on-surface-variant text-[11px]">Hardware Model</span>
            <span className="font-title-base text-on-surface font-semibold text-xs mt-0.5">Paytm Soundbox 4.0 Pro</span>
            <span className="font-label-numeric-base text-tertiary text-[10px] mt-1">Serial #SBX-IND-9941</span>
          </div>
          <div className="p-space-md rounded-xl bg-surface-container-low border border-surface-container-high/30 flex flex-col">
            <span className="text-on-surface-variant text-[11px]">Cellular Connectivity</span>
            <span className="font-title-base text-on-surface font-semibold text-xs mt-0.5">Airtel 4G LTE VoLTE</span>
            <span className="font-label-numeric-base text-primary text-[10px] mt-1">Signal: -64 dBm (Excellent)</span>
          </div>
        </div>

        {/* Battery & Health */}
        <div className="p-space-md rounded-xl bg-surface-container-low border border-surface-container-high/40 flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs">
            <span className="text-on-surface-variant flex items-center gap-1">
              <span className="material-symbols-outlined text-[16px] text-primary">battery_charging_full</span>
              Internal Lithium Battery
            </span>
            <span className="font-label-numeric-base text-primary font-bold">92% Charged</span>
          </div>
          <div className="w-full bg-surface-container h-2 rounded-full overflow-hidden">
            <div className="bg-primary h-full w-[92%] rounded-full"></div>
          </div>
          <span className="text-[10px] text-on-surface-variant">Estimated standby: 72+ hours uninterrupted</span>
        </div>

        {/* Speaker Volume Control */}
        <div className="p-space-md rounded-xl bg-surface-container-low border border-surface-container-high/40 flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs">
            <span className="text-on-surface-variant font-semibold">Master Audio Volume</span>
            <span className="font-label-numeric-base text-tertiary font-bold">{volume}%</span>
          </div>
          <input
            type="range"
            min="20"
            max="100"
            value={volume}
            onChange={(e) => setVolume(Number(e.target.value))}
            className="w-full accent-primary cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-on-surface-variant">
            <span>Quiet (20%)</span>
            <span>Recommended (75%)</span>
            <span>Loud Counter (100%)</span>
          </div>
        </div>

        {/* Test Ping Button */}
        <button
          onClick={handleTestChime}
          disabled={isPinging}
          className="w-full py-2.5 rounded-xl bg-primary hover:bg-primary-fixed-dim text-on-primary font-title-base text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-md active:scale-95"
        >
          <span className="material-symbols-outlined text-[18px]">
            {isPinging ? 'graphic_eq' : 'play_circle'}
          </span>
          <span>{isPinging ? 'Playing Test Soundbox Chime...' : 'Play Test Soundbox Chime'}</span>
        </button>

      </div>
    </div>
  );
}
