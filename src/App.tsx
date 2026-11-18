/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useCallback, useEffect, useState } from 'react';
import { TerminalShell } from './components/TerminalShell';
import { api } from './services/api';
import type {
  AssetMetadata,
  ExperimentDetail,
  ExperimentSummary,
  MarketOverviewResponse,
  ViewId,
} from './types/quant';
import { CommandCenterView } from './views/CommandCenterView';
import { DistributionAnalyticsView } from './views/DistributionAnalyticsView';
import { ModelValidationView } from './views/ModelValidationView';
import { RegimeIntelligenceView } from './views/RegimeIntelligenceView';
import { ResearchReportsView } from './views/ResearchReportsView';
import { SimulationLabView } from './views/SimulationLabView';
import { StressTestingView } from './views/StressTestingView';

export default function App() {
  const [activeView, setActiveView] = useState<ViewId>('command-center');
  const [universe, setUniverse] = useState<AssetMetadata[]>([]);
  const [defaultSymbols, setDefaultSymbols] = useState<string[]>([]);
  const [marketOverview, setMarketOverview] = useState<MarketOverviewResponse | null>(null);
  const [activeExperiment, setActiveExperiment] = useState<ExperimentDetail | null>(null);
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);

  const [loadingMarket, setLoadingMarket] = useState(true);
  const [loadingExperiment, setLoadingExperiment] = useState(true);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const refreshExperiments = useCallback(async () => {
    try {
      const [listRes, latestRes] = await Promise.all([api.listExperiments(), api.getLatestExperiment()]);
      setExperiments(listRes.experiments);
      setActiveExperiment(latestRes.experiment);
    } catch (err) {
      setGlobalError(err instanceof Error ? err.message : 'Unable to reach BLACKSWAN backend.');
    } finally {
      setLoadingExperiment(false);
    }
  }, []);

  useEffect(() => {
    api
      .getUniverse()
      .then((res) => {
        setUniverse(res.assets);
        setDefaultSymbols(res.default_portfolio_symbols);
      })
      .catch(() => {});

    api
      .getMarketOverview()
      .then((res) => {
        setMarketOverview(res);
      })
      .catch((err) => {
        setGlobalError(err instanceof Error ? err.message : 'Failed to load NSE market overview.');
      })
      .finally(() => {
        setLoadingMarket(false);
      });

    refreshExperiments();
  }, [refreshExperiments]);

  const handleExperimentCompleted = (exp: ExperimentDetail) => {
    setActiveExperiment(exp);
    api.listExperiments().then((res) => setExperiments(res.experiments)).catch(() => {});
    setActiveView('command-center');
  };

  const handleSelectExperiment = async (id: string) => {
    setLoadingExperiment(true);
    try {
      const detail = await api.getExperiment(id);
      setActiveExperiment(detail);
      setActiveView('command-center');
    } catch (err) {
      setGlobalError(err instanceof Error ? err.message : 'Failed to load experiment.');
    } finally {
      setLoadingExperiment(false);
    }
  };

  const handleDeleteExperiment = async (id: string) => {
    await api.deleteExperiment(id);
    await refreshExperiments();
  };

  return (
    <TerminalShell
      activeView={activeView}
      onSelectView={setActiveView}
      activeExperiment={activeExperiment}
      onPrimaryAction={() => setActiveView('simulation-lab')}
    >
      {globalError && (
        <div className="p-3 rounded-lg bg-[#C75B64]/10 border border-[#C75B64]/35 text-xs text-[#E28A91]">
          {globalError}
        </div>
      )}

      {activeView === 'command-center' && (
        <CommandCenterView
          experiment={activeExperiment}
          marketOverview={marketOverview}
          loadingMarket={loadingMarket}
          loadingExperiment={loadingExperiment}
          onNavigate={setActiveView}
        />
      )}

      {activeView === 'simulation-lab' && (
        <SimulationLabView
          universe={universe}
          defaultSymbols={defaultSymbols}
          onExperimentCompleted={handleExperimentCompleted}
        />
      )}

      {activeView === 'distribution-analytics' && (
        <DistributionAnalyticsView experiment={activeExperiment} onNavigate={setActiveView} />
      )}

      {activeView === 'regime-intelligence' && (
        <RegimeIntelligenceView experiment={activeExperiment} onNavigate={setActiveView} />
      )}

      {activeView === 'stress-testing' && <StressTestingView experiment={activeExperiment} />}

      {activeView === 'model-validation' && <ModelValidationView experiment={activeExperiment} />}

      {activeView === 'research-reports' && (
        <ResearchReportsView
          experiments={experiments}
          activeExperiment={activeExperiment}
          onSelectExperiment={handleSelectExperiment}
          onDeleteExperiment={handleDeleteExperiment}
        />
      )}
    </TerminalShell>
  );
}
