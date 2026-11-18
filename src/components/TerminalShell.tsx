import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  FileText,
  FlaskConical,
  Layers,
  Menu,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import type { ExperimentDetail, ViewId } from '../types/quant';

interface NavItem {
  id: ViewId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'command-center', label: 'Command Center', icon: Activity },
  { id: 'simulation-lab', label: 'Simulation Lab', icon: SlidersHorizontal },
  { id: 'distribution-analytics', label: 'Distribution Analytics', icon: BarChart3 },
  { id: 'regime-intelligence', label: 'Regime Intelligence', icon: Layers },
  { id: 'stress-testing', label: 'Stress Testing Lab', icon: ShieldAlert },
  { id: 'model-validation', label: 'Model Validation', icon: FlaskConical },
  { id: 'research-reports', label: 'Research Reports', icon: FileText },
];

interface TerminalShellProps {
  activeView: ViewId;
  onSelectView: (view: ViewId) => void;
  activeExperiment: ExperimentDetail | null;
  onPrimaryAction: () => void;
  children: React.ReactNode;
}

export function TerminalShell({
  activeView,
  onSelectView,
  activeExperiment,
  onPrimaryAction,
  children,
}: TerminalShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const currentNav = NAV_ITEMS.find((item) => item.id === activeView) ?? NAV_ITEMS[0];

  return (
    <div className="min-h-screen bg-[#050506] text-[#F4F4F5] flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:flex-col lg:w-64 lg:shrink-0 bg-[#08080A] border-r border-[#1A1A1E]">
        <div className="px-6 py-5 border-b border-[#1A1A1E]">
          <div className="text-base font-semibold tracking-[0.14em] text-[#F4F4F5]">BLACKSWAN</div>
          <p className="mt-1 text-[11px] text-[#71717A]">NSE Portfolio Risk Intelligence</p>
        </div>

        <nav aria-label="Primary sections" className="flex-1 px-3 py-5 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = item.id === activeView;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectView(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-[13px] font-medium rounded-md transition-colors text-left whitespace-nowrap ${
                  isActive
                    ? 'bg-[#16161B] text-[#F4F4F5]'
                    : 'text-[#71717A] hover:text-[#D4D4D8] hover:bg-[#111115]'
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#F4F4F5]' : 'text-[#52525B]'}`} />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="px-6 py-4 border-t border-[#1A1A1E] text-xs text-[#71717A] space-y-1.5">
          <div className="text-[11px] font-medium text-[#A1A1AA]">Active Model Context</div>
          {activeExperiment ? (
            <div className="font-mono text-[11px] space-y-0.5 tabular-nums">
              <div className="truncate text-[#F4F4F5] font-medium">{activeExperiment.name}</div>
              <div>
                {activeExperiment.n_paths.toLocaleString()} paths · {activeExperiment.horizon_days}d · seed{' '}
                {activeExperiment.random_seed}
              </div>
              <div>
                {activeExperiment.data_start_date} / {activeExperiment.data_end_date}
              </div>
            </div>
          ) : (
            <div className="text-[11px] text-[#52525B]">No experiment selected</div>
          )}
        </div>
      </aside>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative w-64 max-w-[80vw] bg-[#08080A] border-r border-[#1A1A1E] flex flex-col z-10">
            <div className="px-5 py-4 border-b border-[#1A1A1E] flex items-center justify-between">
              <span className="text-sm font-semibold tracking-[0.14em] text-[#F4F4F5]">BLACKSWAN</span>
              <button
                type="button"
                aria-label="Close navigation menu"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 text-[#71717A] hover:text-[#F4F4F5]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <nav aria-label="Mobile sections" className="flex-1 px-3 py-4 space-y-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = item.id === activeView;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      onSelectView(item.id);
                      setMobileMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-md text-left ${
                      isActive
                        ? 'bg-[#16161B] text-[#F4F4F5]'
                        : 'text-[#71717A] hover:text-[#D4D4D8]'
                    }`}
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 bg-[#050506]/95 border-b border-[#1A1A1E] px-4 lg:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              aria-label="Open navigation menu"
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-1.5 text-[#A1A1AA] hover:text-[#F4F4F5] rounded-md border border-[#1E1E24]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 text-xs sm:text-sm min-w-0 truncate">
              <span className="text-[#71717A] hidden sm:inline">BLACKSWAN</span>
              <span className="text-[#27272D] hidden sm:inline">/</span>
              <span className="font-medium text-[#F4F4F5] truncate">{currentNav.label}</span>
              {activeExperiment && (
                <>
                  <span className="text-[#27272D] hidden md:inline">·</span>
                  <span className="font-mono text-xs text-[#71717A] hidden md:inline truncate">
                    {activeExperiment.id}
                  </span>
                </>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onPrimaryAction}
            className="px-4 py-1.5 text-xs font-semibold bg-[#F4F4F5] text-[#050506] rounded-md hover:bg-[#E4E4E7] transition-colors whitespace-nowrap shrink-0"
          >
            {activeExperiment ? 'Configure Simulation' : 'Launch Simulation'}
          </button>
        </header>

        <main className="flex-1 p-4 lg:p-8 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
}

export function EmptyExperimentPrompt({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-8 text-center max-w-2xl mx-auto">
      <div className="inline-flex items-center justify-center w-10 h-10 rounded-md bg-[#141418] border border-[#222228] text-[#D4D4D8] mb-4">
        <AlertTriangle className="w-5 h-5" />
      </div>
      <h2 className="text-base font-semibold text-[#F4F4F5]">{title}</h2>
      <p className="mt-2 text-sm text-[#A1A1AA] leading-relaxed">{description}</p>
      <div className="mt-5">
        <button
          type="button"
          onClick={onAction}
          className="px-5 py-2 text-xs font-semibold bg-[#F4F4F5] text-[#050506] rounded-md hover:bg-[#E4E4E7] transition-colors"
        >
          {actionLabel}
        </button>
      </div>
    </div>
  );
}

export function LoadingPanel({ label }: { label: string }) {
  return (
    <div className="bg-[#0B0B0D] border border-[#1A1A1E] rounded-lg p-6 space-y-4" aria-busy="true">
      <div className="text-xs font-mono text-[#71717A]">{label}</div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((idx) => (
          <div key={idx} className="h-20 bg-[#141418] rounded-md animate-pulse" />
        ))}
      </div>
      <div className="h-64 bg-[#141418] rounded-md animate-pulse" />
    </div>
  );
}
