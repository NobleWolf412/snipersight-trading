import { useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { X } from '@phosphor-icons/react';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import { useSymbolCycles } from '@/hooks/useSymbolCycles';
import { FourYearCycleGauge } from '@/components/market/FourYearCycleGauge';
import { BTCCycleIntel } from '@/components/market/BTCCycleIntel';
import { api } from '@/utils/api';
import '@/styles/intel-hud.css';

// Radar SVG Component with animation
function RadarVisualization() {
  return (
    <div className="radar-visual">
      <svg viewBox="0 0 200 200" className="radar-svg">
        <circle cx="100" cy="100" r="90" fill="none" stroke="#0ff" strokeWidth="1" opacity="0.3" />
        <circle cx="100" cy="100" r="60" fill="none" stroke="#0ff" strokeWidth="1" opacity="0.2" />
        <circle cx="100" cy="100" r="30" fill="none" stroke="#0ff" strokeWidth="1" opacity="0.1" />

        {/* Radar sweep animation */}
        <line x1="100" y1="100" x2="100" y2="10" stroke="#0f0" strokeWidth="2" opacity="0.6" className="radar-sweep" />

        {/* Data points */}
        <circle cx="130" cy="70" r="4" fill="#0f0" />
        <circle cx="150" cy="100" r="4" fill="#ff6b00" />
        <circle cx="100" cy="150" r="4" fill="#0ff" />
        <circle cx="60" cy="80" r="3" fill="#0ff" />
      </svg>
    </div>
  );
}

// Fear & Greed data interface
interface FearGreedData {
  value: number;
  classification: string;
  sentiment: string;
  bottom_line: string;
  risk_text: string;
}

export function Intel() {
  const navigate = useNavigate();
  const regime = useMarketRegime('scanner');

  // Fear & Greed state
  const [fearGreed, setFearGreed] = useState<FearGreedData | null>(null);

  // Fetch Fear & Greed Index on mount
  useEffect(() => {
    api.getFearGreedIndex().then(res => {
      if (res.data) {
        setFearGreed(res.data);
      }
    });
  }, []);

  const { btcContext } = useSymbolCycles({
    symbols: ['BTCUSDT'],
    exchange: 'phemex'
  });

  // Extract dominance data
  const btcDom = regime.btcDominance ?? 52.5;
  const usdtDom = regime.usdtDominance ?? 6.2;
  const ethDom = 17.5; // Estimated
  const altsDom = Math.max(0, 100 - btcDom - ethDom - usdtDom);

  // Extract cycle data
  const fourYearCycle = btcContext?.four_year_cycle;
  const phase = fourYearCycle?.phase ?? 'DISTRIBUTION';
  const macroBias = fourYearCycle?.macro_bias ?? 'BEARISH';
  const daysSinceLow = fourYearCycle?.days_since_low ?? 770;

  // Use Fear & Greed data for bottom line, with fallback to cycle-based logic
  const bottomLineText = fearGreed?.bottom_line ?? (
    macroBias === 'BULLISH'
      ? "The structural trend remains unequivocally bullish. Pullbacks are for buying, not for shorting."
      : "Structure has broken. The path of least resistance is down until proven otherwise."
  );

  const riskText = fearGreed?.risk_text ?? (
    macroBias === 'BULLISH'
      ? "over-leveraged late longs flushing out"
      : "short squeezes on relief rallies"
  );

  // Sentiment classification for display
  const sentimentLabel = fearGreed?.classification ?? (macroBias === 'BULLISH' ? 'Greed' : 'Fear');
  const sentimentValue = fearGreed?.value ?? 50;

  // Date formatting
  const today = new Date();
  const dateStr = today.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  }).toUpperCase();

  // Gauge data for FourYearCycleGauge
  const gaugeData = fourYearCycle || {
    days_since_low: 770,
    days_until_expected_low: 690,
    cycle_position_pct: 78,
    phase: 'DISTRIBUTION',
    phase_progress_pct: 56,
    last_low: { date: '2022-11-21', price: 15476, event: 'FTX Collapse' },
    expected_next_low: '2026-10-15',
    macro_bias: 'BEARISH',
    confidence: 72,
    zones: { is_danger_zone: true, is_opportunity_zone: false }
  };

  return (
    <div className="intel-page">
      {/* Header */}
      <header className="intel-header">
        <div>
          <div className="intel-header-badge">⚡ SNIPERS SIGHT</div>
          <h1>GLOBAL INTELLIGENCE COMMAND</h1>
          <p>Market Structure Analysis • Regime Detection • Institutional Flow</p>
        </div>
        <button
          className="intel-close-btn"
          onClick={() => navigate('/')}
          aria-label="Close"
        >
          <X size={24} />
        </button>
      </header>

      {/* Main Content */}
      <main className="intel-main">
        {/* Two Column: Brief + Radar */}
        <div className="intel-grid-2col">
          {/* Market Brief Section */}
          <section className="intel-section">
            <div className="intel-section-header">
              <h2>MARKET BRIEF: {macroBias} STRUCTURE</h2>
              <span className="timestamp">{dateStr} // SNIPERS SIGHT INTEL</span>
            </div>

            <div className="brief-content">
              <div className="bottom-line">
                <h3>THE BOTTOM LINE:</h3>
                <p>{bottomLineText}</p>
              </div>

              <div className="analysis-block">
                <h3>◎ CYCLE ANALYSIS</h3>
                <p>We are tracking the daily cycle development. Day {daysSinceLow} since the macro low.</p>
                <p>Our proprietary 4-Year Cycle Gauge (<strong>{phase}</strong>) indicates we are structurally positioned for {macroBias.toLowerCase()} continuation.</p>
              </div>

              <div className="risk-block">
                <h3>⚠ RISK ASSESSMENT</h3>
                <p>Volatility remains elevated. Leverage should be reduced.</p>
                <p>The primary risk at this moment is <strong>{riskText}</strong>.</p>
              </div>

              <div className="philosophy-block">
                <p className="quote">"In a bull market, bad news is ignored. In a bear market, good news is sold."</p>
                <p className="source">— TRADING PHILOSOPHY</p>
              </div>
            </div>
          </section>

          {/* Capital Flow Radar */}
          <section className="intel-section radar-section">
            <div className="intel-section-header">
              <h2>CAPITAL FLOW RADAR</h2>
              <span className="subtitle">CAPITAL ROTATION RADAR</span>
            </div>

            <div className="radar-content">
              {/* Radar Chart */}
              <div className="chart-placeholder">
                <RadarVisualization />
              </div>

              {/* Dominance Grid */}
              <div className="narratives-grid">
                <div className="narrative-card">
                  <span className="narrative-label">BTC.D</span>
                  <span className="narrative-value">{btcDom.toFixed(1)}%</span>
                  <span className="narrative-trend">↑</span>
                </div>
                <div className="narrative-card">
                  <span className="narrative-label">USDT.D</span>
                  <span className="narrative-value">{usdtDom.toFixed(1)}%</span>
                  <span className="narrative-trend">↑</span>
                </div>
                <div className="narrative-card">
                  <span className="narrative-label">ETH.D</span>
                  <span className="narrative-value">{ethDom.toFixed(1)}%</span>
                  <span className="narrative-trend down">↓</span>
                </div>
                <div className="narrative-card">
                  <span className="narrative-label">ALTS.D</span>
                  <span className="narrative-value">{altsDom.toFixed(1)}%</span>
                  <span className="narrative-trend down">↓</span>
                </div>
              </div>

              {/* Active Narratives */}
              <div className="active-narratives">
                <h3>ACTIVE NARRATIVES</h3>
                <div className="narrative-list">
                  <div className="narrative-item">
                    <span className="label">AI Agents</span>
                    <span className="sentiment strong">STRONG</span>
                  </div>
                  <div className="narrative-item">
                    <span className="label">RWA</span>
                    <span className="sentiment moderate">MODERATE</span>
                  </div>
                  <div className="narrative-item">
                    <span className="label">Meme Coins</span>
                    <span className="sentiment weak">WEAK</span>
                  </div>
                  <div className="narrative-item">
                    <span className="label">L2 Scaling</span>
                    <span className="sentiment moderate">MODERATE</span>
                  </div>
                  <div className="narrative-item">
                    <span className="label">Gaming</span>
                    <span className="sentiment weak">WEAK</span>
                  </div>
                </div>
              </div>

              {/* Total Line */}
              <div className="total-line">
                <span>Total Market Cap</span>
                <span>{(btcDom + ethDom + usdtDom + altsDom).toFixed(1)}%</span>
              </div>
            </div>
          </section>
        </div>

        {/* Cycle Intelligence - Full Width */}
        <section className="intel-section full-width">
          <div className="intel-section-header">
            <h2>CYCLE INTELLIGENCE</h2>
            <p className="subtitle">Price action moves in waves. We track the 4-Year Macro Cycle and fractal daily/weekly cycles to determine structural health.</p>
          </div>

          <div className="cycle-grid">
            {/* Cycle Theory Box */}
            <div className="cycle-box">
              <h3>Cycle Theory 101</h3>
              <p className="theory-text">Price structure dictates market health. Understanding "Translation" is key to identifying cycle tops.</p>

              <div className="cycle-chart-placeholder">
                <div className="placeholder-text">📊 Cycle Chart Area</div>
                <div className="placeholder-description">Right Translation • Cycle Peak • Recension Analysis</div>
              </div>

              <div className="axiom-block">
                <h3>◎ CAMEL FINANCE AXIOM</h3>
                <p className="axiom-text">"Price structure is truth. Narrative is noise. When price holds up late in a cycle, the narrative will turn bullish to justify it."</p>
              </div>
            </div>

            {/* 4-Year Halving Cycle - Full width gauge, no duplicate header */}
            <div className="cycle-box four-year-gauge-container">
              <FourYearCycleGauge data={gaugeData} className="hud-gauge-override" />
            </div>
          </div>
        </section>

        {/* Deep Dive Analysis - Full Width */}
        <section className="intel-section full-width">
          <div className="intel-section-header">
            <h2>DEEP DIVE ANALYSIS</h2>
            <p className="subtitle">Market leader context for all trades</p>
          </div>

          <BTCCycleIntel autoRefresh={false} />
        </section>
      </main>
    </div>
  );
}

export default Intel;
