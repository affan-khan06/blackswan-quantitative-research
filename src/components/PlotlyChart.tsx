import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';

interface PlotlyChartProps {
  data: Partial<Plotly.Data>[];
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
  className?: string;
  height?: number;
  testId?: string;
}

export function PlotlyChart({
  data,
  layout,
  config,
  className = '',
  height = 360,
  testId,
}: PlotlyChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const hasY2 = Boolean(layout?.yaxis2);
    const defaultMargin = { t: 28, r: hasY2 ? 78 : 22, b: 48, l: 64 };

    const mergedLayout: Partial<Plotly.Layout> = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: '#0B0B0D',
      font: {
        family: '"Plus Jakarta Sans", sans-serif',
        color: '#A1A1AA',
        size: 11,
      },
      height,
      hovermode: 'x unified',
      ...layout,
      margin: {
        ...defaultMargin,
        ...layout?.margin,
      },
      xaxis: {
        gridcolor: '#17171B',
        zerolinecolor: '#222228',
        linecolor: '#222228',
        tickfont: { family: '"JetBrains Mono", monospace', size: 10, color: '#71717A' },
        ...layout?.xaxis,
      },
      yaxis: {
        gridcolor: '#17171B',
        zerolinecolor: '#222228',
        linecolor: '#222228',
        tickfont: { family: '"JetBrains Mono", monospace', size: 10, color: '#71717A' },
        ...layout?.yaxis,
      },
      legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: 1.02,
        xanchor: 'left',
        x: 0,
        font: { size: 11, color: '#D4D4D8' },
        bgcolor: 'rgba(0,0,0,0)',
        ...layout?.legend,
      },
    };

    const mergedConfig: Partial<Plotly.Config> = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
      ...config,
    };

    Plotly.react(el, data as Plotly.Data[], mergedLayout, mergedConfig);

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        Plotly.Plots.resize(containerRef.current);
      }
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [data, layout, config, height]);

  useEffect(() => {
    const el = containerRef.current;
    return () => {
      if (el) {
        Plotly.purge(el);
      }
    };
  }, []);

  return <div ref={containerRef} data-testid={testId} className={`w-full ${className}`} style={{ minHeight: height }} />;
}
