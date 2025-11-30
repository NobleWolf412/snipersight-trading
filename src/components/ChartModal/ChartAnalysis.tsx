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

  const generateAnalysis = async () => {
    setIsAnalyzing(true);
    
    try {
      if (!(window as any).spark || typeof (window as any).spark.llm !== 'function') {
        throw new Error('Spark is not available in this environment.');
      }

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
    } catch (error) {
      console.error('[ChartAnalysis] Spark LLM error:', error);
      const host = window.location.host;
      const tips = [
        'Make sure you are logged into GitHub in this browser.',
        'If using Codespaces, ensure the frontend port is Public in the Ports tab.',
        'On mobile browsers, allow cookies/site data for app.github.dev and github.com.',
      ];
      setAnalysis(
        `Failed to generate analysis via Spark.
        
Environment: ${host}
Tips:
- ${tips.join('\n- ')}`
      );
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
