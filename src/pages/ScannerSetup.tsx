import { PageContainer } from '@/components/layout/PageContainer';
import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useScanner } from '@/context/ScannerContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Crosshair, Lightning } from '@phosphor-icons/react';
import { convertSignalToScanResult, generateDemoScanResults } from '@/utils/mockData';
import { SniperModeSelector } from '@/components/SniperModeSelector';
import { api } from '@/utils/api';
import { useToast } from '@/hooks/use-toast';
import { scanHistoryService } from '@/services/scanHistoryService';
import { ScannerConsole } from '@/components/ScannerConsole';
import { debugLogger } from '@/utils/debugLogger';
import { HelpTooltip } from '@/components/HelpTooltip';
import { SCANNER_FIELD_HELP, getLeverageWarning } from '@/constants/scannerFieldHelp';
import { validateScannerConfig, hasBlockingErrors, getSeverityColor, getSeverityIcon, type ValidationIssue } from '@/utils/scannerValidation';
import { ASSET_PRESETS } from '@/constants/assetPresets';

export function ScannerSetup() {
  const navigate = useNavigate();
  const { scanConfig, setScanConfig, selectedMode, addConsoleLog, clearConsoleLogs } = useScanner();
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState<{ current: number; total: number; symbol?: string } | null>(null);
  const { toast } = useToast();
  // Local state for topPairs input to allow empty string
  const [topPairsInput, setTopPairsInput] = useState(scanConfig.topPairs.toString());

  // Validation - check config before arming
  const validationIssues = useMemo(() =>
    validateScannerConfig(scanConfig, selectedMode),
    [scanConfig, selectedMode]
  );
  const hasErrors = hasBlockingErrors(validationIssues);

  // Keep local input in sync with context changes
  useEffect(() => {
    setTopPairsInput(scanConfig.topPairs.toString());
  }, [scanConfig.topPairs]);

  // Clear any stale console logs when arriving on setup screen if not actively scanning
  useEffect(() => {
    clearConsoleLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleArmScanner = async () => {
    setIsScanning(true);
    setScanProgress({ current: 0, total: 0 });
    const startedAt = Date.now();
    let heartbeatId: number | null = null;

    // Clear previous results
    localStorage.removeItem('scan-results');
    localStorage.removeItem('scan-metadata');
    localStorage.removeItem('scan-rejections');

    // Log scan initialization
    debugLogger.info('━━━ SCAN INITIATED ━━━', 'scanner');
    debugLogger.info(`Mode: ${scanConfig.sniperMode.toUpperCase()}`, 'scanner');
    debugLogger.info(`Exchange: ${scanConfig.exchange} | Leverage: ${scanConfig.leverage}x`, 'scanner');
    debugLogger.info(`Categories: Majors=${scanConfig.categories.majors}, Alts=${scanConfig.categories.altcoins}, Meme=${scanConfig.categories.memeMode}`, 'scanner');
    debugLogger.info(`Target pairs: ${scanConfig.topPairs} | Min Score: ${selectedMode?.min_confluence_score || 0}`, 'scanner');
    debugLogger.info(`API Base URL: ${api.baseURL}`, 'scanner');

    try {
      debugLogger.info('Sending request to backend...', 'scanner');

      // 1. Start the scan run (Async)
      const runResponse = await api.createScanRun({
        limit: scanConfig.topPairs || 20,
        min_score: selectedMode?.min_confluence_score || 0,
        sniper_mode: scanConfig.sniperMode,
        majors: scanConfig.categories.majors,
        altcoins: scanConfig.categories.altcoins,
        meme_mode: scanConfig.categories.memeMode,
        exchange: scanConfig.exchange,
        leverage: scanConfig.leverage || 1,
        macro_overlay: scanConfig.macroOverlay,
      });

      if (runResponse.error || !runResponse.data) {
        debugLogger.error(`Scan failed to start: ${runResponse.error || 'No data received'}`, 'scanner');
        throw new Error(runResponse.error || 'Failed to start scan');
      }

      const runId = runResponse.data.run_id;
      debugLogger.success(`✓ Scan queued (ID: ${runId.slice(0, 8)}...)`, 'scanner');
      debugLogger.info(`━━━ STARTING ANALYSIS PIPELINE ━━━`, 'scanner');

      // Start heartbeat to show liveness during scan
      heartbeatId = window.setInterval(() => {
        const elapsed = Math.round((Date.now() - startedAt) / 1000);
        debugLogger.info(`⏳ Scanning... ${elapsed}s elapsed`, 'scanner');
      }, 2000);

      // 2. Poll for status
      let jobStatus = 'queued';
      let pollAttempts = 0;
      const MAX_POLL_ATTEMPTS = 300; // 5 minutes max
      let lastSymbol = '';
      let lastProgress = 0;
      let lastLogCount = 0; // Track how many backend logs we've displayed

      while ((jobStatus === 'queued' || jobStatus === 'running') && pollAttempts < MAX_POLL_ATTEMPTS) {
        await new Promise(resolve => setTimeout(resolve, 1000)); // Poll every 1s
        pollAttempts++;

        const statusRes = await api.getScanRun(runId, { silent: true });
        if (statusRes.error || !statusRes.data) {
          // Only log warning if it's not a timeout (which is silent now)
          if (!statusRes.error?.includes('timeout')) {
            debugLogger.warning(`Poll attempt ${pollAttempts}: ${statusRes.error}`, 'scanner');
          }
          continue; // Retry polling
        }

        const job = statusRes.data;
        jobStatus = job.status;

        // Update progress UI
        setScanProgress({
          current: job.progress,
          total: job.total,
          symbol: job.current_symbol
        });

        // Display new backend logs from orchestrator
        try {
          if (job.logs && Array.isArray(job.logs) && job.logs.length > lastLogCount) {
            const newLogs = job.logs.slice(lastLogCount);
            newLogs.forEach((logMsg: string) => {
              if (!logMsg || typeof logMsg !== 'string') return;

              // Parse log level and message
              const parts = logMsg.split(' | ');
              if (parts.length < 2) {
                // No level prefix, just log as info
                debugLogger.info(logMsg, 'scanner');
                return;
              }

              const [level, ...msgParts] = parts;
              const msg = msgParts.join(' | ');

              if (level === 'INFO') {
                debugLogger.info(msg, 'scanner');
              } else if (level === 'WARNING') {
                debugLogger.warning(msg, 'scanner');
              } else if (level === 'ERROR') {
                debugLogger.error(msg, 'scanner');
              } else {
                debugLogger.info(msg, 'scanner');
              }
            });
            lastLogCount = job.logs.length;
          }
        } catch (logError) {
          // Silently fail - don't let log parsing break the scanner
          console.error('[Scanner] Log parsing error:', logError);
        }

        // Show progress updates every 5 symbols
        if (job.total > 0 && job.progress !== lastProgress && job.progress % 5 === 0) {
          debugLogger.info(`⚡ Progress: ${job.progress}/${job.total} symbols analyzed`, 'scanner');
          lastProgress = job.progress;
        }

        if (jobStatus === 'completed') {
          // Process results
          const data = job;
          debugLogger.info(`━━━ ANALYSIS COMPLETE ━━━`, 'scanner');
          debugLogger.success(`✓ Signals Generated: ${data.signals?.length || 0}`, 'scanner');
          debugLogger.info(`📊 Symbols Scanned: ${data.metadata?.scanned || 0}`, 'scanner');
          debugLogger.info(`🚫 Rejected: ${data.metadata?.rejected || 0}`, 'scanner');

          const results = (data.signals || []).map(convertSignalToScanResult);
          localStorage.setItem('scan-results', JSON.stringify(results));

          // Metadata handling
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

          // Show appropriate message based on results
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
          console.log('[ScannerSetup] Scan complete, navigating to /results with', results.length, 'results');
          navigate('/results');
          return; // Exit function
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
      // Fallback to demo results to prevent empty UI when backend is unreachable (e.g., 504)
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
      }));

      toast({
        title: 'Operating Offline',
        description: `Backend unavailable or scan failed. Showing ${demo.length} demo setups.`,
      });

      setIsScanning(false);
      setScanProgress(null);
      console.log('[ScannerSetup] Fallback mode, navigating to /results with demo data');
      navigate('/results');
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden" id="main-content">
      <main className="py-10 md:py-14">
        <PageContainer>
          <div className="max-w-6xl mx-auto space-y-8">
            <div className="text-center space-y-2">
              <h1 className="text-3xl font-bold hud-headline hud-text-green">SCANNER SETUP</h1>
              <p className="hud-terminal text-primary/80">Configure your scanner parameters</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:items-stretch">
              <div className="lg:col-span-2 space-y-6">
                {/* Scan Mode */}
                <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d">
                  <h2 className="text-xl font-semibold mb-4 hud-headline hud-text-green">SCAN MODE & PROFILE</h2>
                  <SniperModeSelector />
                </div>

                {/* Operational Parameters */}
                <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d">
                  <h2 className="text-xl font-semibold mb-4 hud-headline hud-text-green">OPERATIONAL PARAMETERS</h2>
                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                      <div className="w-32 flex items-center justify-end gap-1">
                        <span id="exchange-label" className="text-base hud-terminal text-primary/90 tracking-wide">EXCHANGE</span>
                        <HelpTooltip
                          content={SCANNER_FIELD_HELP.exchange.tooltip}
                          example={SCANNER_FIELD_HELP.exchange.example}
                          warning={SCANNER_FIELD_HELP.exchange.warning}
                        />
                      </div>
                      <div className="flex-1 flex justify-end">
                        <Select
                          value={scanConfig.exchange}
                          onValueChange={(value) =>
                            setScanConfig({ ...scanConfig, exchange: value })
                          }
                        >
                          <SelectTrigger id="exchange" aria-label="Select Exchange" aria-labelledby="exchange-label" className="bg-background border-border hover:border-primary/50 transition-colors h-12 text-base font-mono">
                            <SelectValue placeholder="Exchange" />
                          </SelectTrigger>
                          <SelectContent className="font-mono">
                            <SelectItem value="phemex" className="text-base font-mono">⚡ Phemex (Fast, No Geo-Block)</SelectItem>
                            <SelectItem value="bybit" className="text-base font-mono">🔥 Bybit (May Be Geo-Blocked)</SelectItem>
                            <SelectItem value="okx" className="text-base font-mono">🏛️ OKX (May Be Geo-Blocked)</SelectItem>
                            <SelectItem value="bitget" className="text-base font-mono">🤖 Bitget</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="h-px bg-border/50" />

                    <div className="flex items-center gap-4">
                      <div className="w-32 flex items-center justify-end gap-1">
                        <span id="leverage-label" className="text-base hud-terminal text-primary/90 tracking-wide">LEVERAGE</span>
                        <HelpTooltip
                          content={SCANNER_FIELD_HELP.leverage.tooltip}
                          example={SCANNER_FIELD_HELP.leverage.example}
                          warning={SCANNER_FIELD_HELP.leverage.warning}
                        />
                      </div>
                      <div className="flex-1 flex flex-col items-end">
                        <Select
                          value={(scanConfig.leverage ?? 1).toString()}
                          onValueChange={(value) => {
                            const lev = parseInt(value);
                            setScanConfig({ ...scanConfig, leverage: lev });
                            addConsoleLog(`CONFIG: Leverage set to ${lev}x`, 'config');
                          }}
                        >
                          <SelectTrigger id="leverage" aria-label="Select Leverage" aria-labelledby="leverage-label" className="bg-background border-border hover:border-primary/50 transition-colors h-12 text-base font-mono">
                            <SelectValue placeholder="Leverage" />
                          </SelectTrigger>
                          <SelectContent className="font-mono">
                            <SelectItem value="1" className="text-base font-mono">1x (No Leverage)</SelectItem>
                            <SelectItem value="2" className="text-base font-mono">2x</SelectItem>
                            <SelectItem value="3" className="text-base font-mono">3x</SelectItem>
                            <SelectItem value="5" className="text-base font-mono">5x</SelectItem>
                            <SelectItem value="10" className="text-base font-mono">10x</SelectItem>
                            <SelectItem value="20" className="text-base font-mono">20x</SelectItem>
                            <SelectItem value="50" className="text-base font-mono">50x</SelectItem>
                            <SelectItem value="100" className="text-base font-mono">100x</SelectItem>
                            <SelectItem value="125" className="text-base font-mono">125x</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="h-px bg-border/50" />

                    <div className="flex items-center gap-4">
                      <div className="w-32 flex items-center justify-end gap-1">
                        <label htmlFor="top-pairs" id="top-pairs-label" className="text-base hud-terminal text-primary/90 tracking-wide">PAIRS TO SCAN</label>
                        <HelpTooltip
                          content={SCANNER_FIELD_HELP.topPairs.tooltip}
                          example={SCANNER_FIELD_HELP.topPairs.example}
                        />
                      </div>
                      <div className="flex-1 flex flex-col items-end">
                        <Input
                          id="top-pairs"
                          aria-labelledby="top-pairs-label"
                          type="number"
                          min="1"
                          max="100"
                          value={topPairsInput}
                          onChange={(e) => {
                            const val = e.target.value;
                            // Allow empty string for deletion
                            setTopPairsInput(val);
                            if (val === '') return;
                            const num = Number(val);
                            if (!isNaN(num) && num >= 1 && num <= 100) {
                              setScanConfig({ ...scanConfig, topPairs: num });
                            }
                          }}
                          className="h-12 text-lg w-20 max-w-24"
                        />
                        <p className="text-sm hud-terminal text-primary/60 mt-2 text-right">
                          Higher values scan more symbols but take longer
                        </p>
                      </div>
                    </div>

                  </div>
                </div>

                {/* Asset Categories */}
                <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d">
                  <h2 className="text-xl font-semibold mb-2 hud-headline hud-text-green">ASSET CATEGORIES</h2>
                  <p className="hud-terminal text-primary/80 mb-4">Quick presets or customize below</p>

                  {/* Asset Presets */}
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    {ASSET_PRESETS.map((preset) => {
                      const isActive =
                        scanConfig.categories.majors === preset.categories.majors &&
                        scanConfig.categories.altcoins === preset.categories.altcoins &&
                        scanConfig.categories.memeMode === preset.categories.memeMode;

                      return (
                        <button
                          key={preset.id}
                          type="button"
                          onClick={() => {
                            setScanConfig({
                              ...scanConfig,
                              categories: { ...preset.categories },
                            });
                            addConsoleLog(`CONFIG: Applied "${preset.name}" preset`, 'config');
                          }}
                          className={`p-3 rounded-lg border text-left transition-all ${isActive
                            ? 'border-primary bg-primary/20 ring-1 ring-primary/50'
                            : 'border-border/40 bg-background/40 hover:border-primary/30'
                            }`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-lg">{preset.icon}</span>
                            <span className={`text-sm font-medium ${isActive ? 'text-primary' : 'text-foreground'}`}>
                              {preset.name}
                            </span>
                            {preset.recommended && (
                              <Badge variant="outline" className="text-[10px] px-1 py-0 border-accent/50 text-accent">REC</Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">{preset.description}</p>
                          <div className="flex gap-2 mt-2 text-[10px] text-muted-foreground">
                            <span>📊 {preset.expectedSignals}</span>
                            <span className={preset.volatility === 'High' ? 'text-warning' : ''}>
                              ⚡ {preset.volatility}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className="h-px bg-border/30 my-4" />
                  <p className="text-xs text-muted-foreground mb-3">Or customize manually:</p>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                      <div className="flex items-center gap-1">
                        <span className="hud-terminal text-primary/90 tracking-wide">MAJORS</span>
                        <HelpTooltip
                          content={SCANNER_FIELD_HELP.majors.tooltip}
                          example={SCANNER_FIELD_HELP.majors.example}
                        />
                      </div>
                      <Switch
                        id="majors"
                        checked={scanConfig.categories.majors}
                        onCheckedChange={(checked) =>
                          setScanConfig({
                            ...scanConfig,
                            categories: { ...scanConfig.categories, majors: checked },
                          })
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                      <div className="flex items-center gap-1">
                        <span className="hud-terminal text-primary/90 tracking-wide">ALTCOINS</span>
                        <HelpTooltip
                          content={SCANNER_FIELD_HELP.altcoins.tooltip}
                          example={SCANNER_FIELD_HELP.altcoins.example}
                        />
                      </div>
                      <Switch
                        id="altcoins"
                        checked={scanConfig.categories.altcoins}
                        onCheckedChange={(checked) =>
                          setScanConfig({
                            ...scanConfig,
                            categories: { ...scanConfig.categories, altcoins: checked },
                          })
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1">
                          <span className="hud-terminal text-primary/90 tracking-wide">MEME MODE</span>
                          <HelpTooltip
                            content={SCANNER_FIELD_HELP.memeMode.tooltip}
                            warning={SCANNER_FIELD_HELP.memeMode.warning}
                          />
                        </div>
                        {scanConfig.categories.memeMode && (
                          <Badge variant="outline" className="text-xs hud-text-amber border-warning/50">HIGH VOLATILITY</Badge>
                        )}
                      </div>
                      <Switch
                        id="meme"
                        checked={scanConfig.categories.memeMode}
                        onCheckedChange={(checked) =>
                          setScanConfig({
                            ...scanConfig,
                            categories: { ...scanConfig.categories, memeMode: checked },
                          })
                        }
                      />
                    </div>

                    <div className="h-px bg-border/50 my-4" />

                    <div className="flex items-center justify-between p-3 rounded border border-border/40 bg-background/40 hover:border-primary/30 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1">
                          <span className="hud-terminal text-primary/90 tracking-wide">MACRO OVERLAY</span>
                          <HelpTooltip
                            content={SCANNER_FIELD_HELP.macroOverlay.tooltip}
                            example={SCANNER_FIELD_HELP.macroOverlay.example}
                          />
                        </div>
                        {scanConfig.macroOverlay && (
                          <Badge variant="outline" className="text-xs hud-text-green border-accent/50">DOMINANCE FLOW</Badge>
                        )}
                      </div>
                      <Switch
                        id="macro-overlay"
                        checked={scanConfig.macroOverlay}
                        onCheckedChange={(checked) => {
                          setScanConfig({
                            ...scanConfig,
                            macroOverlay: checked,
                          });
                          addConsoleLog(
                            `CONFIG: Macro overlay ${checked ? 'enabled' : 'disabled'} (BTC/ALT dominance flow)`,
                            'config'
                          );
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Console */}
              <div className="rounded-2xl p-6 md:p-8 backdrop-blur-sm card-3d relative z-0 flex flex-col h-[1200px]">
                <h2 className="text-xl font-semibold mb-4 hud-headline hud-text-green shrink-0">SCANNER CONSOLE</h2>
                <div className="flex-1 min-h-0 overflow-hidden">
                  <ScannerConsole
                    isScanning={isScanning}
                    className="h-full"
                  />
                </div>
              </div>
            </div>

            {/* Validation Warnings */}
            {validationIssues.length > 0 && (
              <div className="space-y-2 mb-4">
                {validationIssues.map((issue) => (
                  <div
                    key={issue.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border ${getSeverityColor(issue.severity)}`}
                  >
                    <span className="text-lg mt-0.5">{getSeverityIcon(issue.severity)}</span>
                    <div className="flex-1">
                      <p className="font-medium">{issue.message}</p>
                      {issue.suggestion && (
                        <p className="text-sm opacity-80 mt-0.5">
                          💡 {issue.suggestion}
                        </p>
                      )}
                    </div>
                    {issue.autoFix && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const fix = issue.autoFix!.apply(scanConfig);
                          setScanConfig({ ...scanConfig, ...fix });
                        }}
                        className="shrink-0"
                      >
                        {issue.autoFix.label}
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Arm Button */}
            <Button
              onClick={handleArmScanner}
              disabled={isScanning || scanConfig.timeframes.length === 0 || hasErrors}
              className="w-full h-14 text-lg relative z-10 btn-tactical-scanner"
              size="lg"
            >
              {isScanning ? (
                <>
                  <Lightning size={24} className="mr-2" />
                  {scanProgress && scanProgress.total > 0
                    ? `Scanning ${scanProgress.current}/${scanProgress.total}${scanProgress.symbol ? ` • ${scanProgress.symbol}` : ''}`
                    : 'Initializing Scan...'
                  }
                </>
              ) : (
                <>
                  <Crosshair size={24} className="mr-2" />
                  Arm Scanner
                </>
              )}
            </Button>

            {scanProgress && scanProgress.total > 0 && (
              <div className="h-2 bg-muted rounded-full overflow-hidden">
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
