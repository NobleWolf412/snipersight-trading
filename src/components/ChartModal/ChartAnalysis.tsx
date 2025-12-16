import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { CircleNotch, Sparkle, TrendUp, TrendDown, Warning } from '@phosphor-icons/react';
import type { ScanResult } from '@/utils/mockData';
import { MarkdownViewer } from '@/components/MarkdownViewer';

interface ChartAnalysisProps {
  result: ScanResult;
}

// Helper function for adaptive number formatting
const formatAdaptive = (v: number) => {
  if (v >= 1000) return v.toFixed(5);
  if (v >= 100) return v.toFixed(5);
  if (v >= 10) return v.toFixed(5);
  if (v >= 1) return v.toFixed(5);
  if (v >= 0.1) return v.toFixed(5);
  if (v >= 0.01) return v.toFixed(6);
  return v.toFixed(7);
};

export function ChartAnalysis({ result }: ChartAnalysisProps) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<string | null>(null);

  const generateLocalAnalysis = () => {
    const rr = ((result.takeProfits[0] - result.entryZone.high) / (result.entryZone.high - result.stopLoss));
    const maxGain = ((result.takeProfits[2] - result.entryZone.high) / result.entryZone.high * 100);
    const maxRisk = ((result.entryZone.high - result.stopLoss) / result.entryZone.high * 100);
    
    // Check for reversal setup
    const reversalInfo = result.reversal_context?.is_reversal_setup
      ? `\n\n🔄 **TREND REVERSAL DETECTED** (${result.reversal_context.confidence.toFixed(0)}% confidence)\n${result.reversal_context.rationale}\n${result.reversal_context.htf_bypass_active ? '⚡ *Strong reversal - HTF alignment bypassed*' : ''}\n${result.reversal_context.cycle_aligned ? '📊 *Aligned with cycle extreme (DCL/WCL zone)*' : ''}`
      : '';

    const trendAnalysis = result.trendBias === 'BULLISH'
      ? '📈 **Bullish Setup**: Price action shows upward momentum with higher timeframe alignment supporting long positions.' + reversalInfo
      : result.trendBias === 'BEARISH'
      ? '📉 **Bearish Setup**: Downward pressure evident with HTF structure favoring short positions.' + reversalInfo
      : '↔️ **Neutral Setup**: Mixed signals suggest caution; wait for clearer directional bias.';
    
    const confidenceAnalysis = result.confidenceScore >= 80
      ? `🎯 **High Confidence (${result.confidenceScore.toFixed(0)}%)**: Strong confluence across multiple timeframes with fresh SMC structures.`
      : result.confidenceScore >= 65
      ? `✅ **Moderate Confidence (${result.confidenceScore.toFixed(0)}%)**: Decent setup with acceptable confluence, proceed with standard position sizing.`
      : `⚠️ **Lower Confidence (${result.confidenceScore.toFixed(0)}%)**: Marginal setup; consider reducing size or waiting for confirmation.`;
    
    const riskAnalysis = result.riskScore < 4
      ? '🛡️ **Low Risk**: Favorable setup with controlled downside exposure.'
      : result.riskScore < 7
      ? '⚖️ **Medium Risk**: Balanced risk profile; maintain proper position sizing.'
      : '🚨 **High Risk**: Elevated exposure; consider tighter stops or smaller positions.';
    
    const conviction = result.conviction_class === 'A'
      ? '⭐ **Grade A Conviction**: Premium setup with complete SMC structure and HTF alignment.'
      : result.conviction_class === 'B'
      ? '✨ **Grade B Conviction**: Solid setup meeting quality thresholds.'
      : '💡 **Grade C Conviction**: Acceptable setup but monitor closely for invalidation.';
    
    const entryStrategy = result.classification === 'SWING'
      ? `**Swing Trade Approach**: Enter within the zone $${formatAdaptive(result.entryZone.low)} - $${formatAdaptive(result.entryZone.high)} using limit orders. Allow 4H+ candles to confirm structure before full position.`
      : `**Scalp Trade Approach**: Quick entry on lower timeframe confirmation within $${formatAdaptive(result.entryZone.low)} - $${formatAdaptive(result.entryZone.high)}. Target TP1-TP2 for rapid exits.`;
    
    const targets = result.takeProfits.map((tp, i) => 
      `- **TP${i + 1}**: $${formatAdaptive(tp)} (+${((tp - result.entryZone.high) / result.entryZone.high * 100).toFixed(2)}%)`
    ).join('\n');
    
    return `## ${result.pair} Trade Analysis

${trendAnalysis}

${confidenceAnalysis}

${conviction}

### Trade Setup

${entryStrategy}

**Stop Loss**: $${formatAdaptive(result.stopLoss)} (-${maxRisk.toFixed(2)}%)
- ${result.plan_type === 'SMC' ? 'Structure-based stop below key order block' : 'ATR-based stop for volatility protection'}

**Take Profit Targets**:
${targets}

**Risk/Reward Ratio**: ${rr.toFixed(2)}:1

${riskAnalysis}

### Smart Money Concepts

${result.orderBlocks.length > 0 ? `📦 **Order Blocks Identified**: ${result.orderBlocks.length} zone(s) providing institutional support/resistance.` : ''}

${result.fairValueGaps.length > 0 ? `⚡ **Fair Value Gaps**: ${result.fairValueGaps.length} imbalance zone(s) likely to attract price for rebalancing.` : ''}

${result.regime?.global_regime ? `🌍 **Market Regime**: ${result.regime.global_regime.composite} (Score: ${result.regime.global_regime.score}) - Adjust sizing based on broader market conditions.` : ''}

### Execution Notes

- **Entry Type**: ${result.classification}
- **Max Gain Potential**: +${maxGain.toFixed(2)}% at TP3
- **Max Risk**: -${maxRisk.toFixed(2)}% at stop loss
- Monitor HTF structure for invalidation signals
- Scale out at targets; don't wait for TP3 on full position

---
*This analysis is generated from Smart Money Concepts confluence scoring and structural analysis. Always validate with your own research.*`;
  };

  const generateAnalysis = async () => {
    setIsAnalyzing(true);
    
    try {
      // Try Spark LLM first if available
      if ((window as any).spark && typeof (window as any).spark.llm === 'function') {
        const promptText = `You are a professional crypto trader analyzing a ${result.pair} trading setup.

**Market Data:**
- Trend Bias: ${result.trendBias}
- Confidence Score: ${result.confidenceScore}%
- Risk Score: ${result.riskScore}/10
- Classification: ${result.classification}
- Entry Zone: $${formatAdaptive(result.entryZone.low)} - $${formatAdaptive(result.entryZone.high)}
- Stop Loss: $${formatAdaptive(result.stopLoss)}
- Take Profits: ${result.takeProfits.map((tp, i) => `TP${i + 1}: $${formatAdaptive(tp)}`).join(', ')}
- Order Blocks: ${result.orderBlocks.map(ob => `${ob.type} at $${ob.price} (${ob.timeframe})`).join(', ')}
- Fair Value Gaps: ${result.fairValueGaps.map(fvg => `${fvg.type} $${fvg.low}-$${fvg.high}`).join(', ')}

Provide a detailed technical analysis in markdown format with the following sections:

## Market Structure
Analyze the overall trend and market structure based on the bias and order blocks.

## Key Levels Analysis
Discuss the significance of entry zones, stop loss placement, and take profit targets.

## Risk Assessment
Evaluate the risk/reward ratio and overall risk score. Discuss position sizing recommendations.

## Trade Execution Plan
Provide step-by-step guidance on how to execute this trade, including entry strategy and profit-taking approach.

## Potential Challenges
Identify possible obstacles or scenarios that could invalidate the setup.

Be professional, concise, and actionable. Use bullet points where appropriate.`;

      const prompt = (window as any).spark.llmPrompt([promptText], promptText);
        // Try model, and provide a graceful fallback if the selected model is unavailable
        let response: string | undefined;
        const models = ['gpt-4o-mini'];
        let lastError: any = null;
        for (const model of models) {
          try {
            response = await (window as any).spark.llm(prompt, model);
            break;
          } catch (err) {
            lastError = err;
          }
        }
        if (!response) {
          throw lastError || new Error('Spark LLM call failed');
        }
        setAnalysis(response);
      } else {
        // Spark not available - use local analysis generator
        console.log('[ChartAnalysis] Spark not available, using local analysis generator');
        const localAnalysis = generateLocalAnalysis();
        setAnalysis(localAnalysis);
      }
    } catch (error) {
      console.error('[ChartAnalysis] Analysis generation error:', error);
      // Fallback to local analysis on any error
      const localAnalysis = generateLocalAnalysis();
      setAnalysis(localAnalysis);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <Card className="bg-card/30 border-accent/20">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Sparkle size={20} weight="fill" className="text-accent" />
            AI Chart Analysis
          </span>
          {!analysis && (
            <Button
              onClick={generateAnalysis}
              disabled={isAnalyzing}
              size="sm"
              className="bg-accent hover:bg-accent/90 text-accent-foreground"
            >
              {isAnalyzing ? (
                <>
                  <CircleNotch size={16} className="animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkle size={16} />
                  Generate Analysis
                </>
              )}
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!analysis && !isAnalyzing && (
          <div className="text-center py-8 text-muted-foreground">
            <Sparkle size={48} className="mx-auto mb-3 opacity-50" />
            <p>Click "Generate Analysis" to get AI-powered insights on this trading setup</p>
          </div>
        )}

        {isAnalyzing && (
          <div className="text-center py-12">
            <CircleNotch size={48} className="mx-auto mb-4 text-accent animate-spin" />
            <p className="text-muted-foreground">Analyzing chart patterns and market structure...</p>
          </div>
        )}

        {analysis && (
          <div className="space-y-4">
            <div className="flex justify-end">
              <Button
                onClick={generateAnalysis}
                disabled={isAnalyzing}
                size="sm"
                variant="outline"
              >
                <Sparkle size={14} />
                Regenerate
              </Button>
            </div>
            
            <Separator />
            
            <div className="prose prose-invert max-w-none">
              <MarkdownViewer content={analysis} />
            </div>

            <Separator />

            <div className="grid md:grid-cols-3 gap-3">
              <div className="bg-success/10 border border-success/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <TrendUp size={16} weight="bold" className="text-success" />
                  <span className="text-xs font-bold text-success">PROFIT POTENTIAL</span>
                </div>
                <div className="font-mono text-lg font-bold text-success">
                  +{((result.takeProfits[2] - result.entryZone.high) / result.entryZone.high * 100).toFixed(2)}%
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  At TP3: ${formatAdaptive(result.takeProfits[2])}
                </div>
              </div>

              <div className="bg-destructive/10 border border-destructive/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <TrendDown size={16} weight="bold" className="text-destructive" />
                  <span className="text-xs font-bold text-destructive">MAX RISK</span>
                </div>
                <div className="font-mono text-lg font-bold text-destructive">
                  -{((result.entryZone.high - result.stopLoss) / result.entryZone.high * 100).toFixed(2)}%
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  At SL: ${formatAdaptive(result.stopLoss)}
                </div>
              </div>

              <div className="bg-warning/10 border border-warning/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Warning size={16} weight="bold" className="text-warning" />
                  <span className="text-xs font-bold text-warning">RISK RATING</span>
                </div>
                <div className="font-mono text-lg font-bold text-warning">
                  {result.riskScore.toFixed(1)}/10
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {result.riskScore < 4 ? 'Low Risk' : result.riskScore < 7 ? 'Medium Risk' : 'High Risk'}
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
