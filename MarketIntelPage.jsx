import React, { useState } from 'react';
import { X, TrendingDown, Activity, Zap, BarChart3 } from 'lucide-react';

const MarketIntelPage = ({ onClose }) => {
  return (
    <div className="market-intel-page">
      {/* Header */}
      <header className="intel-header">
        <div className="header-content">
          <div className="header-badge">⚡ SNIPERS SIGHT</div>
          <h1>GLOBAL INTELLIGENCE COMMAND</h1>
          <p>Market Structure Analysis • Regime Detection • Institutional Flow</p>
        </div>
        <button className="close-btn" onClick={onClose} aria-label="Close">
          <X size={24} />
        </button>
      </header>

      {/* Main Content */}
      <main className="intel-main">
        {/* Two Column: Brief + Radar */}
        <div className="intel-grid-2col">
          {/* Market Brief Section */}
          <section className="intel-section">
            <div className="section-header">
              <h2>MARKET BRIEF: BEARISH STRUCTURE</h2>
              <span className="timestamp">WEDNESDAY, DECEMBER 31 // SNIPERS SIGHT INTEL</span>
            </div>

            <div className="brief-content">
              <div className="bottom-line">
                <h3>THE BOTTOM LINE:</h3>
                <p>Structure has broken. The path of least resistance is down until proven otherwise.</p>
              </div>

              <div className="analysis-block">
                <h3>@CYCLE ANALYSIS</h3>
                <p>We are early in the new daily cycle. This is typically the safest window for long entries.</p>
                <p>Our proprietary 4-Year Cycle (DISTRIBUTION) indicates we are structurally positioned for bearish continuation.</p>
              </div>

              <div className="risk-block warning">
                <h3>⚠ RISK ASSESSMENT</h3>
                <p>Volatility remains elevated. Leverage should be reduced.</p>
                <p>The primary risk at this moment is <strong>short squeezes on relief rallies</strong>.</p>
              </div>

              <div className="philosophy-block">
                <p className="quote">"In a bull market, bad news is ignored. In a bear market, good news is sold."</p>
                <p className="source">— TRADING PHILOSOPHY</p>
              </div>
            </div>
          </section>

          {/* Capital Flow Radar */}
          <section className="intel-section radar-section">
            <div className="section-header">
              <h2>CAPITAL FLOW RADAR</h2>
              <span className="subtitle">CAPITAL ROTATION RADAR</span>
            </div>

            <div className="radar-content">
              {/* Placeholder Chart Area */}
              <div className="chart-placeholder">
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
                  </svg>
                </div>
              </div>

              {/* Narratives Grid */}
              <div className="narratives-grid">
                <div className="narrative-card">
                  <span className="narrative-label">BTC.D</span>
                  <span className="narrative-value">52.5%</span>
                  <span className="narrative-trend">↑</span>
                </div>
                <div className="narrative-card">
                  <span className="narrative-label">USDT.D</span>
                  <span className="narrative-value">6.2%</span>
                  <span className="narrative-trend">↑</span>
                </div>
                <div className="narrative-card">
                  <span className="narrative-label">ETH.D</span>
                  <span className="narrative-value">17.5%</span>
                  <span className="narrative-trend">↓</span>
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
            </div>
          </section>
        </div>

        {/* Cycle Intelligence - Full Width */}
        <section className="intel-section full-width">
          <div className="section-header">
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

            {/* 4-Year Halving Cycle */}
            <div className="cycle-box">
              <h3>4-YEAR HALVING CYCLE</h3>
              <div className="halving-chart-placeholder">
                <div className="placeholder-visual">📈 Halving Cycle Chart</div>
                <div className="cycle-labels">
                  <span>MKD</span>
                  <span className="active">78% ↗</span>
                </div>
              </div>

              {/* Distribution Section */}
              <div className="distribution-box">
                <h3>⚠ DISTRIBUTION</h3>
                <p className="subtitle-sm">Smart money exiting - manage risk carefully</p>
                
                <div className="distribution-visual">
                  <span className="phase-label">Phase Shift</span>
                  <span className="phase-value">MACRO BEARISH</span>
                </div>

                <div className="macro-dates">
                  <div className="date-block">
                    <span className="date-label">@LAST 4YC LOW</span>
                    <span className="date-value">Nov 2022</span>
                    <span className="date-price">$15,476</span>
                  </div>
                  <div className="date-block">
                    <span className="date-label">@EXPECTED NEXT LOW</span>
                    <span className="date-value">Nov 2026</span>
                    <span className="date-price">~0 days</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Deep Dive Analysis - Full Width */}
        <section className="intel-section full-width">
          <div className="section-header">
            <h2>DEEP DIVE ANALYSIS</h2>
            <p className="subtitle">Market leader context for all trades</p>
          </div>

          <div className="deepdive-grid">
            <div className="deepdive-card">
              <h3>BTC Cycle Intelligence</h3>
              <p className="card-subtitle">Daily Cycle</p>
              <div className="placeholder-content">
                <div className="placeholder-bar">Chart Area</div>
                <div className="placeholder-bar">Timeframe Data</div>
              </div>
            </div>

            <div className="deepdive-card">
              <h3>Market Narratives</h3>
              <p className="card-subtitle">Sentiment Tracker</p>
              <div className="placeholder-content">
                <div className="placeholder-bar">Active Narratives</div>
                <div className="placeholder-bar">Strength Gauge</div>
              </div>
            </div>

            <div className="deepdive-card">
              <h3>Institutional Positioning</h3>
              <p className="card-subtitle">Smart Money Flow</p>
              <div className="placeholder-content">
                <div className="placeholder-bar">Order Block Analysis</div>
                <div className="placeholder-bar">Liquidity Zones</div>
              </div>
            </div>

            <div className="deepdive-card">
              <h3>Risk/Reward Zones</h3>
              <p className="card-subtitle">Entry Setup Quality</p>
              <div className="placeholder-content">
                <div className="placeholder-bar">High Probability Setups</div>
                <div className="placeholder-bar">Risk Management</div>
              </div>
            </div>
          </div>
        </section>
      </main>

      <style jsx>{`
        .market-intel-page {
          background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
          color: #0ff;
          min-height: 100vh;
          font-family: 'Monaco', 'Courier New', monospace;
          overflow-x: hidden;
        }

        .intel-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 2rem 3rem;
          border-bottom: 2px solid #0ff;
          background: rgba(0, 255, 255, 0.05);
          backdrop-filter: blur(10px);
          position: sticky;
          top: 0;
          z-index: 100;
        }

        .header-badge {
          font-size: 0.75rem;
          letter-spacing: 2px;
          color: #0f0;
          margin-bottom: 0.5rem;
          text-transform: uppercase;
        }

        .header-content h1 {
          font-size: 2.2rem;
          font-weight: 700;
          letter-spacing: 3px;
          margin: 0;
          color: #0ff;
          text-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
        }

        .header-content p {
          font-size: 0.85rem;
          color: #0f0;
          margin: 0.5rem 0 0 0;
          letter-spacing: 1px;
          text-transform: uppercase;
        }

        .close-btn {
          background: none;
          border: 2px solid #0ff;
          color: #0ff;
          cursor: pointer;
          padding: 0.5rem;
          border-radius: 4px;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .close-btn:hover {
          background: rgba(0, 255, 255, 0.1);
          box-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
        }

        .intel-main {
          padding: 2rem 3rem;
          max-width: 100%;
        }

        .intel-grid-2col {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 2rem;
          margin-bottom: 2rem;
        }

        @media (max-width: 1400px) {
          .intel-grid-2col {
            grid-template-columns: 1fr;
          }
        }

        .intel-section {
          background: rgba(0, 255, 255, 0.02);
          border: 1px solid rgba(0, 255, 255, 0.15);
          border-radius: 8px;
          padding: 2rem;
          backdrop-filter: blur(10px);
          box-shadow: 0 8px 32px rgba(0, 255, 255, 0.05);
        }

        .intel-section.full-width {
          grid-column: 1 / -1;
          margin-bottom: 2rem;
        }

        .section-header {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          margin-bottom: 1.5rem;
          border-bottom: 2px solid rgba(0, 255, 255, 0.2);
          padding-bottom: 1rem;
        }

        .section-header h2 {
          font-size: 1.4rem;
          letter-spacing: 2px;
          margin: 0;
          color: #0ff;
          text-shadow: 0 0 8px rgba(0, 255, 255, 0.2);
        }

        .section-header .timestamp,
        .section-header .subtitle {
          font-size: 0.75rem;
          letter-spacing: 1px;
          color: #0f0;
          text-transform: uppercase;
          margin: 0;
        }

        /* Brief Content */
        .brief-content {
          display: flex;
          flex-direction: column;
          gap: 1.2rem;
        }

        .bottom-line,
        .analysis-block,
        .risk-block,
        .philosophy-block {
          padding: 1rem;
          border-left: 3px solid rgba(0, 255, 255, 0.3);
          background: rgba(0, 255, 255, 0.02);
          border-radius: 4px;
        }

        .bottom-line {
          border-left-color: #0f0;
          background: rgba(0, 255, 0, 0.02);
        }

        .analysis-block h3 {
          color: #0ff;
          font-size: 0.9rem;
          letter-spacing: 1px;
          margin: 0 0 0.5rem 0;
        }

        .risk-block {
          border-left-color: #ff6b00;
          background: rgba(255, 107, 0, 0.05);
        }

        .risk-block h3 {
          color: #ff6b00;
          font-size: 0.9rem;
          letter-spacing: 1px;
          margin: 0 0 0.5rem 0;
        }

        .risk-block p {
          margin: 0.3rem 0;
          font-size: 0.9rem;
        }

        .risk-block strong {
          color: #ff6b00;
        }

        .philosophy-block {
          background: rgba(0, 255, 0, 0.02);
          border-left-color: #0f0;
          padding: 1.2rem;
        }

        .quote {
          font-style: italic;
          color: #0f0;
          margin: 0 0 0.5rem 0;
          font-size: 0.95rem;
        }

        .source {
          font-size: 0.75rem;
          color: #0f0;
          letter-spacing: 1px;
          margin: 0;
          text-transform: uppercase;
        }

        /* Radar Section */
        .radar-section {
          display: flex;
          flex-direction: column;
        }

        .radar-content {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .chart-placeholder {
          background: rgba(0, 255, 0, 0.02);
          border: 1px dashed rgba(0, 255, 0, 0.3);
          border-radius: 8px;
          padding: 2rem;
          min-height: 200px;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
        }

        .radar-visual {
          width: 100%;
          height: 200px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .radar-svg {
          width: 100%;
          height: 100%;
          max-width: 200px;
          max-height: 200px;
        }

        @keyframes radarSweep {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }

        .radar-sweep {
          transform-origin: 100px 100px;
          animation: radarSweep 4s linear infinite;
        }

        .narratives-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1rem;
        }

        .narrative-card {
          background: rgba(0, 255, 255, 0.05);
          border: 1px solid rgba(0, 255, 255, 0.2);
          border-radius: 6px;
          padding: 1rem;
          text-align: center;
          display: flex;
          flex-direction: column;
          gap: 0.3rem;
        }

        .narrative-label {
          font-size: 0.75rem;
          color: #0f0;
          letter-spacing: 1px;
          text-transform: uppercase;
        }

        .narrative-value {
          font-size: 1.3rem;
          color: #0ff;
          font-weight: 700;
        }

        .narrative-trend {
          font-size: 1rem;
          color: #0f0;
        }

        .active-narratives {
          background: rgba(0, 255, 255, 0.02);
          border: 1px solid rgba(0, 255, 255, 0.15);
          border-radius: 6px;
          padding: 1rem;
        }

        .active-narratives h3 {
          font-size: 0.9rem;
          letter-spacing: 1px;
          color: #0ff;
          margin: 0 0 0.8rem 0;
          text-transform: uppercase;
        }

        .narrative-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .narrative-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.5rem 0.7rem;
          background: rgba(0, 255, 255, 0.03);
          border-radius: 4px;
          border-left: 2px solid rgba(0, 255, 255, 0.2);
          font-size: 0.85rem;
        }

        .narrative-item .label {
          color: #fff;
        }

        .sentiment {
          font-size: 0.7rem;
          letter-spacing: 1px;
          font-weight: 700;
          text-transform: uppercase;
          padding: 0.2rem 0.5rem;
          border-radius: 3px;
        }

        .sentiment.strong {
          background: rgba(0, 255, 0, 0.2);
          color: #0f0;
        }

        .sentiment.moderate {
          background: rgba(255, 107, 0, 0.2);
          color: #ff6b00;
        }

        .sentiment.weak {
          background: rgba(255, 100, 100, 0.2);
          color: #ff6464;
        }

        /* Cycle Intelligence */
        .cycle-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 2rem;
        }

        @media (max-width: 1200px) {
          .cycle-grid {
            grid-template-columns: 1fr;
          }
        }

        .cycle-box {
          background: rgba(0, 255, 255, 0.03);
          border: 1px solid rgba(0, 255, 255, 0.15);
          border-radius: 8px;
          padding: 1.5rem;
          display: flex;
          flex-direction: column;
          gap: 1.2rem;
        }

        .cycle-box h3 {
          font-size: 1rem;
          color: #0ff;
          letter-spacing: 1px;
          margin: 0;
          text-transform: uppercase;
        }

        .theory-text {
          font-size: 0.9rem;
          color: #fff;
          margin: 0;
          line-height: 1.5;
        }

        .cycle-chart-placeholder {
          background: rgba(0, 255, 0, 0.03);
          border: 1px dashed rgba(0, 255, 0, 0.3);
          border-radius: 6px;
          padding: 2rem;
          text-align: center;
          min-height: 150px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
        }

        .placeholder-text {
          color: #0f0;
          font-size: 0.9rem;
          letter-spacing: 1px;
        }

        .placeholder-description {
          color: #0f0;
          font-size: 0.75rem;
          letter-spacing: 1px;
          text-transform: uppercase;
        }

        .axiom-block {
          background: rgba(0, 255, 255, 0.05);
          border-left: 3px solid #0ff;
          padding: 1rem;
          border-radius: 4px;
        }

        .axiom-block h3 {
          font-size: 0.85rem;
          color: #0ff;
          letter-spacing: 1px;
          margin: 0 0 0.5rem 0;
          text-transform: uppercase;
        }

        .axiom-text {
          font-size: 0.9rem;
          color: #fff;
          margin: 0;
          line-height: 1.5;
          font-style: italic;
        }

        .halving-chart-placeholder {
          background: rgba(0, 255, 0, 0.03);
          border: 1px dashed rgba(0, 255, 0, 0.3);
          border-radius: 6px;
          padding: 2rem;
          text-align: center;
          min-height: 150px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 1rem;
        }

        .placeholder-visual {
          color: #0f0;
          font-size: 0.9rem;
        }

        .cycle-labels {
          display: flex;
          justify-content: space-around;
          width: 100%;
          font-size: 0.85rem;
          color: #0f0;
        }

        .cycle-labels .active {
          color: #ff6b00;
          font-weight: 700;
        }

        .distribution-box {
          background: rgba(255, 107, 0, 0.05);
          border-left: 3px solid #ff6b00;
          padding: 1rem;
          border-radius: 4px;
        }

        .distribution-box h3 {
          font-size: 0.9rem;
          color: #ff6b00;
          margin: 0 0 0.5rem 0;
          letter-spacing: 1px;
        }

        .subtitle-sm {
          font-size: 0.75rem;
          color: #ff6b00;
          margin: 0 0 0.8rem 0;
          text-transform: uppercase;
        }

        .distribution-visual {
          background: rgba(255, 107, 0, 0.1);
          border: 1px solid rgba(255, 107, 0, 0.3);
          border-radius: 4px;
          padding: 1rem;
          margin-bottom: 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.3rem;
        }

        .phase-label {
          font-size: 0.75rem;
          color: #ff6b00;
          letter-spacing: 1px;
          text-transform: uppercase;
        }

        .phase-value {
          font-size: 1.1rem;
          color: #ff6b00;
          font-weight: 700;
        }

        .macro-dates {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 0.8rem;
        }

        .date-block {
          background: rgba(255, 107, 0, 0.05);
          border: 1px solid rgba(255, 107, 0, 0.2);
          border-radius: 4px;
          padding: 0.8rem;
          display: flex;
          flex-direction: column;
          gap: 0.3rem;
        }

        .date-label {
          font-size: 0.7rem;
          color: #ff6b00;
          letter-spacing: 1px;
          text-transform: uppercase;
        }

        .date-value {
          font-size: 0.95rem;
          color: #fff;
          font-weight: 700;
        }

        .date-price {
          font-size: 0.75rem;
          color: #ff6b00;
        }

        /* Deep Dive Analysis */
        .deepdive-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 2rem;
        }

        @media (max-width: 1000px) {
          .deepdive-grid {
            grid-template-columns: 1fr;
          }
        }

        .deepdive-card {
          background: rgba(0, 255, 255, 0.03);
          border: 1px solid rgba(0, 255, 255, 0.15);
          border-radius: 8px;
          padding: 1.5rem;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .deepdive-card h3 {
          font-size: 1rem;
          color: #0ff;
          letter-spacing: 1px;
          margin: 0;
          text-transform: uppercase;
        }

        .deepdive-card .card-subtitle {
          font-size: 0.75rem;
          color: #0f0;
          letter-spacing: 1px;
          margin: 0;
          text-transform: uppercase;
        }

        .placeholder-content {
          display: flex;
          flex-direction: column;
          gap: 0.8rem;
        }

        .placeholder-bar {
          background: rgba(0, 255, 255, 0.05);
          border: 1px dashed rgba(0, 255, 255, 0.2);
          border-radius: 4px;
          height: 60px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: rgba(0, 255, 255, 0.5);
          font-size: 0.85rem;
          letter-spacing: 1px;
        }
      `}</style>
    </div>
  );
};

export default MarketIntelPage;
