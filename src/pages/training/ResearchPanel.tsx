import { SectionHead } from '@/components/hud';
import { mlService, type FeatureImportanceItem, type MLStatus } from '@/services/mlService';
import { useEffect, useState } from 'react';
import { StatTile } from '../TradeJournalViews';
export function MLPanel() {
    const [status, setStatus] = useState<MLStatus | null>(null);
    const [importance, setImportance] = useState<FeatureImportanceItem[]>([]);
    const [training, setTraining] = useState(false);
    const [trainMsg, setTrainMsg] = useState<string | null>(null);
    const [loadingStatus, setLoadingStatus] = useState(true);
    const [clearing, setClearing] = useState(false);
    const [clearConfirm, setClearConfirm] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [resetConfirm, setResetConfirm] = useState(false);
    const fetchStatus = async () => {
        try {
            const s = await mlService.getStatus();
            setStatus(s);
            if (s.trained) {
                const feats = await mlService.getFeatureImportance();
                setImportance(feats.slice(0, 12));
            }
        }
        catch {
            // backend may not be running yet
        }
        finally {
            setLoadingStatus(false);
        }
    };
    useEffect(() => {
        fetchStatus();
    }, []);
    const handleResetModel = async () => {
        if (!resetConfirm) {
            setResetConfirm(true);
            setTimeout(() => setResetConfirm(false), 4000);
            return;
        }
        setResetConfirm(false);
        setResetting(true);
        setTrainMsg(null);
        try {
            const result = await mlService.resetModel();
            setTrainMsg(result.message);
            setImportance([]);
            await fetchStatus();
        }
        catch (e) {
            setTrainMsg(e instanceof Error ? e.message : 'Reset failed');
        }
        finally {
            setResetting(false);
        }
    };
    const handleClearLogs = async () => {
        if (!clearConfirm) {
            setClearConfirm(true);
            setTimeout(() => setClearConfirm(false), 4000);
            return;
        }
        setClearConfirm(false);
        setClearing(true);
        setTrainMsg(null);
        try {
            const result = await mlService.clearSessionLogs();
            setTrainMsg(result.message);
            await fetchStatus();
        }
        catch (e) {
            setTrainMsg(e instanceof Error ? e.message : 'Clear failed');
        }
        finally {
            setClearing(false);
        }
    };
    const handleTrain = async () => {
        setTraining(true);
        setTrainMsg(null);
        try {
            const result = await mlService.train();
            setTrainMsg(result.message);
            await fetchStatus();
        }
        catch (e) {
            setTrainMsg(e instanceof Error ? e.message : 'Training failed');
        }
        finally {
            setTraining(false);
        }
    };
    const accuracy = typeof status?.accuracy === "number" && Number.isFinite(status.accuracy) ? status.accuracy : null;
    const accuracyColor = accuracy == null ? "var(--fg-3)" : accuracy >= 0.65 ? "var(--green-soft)" : accuracy >= 0.55 ? "var(--amber)" : "var(--red-2)";
    // SHAP bar dimensions
    const maxImportance = importance.length ? Math.max(...importance.map(i => i.importance)) : 1;
    return (<section className="panel">
      <SectionHead title="Edge Model" right={<div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button className="btn" style={{
                padding: '4px 10px',
                fontSize: 10,
                color: resetConfirm ? 'var(--red-2)' : undefined,
                borderColor: resetConfirm ? 'rgba(248,113,113,.6)' : undefined,
            }} disabled={resetting || training || clearing} onClick={handleResetModel} title="Delete trained model. The model is unavailable until retrained.">
              {resetting ? 'RESETTING…' : resetConfirm ? 'CONFIRM RESET?' : 'RESET MODEL'}
            </button>
            <button className="btn" style={{
                padding: '4px 10px',
                fontSize: 10,
                color: clearConfirm ? 'var(--red-2)' : undefined,
                borderColor: clearConfirm ? 'rgba(248,113,113,.6)' : undefined,
            }} disabled={clearing || training || resetting} onClick={handleClearLogs} title="Clear all session signal logs (trained model is preserved)">
              {clearing ? 'CLEARING…' : clearConfirm ? 'CONFIRM CLEAR?' : 'CLEAR LOGS'}
            </button>
            <button className="btn btn-cyan" style={{ padding: '4px 10px', fontSize: 10 }} disabled={training || clearing || resetting} onClick={handleTrain}>
              {training ? 'TRAINING…' : 'TRAIN MODEL'}
            </button>
          </div>}/>
      <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {loadingStatus ? (<div className="mono" style={{ fontSize: 11, color: 'var(--fg-4)' }}>
            // loading model status…
          </div>) : !status ? (<div className="mono" style={{ fontSize: 11, color: 'var(--fg-4)' }}>
            // backend not reachable
          </div>) : (<>
            <div className="journal-breakdown-meta-grid">
              <StatTile label="Status" value={status.trained ? 'TRAINED' : 'UNTRAINED'} color={status.trained ? 'var(--green-soft)' : 'var(--fg-3)'}/>
              <StatTile label="Model" value={status.model_type === 'none' ? '—' : status.model_type}/>
              <StatTile label="Samples" value={String(status.n_samples)} sub={`min ${status.min_samples_required}`}/>
              <StatTile label="CV Accuracy" value={status.trained && accuracy != null && accuracy != null ? `${(accuracy * 100).toFixed(1)}%` : 'Unknown'} sub={status.trained ? 'purged walk-fwd' : undefined} color={accuracyColor}/>
            </div>

            {(status as {
                available_signals?: number;
            }).available_signals != null && (<div style={{
                    border: '1px solid var(--border-soft)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(0,0,0,.3)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontFamily: 'JetBrains Mono,monospace',
                    fontSize: 11,
                    color: 'var(--fg-3)',
                }}>
                <span>Training data available</span>
                <span style={{
                    color: ((status as {
                        available_signals?: number;
                    }).available_signals ?? 0) >= 10
                        ? 'var(--green-soft)'
                        : 'var(--amber)',
                    fontWeight: 700,
                }}>
                  {(status as {
                available_signals?: number;
            }).available_signals} signals ·{' '}
                  {(status as {
                available_trades?: number;
            }).available_trades ?? 0} trades
                </span>
              </div>)}

            {!status.trained &&
                ((status as {
                    available_signals?: number;
                }).available_signals ?? 0) < 10 && (<div style={{
                    border: '1px solid rgba(245,158,11,.3)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(245,158,11,.05)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--amber)',
                }}>
                  Let the bot run a bit longer — need at least 10 signals to train. Currently have{' '}
                  {(status as {
                available_signals?: number;
            }).available_signals ?? 0}.
                </div>)}
            {status.trained && accuracy != null && accuracy != null && accuracy < 0.55 && (<div style={{
                    border: '1px solid rgba(248,113,113,.3)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(248,113,113,.05)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--red-2)',
                }}>
                Cross-validation accuracy below 55%. Research only; this does not establish trading performance.
              </div>)}
            {status.trained && accuracy != null && accuracy >= 0.65 && (<div style={{
                    border: '1px solid rgba(34,197,94,.3)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(34,197,94,.05)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--green-soft)',
                }}>
                Cross-validation is a research result, not a live win probability. Feature directions describe model attribution.
              </div>)}
            {status.trained && accuracy != null && accuracy >= 0.55 && accuracy < 0.65 && (<div style={{
                    border: '1px solid rgba(245,158,11,.3)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(245,158,11,.05)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--amber)',
                }}>
                Cross-validation accuracy is not calibrated to live outcomes. Inspect the research sample and feature attribution.
              </div>)}

            {trainMsg && (<div style={{
                    border: '1px solid var(--border-soft)',
                    borderRadius: 6,
                    padding: '8px 12px',
                    background: 'rgba(0,0,0,.3)',
                    fontSize: 11,
                    fontFamily: 'JetBrains Mono,monospace',
                    fontWeight: 700,
                    color: trainMsg.toLowerCase().includes('success') || trainMsg.toLowerCase().includes('trained')
                        ? 'var(--green-soft)'
                        : trainMsg.toLowerCase().includes('no training') || trainMsg.toLowerCase().includes('need')
                            ? 'var(--amber)'
                            : 'var(--red-2)',
                }}>
                {trainMsg}
              </div>)}

            {importance.length > 0 && (<div>
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                }}>
                  <div className="mono" style={{
                    fontSize: 9,
                    color: 'var(--fg-4)',
                    letterSpacing: '.18em',
                    textTransform: 'uppercase',
                }}>
                    // SHAP feature importance
                  </div>
                  <div style={{
                    display: 'flex',
                    gap: 12,
                    fontSize: 9,
                    fontFamily: 'JetBrains Mono,monospace',
                    color: 'var(--fg-4)',
                }}>
                    <span>
                      <span style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    background: 'var(--green-soft)',
                    marginRight: 4,
                }}/>
                      positive model attribution
                    </span>
                    <span>
                      <span style={{
                    display: 'inline-block',
                    width: 8,
                    height: 8,
                    background: 'var(--red-2)',
                    marginRight: 4,
                }}/>
                      negative model attribution
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {importance.map(item => {
                    const w = (item.importance / maxImportance) * 100;
                    const c = item.direction >= 0 ? 'var(--green-soft)' : 'var(--red-2)';
                    return (<div key={item.name} className="journal-breakdown-row" style={{
                            fontFamily: 'JetBrains Mono,monospace',
                            fontSize: 10,
                        }}>
                        <span style={{ color: 'var(--fg-2)', textAlign: 'right' }}>
                          {item.name}
                        </span>
                        <div style={{
                            position: 'relative',
                            height: 14,
                            background: 'rgba(0,0,0,.3)',
                            border: '1px solid var(--border-soft)',
                            borderRadius: 2,
                        }}>
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            bottom: 0,
                            left: 0,
                            width: w + '%',
                            background: c,
                            opacity: 0.7,
                            borderRadius: '0 2px 2px 0',
                        }}/>
                        </div>
                        <span style={{ color: c, fontWeight: 700, textAlign: 'right' }}>
                          {item.importance.toFixed(3)}
                        </span>
                      </div>);
                })}
                </div>
              </div>)}
          </>)}
      </div>
    </section>);
}
