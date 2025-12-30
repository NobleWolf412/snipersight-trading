import { PageContainer } from '@/components/layout/PageContainer';
import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Crosshair, Lightning, CaretDown, CaretUp,
  Globe, CurrencyBtc, Biohazard, Target, Activity, Cpu, Coin
} from '@phosphor-icons/react';
import { convertSignalToScanResult, generateDemoScanResults } from '@/utils/mockData';
import { TacticalSelector, TacticalSlider, TacticalToggle, TacticalDropdown } from '@/components/ui/TacticalInputs';
import { Slider } from '@/components/ui/slider';
import { ScannerModeTabs } from '@/components/scanner/ScannerModeTabs';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { scanHistoryService } from '@/services/scanHistoryService';
import { ScannerConsole } from '@/components/ScannerConsole';
import { debugLogger } from '@/utils/debugLogger';
import { validateScannerConfig, hasBlockingErrors, getSeverityColor, getSeverityIcon } from '@/utils/scannerValidation';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode, addConsoleLog, clearConsoleLogs } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ current: number; total: number; symbol?: string } | null>(null);
  const [consoleExpanded, setConsoleExpanded] = useState(false);
  const { toast } = useToast();
  // Validation
  const validationIssues = useMemo(() =>
    validateScannerConfig(scanConfig, selectedMode),
    [scanConfig, selectedMode]
  );
  const hasErrors = hasBlockingErrors(validationIssues);

  // New state for Confluence Gate override
  const [minScoreOverride, setMinScoreOverride] = useState<number>(selectedMode?.min_confluence_score || 0);

  // AI Recommendation State
  const [recommendation, setRecommendation] = useState<{
    mode: string;
    reason: string;
    warning: string | null;
    confidence: string;
  } | null>(null);

  useEffect(() => {
    if (selectedMode) {
      setMinScoreOverride(selectedMode.min_confluence_score);
    }
  }, [selectedMode]);

  useEffect(() => {
    clearConsoleLogs();

    // Fetch AI Recommendation
    const fetchRec = async () => {
      try {
        const res = await api.getScannerRecommendation();
        if (res.data) setRecommendation(res.data);
      } catch (e) {
        console.error("Failed to fetch recommendation", e);
      }
    };
    fetchRec();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleArmScanner = async () => {
    setIsScanning(true);
    setScanProgress({ current: 0, total: scanConfig.topPairs || 20 });
    setConsoleExpanded(true); // Auto-expand console during scan
    const startedAt = Date.now();
    let heartbeatId: number | null = null;

    localStorage.removeItem('scan-results');
    localStorage.removeItem('scan-metadata');
    localStorage.removeItem('scan-rejections');

    debugLogger.info('━━━ SCAN INITIATED ━━━', 'scanner');
    debugLogger.info(`[CONFIG] Mode: ${scanConfig.sniperMode.toUpperCase()}`, 'scanner');
    debugLogger.info(`[CONFIG] Exchange: ${scanConfig.exchange} | Leverage: ${scanConfig.leverage}x`, 'scanner');
    debugLogger.info(`[CONFIG] Categories: Majors=${scanConfig.categories.majors}, Alts=${scanConfig.categories.altcoins}, Meme=${scanConfig.categories.memeMode}`, 'scanner');
    debugLogger.info(`[CONFIG] Pairs: ${scanConfig.topPairs} | Min Score: ${selectedMode?.min_confluence_score || 0}%`, 'scanner');
    debugLogger.info(`API Base URL: ${api.baseURL}`, 'scanner');

    try {
      debugLogger.info('Sending request to backend...', 'scanner');

      const runResponse = await api.createScanRun({
        limit: scanConfig.topPairs || 20,
        min_score: minScoreOverride || 0,
        sniper_mode: scanConfig.sniperMode,
        majors: scanConfig.categories.majors,
        altcoins: scanConfig.categories.altcoins,
        meme_mode: scanConfig.categories.memeMode,
        exchange: scanConfig.exchange,
        leverage: scanConfig.leverage || 1,
        macro_overlay: scanConfig.macroOverlay,
        market_type: scanConfig.marketType,
      });

      if (runResponse.error || !runResponse.data) {
        debugLogger.error(`Scan failed to start: ${runResponse.error || 'No data received'}`, 'scanner');
        throw new Error(runResponse.error || 'Failed to start scan');
      }

      const runId = runResponse.data.run_id;
      debugLogger.success(`✓ Scan queued (ID: ${runId.slice(0, 8)}...)`, 'scanner');
      debugLogger.info(`━━━ STARTING ANALYSIS PIPELINE ━━━`, 'scanner');

      // Heartbeat every 10s to show we're still alive (reduced from 2s to avoid log spam)
      heartbeatId = window.setInterval(() => {
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        const timeStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
        debugLogger.info(`[STATUS] Scan in progress... ${timeStr}`, 'scanner');
      }, 10000);

      let jobStatus = 'queued';
      let pollAttempts = 0;
      const MAX_POLL_ATTEMPTS = 300;
      let lastProgress = 0;
      let lastLogCount = 0;

      while ((jobStatus === 'queued' || jobStatus === 'running') && pollAttempts < MAX_POLL_ATTEMPTS) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        pollAttempts++;

        const statusRes = await api.getScanRun(runId, { silent: true });
        if (statusRes.error || !statusRes.data) {
          if (!statusRes.error?.includes('timeout')) {
            debugLogger.warning(`Poll attempt ${pollAttempts}: ${statusRes.error}`, 'scanner');
          }
          continue;
        }

        const job = statusRes.data;
        jobStatus = job.status;

        setScanProgress({
          current: job.progress,
          total: job.total,
          symbol: job.current_symbol
        });

        try {
          if (job.logs && Array.isArray(job.logs) && job.logs.length > lastLogCount) {
            const newLogs = job.logs.slice(lastLogCount);
            newLogs.forEach((logMsg: string) => {
              if (!logMsg || typeof logMsg !== 'string') return;
              const parts = logMsg.split(' | ');
              if (parts.length < 2) {
                debugLogger.info(logMsg, 'scanner');
                return;
              }
              const [level, ...msgParts] = parts;
              const msg = msgParts.join(' | ');
              if (level === 'INFO') debugLogger.info(msg, 'scanner');
              else if (level === 'WARNING') debugLogger.warning(msg, 'scanner');
              else if (level === 'ERROR') debugLogger.error(msg, 'scanner');
              else debugLogger.info(msg, 'scanner');
            });
            lastLogCount = job.logs.length;
          }
        } catch (logError) {
          console.error('[Scanner] Log parsing error:', logError);
        }

        if (job.total > 0 && job.progress !== lastProgress && job.progress % 5 === 0) {
          debugLogger.info(`⚡ Progress: ${job.progress}/${job.total} symbols analyzed`, 'scanner');
          lastProgress = job.progress;
        }

        if (jobStatus === 'completed') {
          const data = job;
          debugLogger.info(`━━━ ANALYSIS COMPLETE ━━━`, 'scanner');
          debugLogger.success(`✓ Signals Generated: ${data.signals?.length || 0}`, 'scanner');
          debugLogger.info(`📊 Symbols Scanned: ${data.metadata?.scanned || 0}`, 'scanner');
          debugLogger.info(`🚫 Rejected: ${data.metadata?.rejected || 0}`, 'scanner');

          const results = (data.signals || []).map(convertSignalToScanResult);
          localStorage.setItem('scan-results', JSON.stringify(results));

          // Transform rejections to match frontend RejectionDossier expected format
          // Backend returns: { details: { low_confluence: [...], ... } }
          // Frontend expects: { low_confluence: [...], ... } (flat structure)
          const rawRejections = data.rejections || {};
          const flattenedRejections = rawRejections.details || {
            low_confluence: rawRejections.low_confluence || [],
            risk_validation: rawRejections.risk_validation || [],
            no_trade_plan: rawRejections.no_trade_plan || [],
            missing_critical_tf: rawRejections.missing_critical_tf || [],
            errors: rawRejections.errors || [],
          };

          const metadata = {
            mode: data.metadata?.mode || scanConfig.sniperMode,
            appliedTimeframes: data.metadata?.applied_timeframes || [],
            effectiveMinScore: data.metadata?.effective_min_score || 0,
            baselineMinScore: selectedMode?.min_confluence_score || 0,
            profile: selectedMode?.profile || 'default',
            scanned: data.metadata?.scanned || 0,
            rejected: data.metadata?.rejected || 0,
            exchange: data.metadata?.exchange,
            leverage: data.metadata?.leverage,
            criticalTimeframes: selectedMode?.critical_timeframes || [],
            rejections: flattenedRejections, // Include rejections for RejectionDossier
          };
          localStorage.setItem('scan-metadata', JSON.stringify(metadata));

          if (data.rejections) {
            localStorage.setItem('scan-rejections', JSON.stringify(data.rejections));
          }

          scanHistoryService.saveScan({
            mode: metadata.mode,
            profile: metadata.profile,
            timeframes: metadata.appliedTimeframes,
            symbolsScanned: metadata.scanned,
            signalsGenerated: results.length,
            signalsRejected: metadata.rejected,
            effectiveMinScore: metadata.effectiveMinScore,
            rejectionBreakdown: data.rejections?.by_reason,
            results: results,
          });

          debugLogger.success(`━━━ SCAN COMPLETE: ${results.length} signals ━━━`, 'scanner');

          if (results.length === 0) {
            toast({
              title: 'No Setups Found',
              description: `Scanned ${metadata.scanned || 0} symbols - all rejected. Try adjusting mode or threshold.`,
              variant: 'destructive',
            });
          } else {
            toast({
              title: 'Targets Acquired',
              description: `${results.length} high-conviction setups identified`,
            });
          }

          if (heartbeatId) {
            clearInterval(heartbeatId);
            heartbeatId = null;
          }
          setIsScanning(false);
          setScanProgress(null);
          navigate('/results');
          return;
        }

        if (jobStatus === 'failed') {
          throw new Error(job.error || 'Scan job failed on backend');
        }

        if (jobStatus === 'cancelled') {
          throw new Error('Scan job was cancelled');
        }
      }

      if (pollAttempts >= MAX_POLL_ATTEMPTS) {
        throw new Error('Scan timed out waiting for completion');
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      debugLogger.error(`━━━ SCAN FAILED ━━━`, 'scanner');
      debugLogger.error(`Error: ${errorMessage}`, 'scanner');
      debugLogger.warning('Falling back to demo results...', 'scanner');
      if (heartbeatId) {
        clearInterval(heartbeatId);
        heartbeatId = null;
      }

      console.error('Scanner error:', error);
      const demo = generateDemoScanResults(Math.min(scanConfig.topPairs || 5, 5), scanConfig.sniperMode);
      localStorage.setItem('scan-results', JSON.stringify(demo));
      localStorage.setItem('scan-rejections', JSON.stringify({
        total_rejected: 0,
        by_reason: {},
        details: {},
      }));
      localStorage.setItem('scan-metadata', JSON.stringify({
        mode: scanConfig.sniperMode,
        appliedTimeframes: scanConfig.timeframes,
        effectiveMinScore: selectedMode?.min_confluence_score || 0,
        baselineMinScore: selectedMode?.min_confluence_score || 0,
        profile: selectedMode?.profile || 'default',
        scanned: demo.length,
        offline: true,
        offlineReason: errorMessage,
      }));

      toast({
        title: 'Operating Offline',
        description: `${errorMessage}. Showing ${demo.length} demo setups.`,
        variant: 'destructive',
      });

      setIsScanning(false);
      setScanProgress(null);
      navigate('/results');
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden" id="main-content">
      <main className="py-8 lg:py-12">
        <PageContainer>
          <div className="max-w-7xl mx-auto space-y-8">

            {/* Header */}
            <div className="text-center space-y-3">
              <div className="inline-flex items-center gap-3 px-4 py-2 glass-card-subtle glow-border-green">
                <div className="w-2 h-2 bg-accent rounded-full animate-pulse shadow-[0_0_8px_rgba(0,255,170,0.8)]" />
                <span className="text-xs tracking-[0.3em] text-accent/80 uppercase">Scanner Ready</span>
              </div>
              <h1 className="text-3xl lg:text-4xl font-bold hud-headline hud-text-green">SCANNER SETUP</h1>
              <p className="text-base lg:text-lg text-muted-foreground max-w-xl mx-auto">
                Configure your reconnaissance parameters and select your operational mode
              </p>
            </div>

            {/* Market Type Selection - Centered Top */}
            <div className="flex justify-center max-w-md mx-auto w-full">
              <TacticalSelector
                label="MARKET TYPE"
                value={scanConfig.marketType || 'swap'}
                onChange={(val) => {
                  // Force leverage to 1 if switching to spot
                  const updates = { marketType: val };
                  if (val === 'spot') {
                    updates['leverage'] = 1;
                  }
                  setScanConfig({ ...scanConfig, ...updates });
                  addConsoleLog(`CONFIG: Market type set to ${val.toUpperCase()}`, 'config');
                }}
                gridCols={2}
                variant="3d"
                centeredLabel={true}
                options={[
                  { value: 'swap', label: 'FUTURES', icon: <Activity className="text-purple-400" size={24} />, subLabel: 'PERPETUALS', color: '#a855f7' },
                  { value: 'spot', label: 'SPOT', icon: <Coin className="text-yellow-400" size={24} />, subLabel: 'ASSETS', color: '#eab308' },
                ]}
              />
            </div>



            {/* Mode Selection - Full Width */}
            <section className="glass-card glow-border-green p-4 lg:p-8 rounded-2xl">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
                <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-green">SELECT MODE</h2>

                {/* AI ADVISORY WIDGET */}
                {recommendation && (
                  <div
                    className={`flex items-center gap-3 px-4 py-2 rounded-lg backdrop-blur-sm border transition-all duration-500 animate-in fade-in slide-in-from-right-4 ${recommendation.warning
                      ? 'bg-yellow-500/10 border-yellow-500/30'
                      : 'bg-black/40 border-[#00ff88]/20'
                      }`}
                  >
                    <div className={`w-2 h-2 rounded-full ${recommendation.warning ? 'bg-yellow-500 animate-pulse' : 'bg-[#00ff88] animate-pulse'
                      }`} />
                    <span className={`text-xs font-mono uppercase tracking-wider ${recommendation.warning ? 'text-yellow-400' : 'text-[#00ff88]'
                      }`}>
                      AI RECON: <span className="font-bold text-white">{recommendation.mode.toUpperCase()}</span>
                    </span>

                    <div className="h-4 w-px bg-white/10 hidden lg:block" />

                    <span className="hidden lg:inline text-xs text-muted-foreground truncate max-w-[400px]" title={recommendation.reason}>
                      {recommendation.reason}
                    </span>

                    {/* Auto-select button if not active */}
                    {scanConfig.sniperMode !== recommendation.mode.toLowerCase() && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-[10px] px-2 ml-2 border border-white/10 hover:bg-white/10"
                        onClick={() => setScanConfig({ ...scanConfig, sniperMode: recommendation.mode.toLowerCase() as any })}
                      >
                        APPLY
                      </Button>
                    )}
                  </div>
                )}
              </div>
              <ScannerModeTabs />
            </section>

            {/* Configuration Panels - Two Column on Desktop */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Operational Parameters */}
              {/* TACTICAL CONFIGURATION (Was Operational Parameters) */}
              <section className="glass-card glow-border-green p-5 lg:p-6 rounded-2xl h-full flex flex-col relative overflow-hidden group">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
                <div className="flex items-center gap-3 mb-6 relative z-10">
                  <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-green tracking-wide">TACTICAL CONFIGURATION</h2>
                  <div className="h-px flex-1 bg-gradient-to-r from-[#00ff88]/30 to-transparent" />
                </div>

                <div className="flex-1 flex flex-col justify-between gap-10 lg:gap-12 relative z-10">

                  {/* 1. Server Uplink (Exchange) */}
                  <div className="w-full">
                    <TacticalDropdown
                      label="EXCHANGE UPLINK"
                      value={scanConfig.exchange}
                      onChange={(val) => setScanConfig({ ...scanConfig, exchange: val })}
                      options={[
                        { value: 'phemex', label: 'PHEMEX', icon: <Lightning weight="fill" className="text-amber-400" size={24} /> },
                        { value: 'bybit', label: 'BYBIT', icon: <Activity weight="bold" className="text-blue-400" size={24} />, disabled: true },
                        { value: 'binance', label: 'BINANCE', icon: <Globe weight="fill" className="text-yellow-500" size={24} />, disabled: true },
                        { value: 'coinbase', label: 'COINBASE', icon: <Target weight="bold" className="text-blue-600" size={24} />, disabled: true },
                        { value: 'kraken', label: 'KRAKEN', icon: <Cpu weight="bold" className="text-purple-500" size={24} />, disabled: true },
                      ]}
                    />
                  </div>

                  {/* 2. Risk Multiplier (Leverage) - HIDDEN for Spot */}
                  {(!scanConfig.marketType || scanConfig.marketType === 'swap') ? (
                    <div>
                      <div className="flex items-end justify-between mb-4">
                        <div>
                          <label className="block text-base font-bold font-mono text-[#00ff88] tracking-widest uppercase mb-1">RISK MULTIPLIER (LEVERAGE)</label>
                          <p className="text-sm text-muted-foreground">Capital Exposure Factor</p>
                        </div>
                        <div className="flex items-center gap-3 bg-black/40 border border-white/10 px-3 py-1.5 rounded-lg">
                          <span className="text-2xl font-bold font-mono tabular-nums leading-none" style={{ color: (scanConfig.leverage || 1) <= 5 ? '#00ff88' : (scanConfig.leverage || 1) <= 10 ? '#fbbf24' : '#ef4444' }}>
                            {scanConfig.leverage || 1}x
                          </span>
                        </div>
                      </div>
                      <Slider
                        value={[scanConfig.leverage || 1]}
                        onValueChange={(val) => {
                          setScanConfig({ ...scanConfig, leverage: val[0] });
                          addConsoleLog(`CONFIG: Leverage set to ${val[0]}x`, 'config');
                        }}
                        min={1}
                        max={20}
                        step={1}
                        zones={[
                          { limit: 5, color: '#00ff88', label: 'SAFE' },
                          { limit: 10, color: '#fbbf24', label: 'MODERATE' },
                          { limit: 20, color: '#ef4444', label: 'HIGH' },
                        ]}
                      />
                    </div>
                  ) : (
                    /* Disabled/Hidden State for Spot */
                    <div className="opacity-50 pointer-events-none grayscale">
                      <div className="flex items-end justify-between mb-4">
                        <div>
                          <label className="block text-base font-bold font-mono text-muted-foreground tracking-widest uppercase mb-1">LEVERAGE DISABLED</label>
                          <p className="text-sm text-muted-foreground">Not available for Spot markets</p>
                        </div>
                        <div className="flex items-center gap-3 bg-black/40 border border-white/5 px-3 py-1.5 rounded-lg">
                          <span className="text-2xl font-bold font-mono tabular-nums leading-none text-muted-foreground">
                            1x
                          </span>
                        </div>
                      </div>
                      <div className="h-16 flex items-center justify-center border-2 border-white/5 rounded-full bg-black/20">
                        <span className="font-mono text-xs text-muted-foreground tracking-widest">SPOT EXECUTION ONLY</span>
                      </div>
                    </div>
                  )}

                  {/* 3. Confluence Gate (Min Score) */}
                  <div>
                    <div className="flex items-end justify-between mb-4">
                      <div>
                        <label className="block text-base font-bold font-mono text-[#00ff88] tracking-widest uppercase mb-1">CONFLUENCE GATE</label>
                        <p className="text-sm text-muted-foreground">Only show setups scoring above this %</p>
                      </div>
                      <div className="flex items-center gap-3 bg-black/40 border border-white/10 px-3 py-1.5 rounded-lg">
                        <span className="text-xs font-bold px-2 py-0.5 rounded-sm bg-black/60 border border-white/5 uppercase tracking-wider" style={{ color: minScoreOverride <= 60 ? '#fbbf24' : minScoreOverride <= 75 ? '#00ff88' : '#3b82f6' }}>
                          {minScoreOverride <= 60 ? 'AGGRESSIVE' : minScoreOverride <= 75 ? 'BALANCED' : 'ELITE'}
                        </span>
                        <span className="text-2xl font-bold font-mono tabular-nums leading-none" style={{ color: minScoreOverride <= 60 ? '#fbbf24' : minScoreOverride <= 75 ? '#00ff88' : '#3b82f6' }}>
                          {minScoreOverride}%
                        </span>
                      </div>
                    </div>
                    <Slider
                      value={[minScoreOverride]}
                      onValueChange={(val) => setMinScoreOverride(val[0])}
                      min={40}
                      max={90}
                      step={1}
                      zones={[
                        { limit: 60, color: '#fbbf24', label: 'AGGRESSIVE' },
                        { limit: 75, color: '#00ff88', label: 'BALANCED' },
                        { limit: 90, color: '#3b82f6', label: 'ELITE' },
                      ]}
                    />
                  </div>

                  {/* 4. Scan Scope (Pairs) */}
                  <TacticalSelector
                    label="SCAN SCOPE"
                    value={scanConfig.topPairs.toString()}
                    onChange={(val) => setScanConfig({ ...scanConfig, topPairs: Number(val) })}
                    gridCols={3}
                    options={[
                      { value: '10', label: 'RECON', subLabel: 'TOP 10', icon: <Target size={24} /> },
                      { value: '20', label: 'TACTICAL', subLabel: 'TOP 20', icon: <Crosshair size={24} /> },
                      { value: '50', label: 'DEEP', subLabel: 'TOP 50', icon: <Globe size={24} /> },
                    ]}
                  />

                </div>
              </section>

              {/* TARGET SECTORS (Was Asset Categories) */}
              <section className="glass-card glow-border-green p-5 lg:p-6 rounded-2xl h-full flex flex-col relative overflow-hidden group">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-green-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
                <div className="flex items-center gap-3 mb-6 relative z-10">
                  <h2 className="text-xl lg:text-2xl font-semibold hud-headline hud-text-green tracking-wide">TARGET SECTORS</h2>
                  <div className="h-px flex-1 bg-gradient-to-r from-[#00ff88]/30 to-transparent" />
                </div>

                <div className="grid gap-3 flex-1 content-start relative z-10">
                  <TacticalToggle
                    label="MAJORS"
                    sublabel="BTC, ETH, SOL (High Liquidity)"
                    tooltip="Top-tier cryptocurrencies with massive trading volumes. Lower volatility, tighter spreads, and more predictable price action. Best for consistent setups."
                    checked={scanConfig.categories.majors}
                    onChange={(checked) => setScanConfig({ ...scanConfig, categories: { ...scanConfig.categories, majors: checked } })}
                    icon={<CurrencyBtc size={32} weight="duotone" />}
                  />

                  <TacticalToggle
                    label="ALTCOINS"
                    sublabel="High Volatility Targets"
                    tooltip="Mid-cap altcoins outside the top 10. Higher volatility means bigger moves but less liquidity. Good for breakout plays and momentum trades."
                    checked={scanConfig.categories.altcoins}
                    onChange={(checked) => setScanConfig({ ...scanConfig, categories: { ...scanConfig.categories, altcoins: checked } })}
                    icon={<Lightning size={32} weight="duotone" />}
                  />

                  <TacticalToggle
                    label="MEME PROTOCOL"
                    sublabel="Extreme Risk / High Reward"
                    tooltip="⚠️ DEGEN MODE: Meme coins (DOGE, SHIB, PEPE, etc). Extreme volatility, thin liquidity, and unpredictable behavior. Only for high-risk traders who accept potential 50%+ swings."
                    checked={scanConfig.categories.memeMode}
                    onChange={(checked) => setScanConfig({ ...scanConfig, categories: { ...scanConfig.categories, memeMode: checked } })}
                    icon={<Biohazard size={32} weight="duotone" />}
                    isHazard={true}
                  />

                  <div className="h-px bg-white/5 my-2" />

                  <TacticalToggle
                    label="MACRO OVERLAY"
                    sublabel="Adjust scores based on BTC.D"
                    tooltip="When enabled, trade scores are adjusted based on the overall market regime. If BTC Dominance is rising (Risk-Off), altcoin longs get penalized. If capital is flowing into alts (Risk-On), altcoin longs get boosted. Helps you avoid swimming upstream."
                    checked={scanConfig.macroOverlay}
                    onChange={(checked) => {
                      setScanConfig({ ...scanConfig, macroOverlay: checked });
                      addConsoleLog(`CONFIG: Macro overlay ${checked ? 'enabled' : 'disabled'}`, 'config');
                    }}
                    icon={<Globe size={32} weight="duotone" />}
                  />
                </div>
              </section>
            </div>

            {/* Validation Warnings */}
            {validationIssues.length > 0 && (
              <div className="space-y-3">
                {validationIssues.map((issue) => (
                  <div
                    key={issue.id}
                    className={`flex items-start gap-4 p-4 lg:p-5 rounded-xl border-l-4 glass-card-subtle transition-all duration-300 ${issue.severity === 'error' ? 'border-l-red-500 glow-border-red' : 'border-l-yellow-500 glow-border-yellow'
                      }`}
                  >
                    <span className={`text-xl mt-0.5 p-2 rounded-lg bg-black/20 ${issue.severity === 'error' ? 'text-red-400' : 'text-yellow-400'}`}>
                      {getSeverityIcon(issue.severity)}
                    </span>
                    <div className="flex-1">
                      <p className="font-semibold text-lg tracking-wide">{issue.message}</p>
                      {issue.suggestion && (
                        <p className="text-base text-muted-foreground mt-1 leading-relaxed">💡 {issue.suggestion}</p>
                      )}
                    </div>
                    {issue.autoFix && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          if (issue.autoFix) {
                            const fix = issue.autoFix.apply(scanConfig);
                            setScanConfig({ ...scanConfig, ...fix });
                            addConsoleLog(`AUTO-FIX: ${issue.autoFix.label}`, 'success');
                          }
                        }}
                        className="shrink-0 font-mono tracking-wider border-dashed hover:border-solid hover:bg-accent/10 hover:text-accent"
                      >
                        {issue.autoFix.label}
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Console - Collapsible */}
            <section className="glass-card glow-border-green rounded-2xl overflow-hidden">
              <button
                type="button"
                onClick={() => setConsoleExpanded(!consoleExpanded)}
                className="w-full flex items-center justify-between p-4 lg:p-5 hover:bg-white/5 transition-colors"
              >
                <h2 className="text-lg lg:text-xl font-semibold hud-headline hud-text-green">SCANNER CONSOLE</h2>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <span className="text-sm">{consoleExpanded ? 'Collapse' : 'Expand'}</span>
                  {consoleExpanded ? <CaretUp size={20} /> : <CaretDown size={20} />}
                </div>
              </button>
              {consoleExpanded && (
                <div className="px-4 lg:px-5 pb-4 lg:pb-5">
                  <div className="h-[500px] lg:h-[600px]">
                    <ScannerConsole
                      isScanning={isScanning}
                      className="h-full"
                      progressCurrent={scanProgress?.current}
                      progressTotal={scanProgress?.total}
                    />
                  </div>
                </div>
              )}
            </section>

            {/* Arm Button */}
            <Button
              onClick={handleArmScanner}
              disabled={isScanning || scanConfig.timeframes.length === 0 || hasErrors}
              className="w-full h-14 lg:h-16 text-lg lg:text-xl relative z-10 btn-tactical-scanner"
              size="lg"
            >
              {isScanning ? (
                <>
                  <Lightning size={26} className="mr-2 animate-pulse" />
                  {scanProgress && scanProgress.total > 0
                    ? `Scanning ${scanProgress.current}/${scanProgress.total}${scanProgress.symbol ? ` • ${scanProgress.symbol}` : ''}`
                    : 'Initializing Scan...'
                  }
                </>
              ) : (
                <>
                  <Crosshair size={26} className="mr-2" />
                  ARM SCANNER
                </>
              )}
            </Button>

            {/* Progress Bar */}
            {scanProgress && scanProgress.total > 0 && (
              <div className="h-2 lg:h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{ width: `${(scanProgress.current / scanProgress.total) * 100}%` }}
                />
              </div>
            )}
          </div>
        </PageContainer>
      </main>
    </div>
  );
}
