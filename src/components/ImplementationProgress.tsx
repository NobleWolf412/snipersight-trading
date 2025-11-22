import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { CheckCircle, Circle, Clock, FileText, Code, TestTube } from '@phosphor-icons/react';

interface PhaseStatus {
  phase: number;
  name: string;
  status: 'complete' | 'in-progress' | 'pending';
  progress: number;
  files: number;
  description: string;
  modules: {
    name: string;
    status: 'complete' | 'in-progress' | 'pending';
  }[];
}

const phaseData: PhaseStatus[] = [
  {
    phase: 1,
    name: 'Foundation',
    status: 'complete',
    progress: 100,
    files: 18,
    description: 'Shared models, contracts, configuration system',
    modules: [
      { name: 'Data Models', status: 'complete' },
      { name: 'SMC Models', status: 'complete' },
      { name: 'Trading Models', status: 'complete' },
      { name: 'Configuration', status: 'complete' },
      { name: 'Contracts', status: 'complete' },
    ],
  },
  {
    phase: 2,
    name: 'Data Layer',
    status: 'complete',
    progress: 100,
    files: 12,
    description: 'Multi-exchange adapters, caching, ingestion pipeline',
    modules: [
      { name: 'Binance Adapter', status: 'complete' },
      { name: 'Bybit Adapter', status: 'complete' },
      { name: 'Caching System', status: 'complete' },
      { name: 'Ingestion Pipeline', status: 'complete' },
      { name: 'Mock Data Generators', status: 'complete' },
    ],
  },
  {
    phase: 3,
    name: 'Analysis Layer',
    status: 'complete',
    progress: 100,
    files: 13,
    description: 'Indicators, SMC detection, confluence scoring, trade planning',
    modules: [
      { name: 'Momentum Indicators', status: 'complete' },
      { name: 'Volatility Indicators', status: 'complete' },
      { name: 'Volume Indicators', status: 'complete' },
      { name: 'Order Blocks', status: 'complete' },
      { name: 'Fair Value Gaps', status: 'complete' },
      { name: 'BOS/CHoCH', status: 'complete' },
      { name: 'Liquidity Sweeps', status: 'complete' },
      { name: 'Confluence Scorer', status: 'complete' },
      { name: 'Trade Planner', status: 'complete' },
      { name: 'TA-Lib Validation', status: 'complete' },
    ],
  },
  {
    phase: 4,
    name: 'Risk & Bot',
    status: 'in-progress',
    progress: 0,
    files: 15,
    description: 'Position sizing, risk management, Telegram notifications, execution',
    modules: [
      { name: 'Position Sizing', status: 'pending' },
      { name: 'Exposure Limits', status: 'pending' },
      { name: 'Compliance Checks', status: 'pending' },
      { name: 'Audit Logging', status: 'pending' },
      { name: 'Telegram Notifier', status: 'pending' },
      { name: 'Message Formatters', status: 'pending' },
      { name: 'Trade Executor', status: 'pending' },
      { name: 'Safeguards', status: 'pending' },
      { name: 'Telemetry', status: 'pending' },
    ],
  },
  {
    phase: 5,
    name: 'Orchestration',
    status: 'pending',
    progress: 0,
    files: 8,
    description: 'Pipeline controller, context management, hook system',
    modules: [
      { name: 'Pipeline Controller', status: 'pending' },
      { name: 'Context Manager', status: 'pending' },
      { name: 'Hook System', status: 'pending' },
      { name: 'CLI Commands', status: 'pending' },
    ],
  },
  {
    phase: 6,
    name: 'Testing',
    status: 'pending',
    progress: 0,
    files: 20,
    description: 'Unit tests, integration tests, backtest framework',
    modules: [
      { name: 'Unit Tests', status: 'pending' },
      { name: 'Integration Tests', status: 'pending' },
      { name: 'Backtest Framework', status: 'pending' },
      { name: 'Verification Checklist', status: 'pending' },
    ],
  },
];

export function ImplementationProgress() {
  const totalPhases = phaseData.length;
  const completedPhases = phaseData.filter((p) => p.status === 'complete').length;
  const overallProgress = (completedPhases / totalPhases) * 100;

  const getStatusIcon = (status: PhaseStatus['status']) => {
    switch (status) {
      case 'complete':
        return <CheckCircle className="text-success" weight="fill" />;
      case 'in-progress':
        return <Clock className="text-accent" weight="fill" />;
      default:
        return <Circle className="text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: PhaseStatus['status']) => {
    switch (status) {
      case 'complete':
        return (
          <Badge className="bg-success/20 text-success border-success/30">
            Complete
          </Badge>
        );
      case 'in-progress':
        return (
          <Badge className="bg-accent/20 text-accent border-accent/30">
            In Progress
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-muted-foreground">
            Pending
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-8">
      <Card className="border-accent/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <Code className="text-accent" size={32} />
            SniperSight Backend Implementation
          </CardTitle>
          <CardDescription>
            Python backend development progress tracker
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Overall Progress</span>
              <span className="text-sm text-muted-foreground">
                {completedPhases} / {totalPhases} Phases Complete
              </span>
            </div>
            <Progress value={overallProgress} className="h-3" />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6">
        {phaseData.map((phase) => (
          <Card
            key={phase.phase}
            className={
              phase.status === 'in-progress'
                ? 'border-accent/50 bg-accent/5'
                : phase.status === 'complete'
                ? 'border-success/30'
                : 'border-border'
            }
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  {getStatusIcon(phase.status)}
                  <div>
                    <CardTitle className="text-xl">
                      Phase {phase.phase}: {phase.name}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {phase.description}
                    </CardDescription>
                  </div>
                </div>
                {getStatusBadge(phase.status)}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <FileText className="text-muted-foreground" size={16} />
                  <span>{phase.files} files</span>
                </div>
                {phase.status === 'in-progress' && (
                  <div className="flex items-center gap-2">
                    <TestTube className="text-accent" size={16} />
                    <span className="text-accent">Active development</span>
                  </div>
                )}
              </div>

              {phase.progress > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-muted-foreground">
                      Module Progress
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {phase.progress}%
                    </span>
                  </div>
                  <Progress value={phase.progress} className="h-2" />
                </div>
              )}

              <Separator />

              <div className="space-y-2">
                <div className="text-sm font-medium text-muted-foreground">
                  Modules
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {phase.modules.map((module) => (
                    <div
                      key={module.name}
                      className="flex items-center gap-2 text-sm"
                    >
                      {module.status === 'complete' ? (
                        <CheckCircle
                          className="text-success flex-shrink-0"
                          size={16}
                          weight="fill"
                        />
                      ) : module.status === 'in-progress' ? (
                        <Clock
                          className="text-accent flex-shrink-0"
                          size={16}
                          weight="fill"
                        />
                      ) : (
                        <Circle
                          className="text-muted-foreground flex-shrink-0"
                          size={16}
                        />
                      )}
                      <span
                        className={
                          module.status === 'complete'
                            ? 'text-foreground'
                            : 'text-muted-foreground'
                        }
                      >
                        {module.name}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
