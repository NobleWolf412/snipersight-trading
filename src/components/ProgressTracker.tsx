import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { CheckCircle, Circle, Clock } from '@phosphor-icons/react'
import { useKV } from '@github/spark/hooks'

export interface Phase {
  id: string
  name: string
  description: string
  modules: string[]
  status: 'completed' | 'in-progress' | 'pending'
}

const defaultPhases: Phase[] = [
  {
    id: 'phase-1',
    name: 'Phase 1: Foundation',
    description: 'Core data structures, contracts, and configuration system',
    modules: [
      'shared/models/',
      'contracts/',
      'shared/config/'
    ],
    status: 'pending'
  },
  {
    id: 'phase-2',
    name: 'Phase 2: Data Layer',
    description: 'Exchange adapters, caching, and ingestion pipeline',
    modules: [
      'data/adapters/',
      'data/cache.py',
      'data/ingestion_pipeline.py',
      'tests/fixtures/'
    ],
    status: 'pending'
  },
  {
    id: 'phase-3',
    name: 'Phase 3: Analysis Layer',
    description: 'Indicator computation, SMC detection, confluence scoring, and trade planning',
    modules: [
      'indicators/',
      'strategy/smc/',
      'strategy/confluence/',
      'strategy/planner/'
    ],
    status: 'pending'
  },
  {
    id: 'phase-4',
    name: 'Phase 4: Risk & Execution',
    description: 'Risk management, notification system, and execution layer',
    modules: [
      'risk/',
      'bot/notifications/',
      'bot/executor/',
      'bot/telemetry/'
    ],
    status: 'pending'
  },
  {
    id: 'phase-5',
    name: 'Phase 5: Orchestration',
    description: 'Pipeline controller, context management, hooks, and CLI',
    modules: [
      'engine/pipeline.py',
      'engine/context.py',
      'engine/hooks.py',
      'sniper_sight_cli.py'
    ],
    status: 'pending'
  },
  {
    id: 'phase-6',
    name: 'Phase 6: Quality & Testing',
    description: 'Quality gates, backtest framework, verification checklist, and comprehensive testing',
    modules: [
      'tests/unit/',
      'tests/integration/',
      'tests/backtest/',
      'scripts/run_quality_audit.py'
    ],
    status: 'pending'
  }
]

export function ProgressTracker() {
  const [phases, setPhases] = useKV<Phase[]>('snipersight-phases', defaultPhases)

  const phasesList = phases || defaultPhases
  const completedCount = phasesList.filter(p => p.status === 'completed').length
  const inProgressCount = phasesList.filter(p => p.status === 'in-progress').length
  const totalCount = phasesList.length
  const progressPercentage = (completedCount / totalCount) * 100

  const togglePhaseStatus = (phaseId: string) => {
    setPhases(currentPhases => {
      const current = currentPhases || defaultPhases
      return current.map(phase => {
        if (phase.id === phaseId) {
          const nextStatus =
            phase.status === 'pending'
              ? 'in-progress'
              : phase.status === 'in-progress'
              ? 'completed'
              : 'pending'
          return { ...phase, status: nextStatus }
        }
        return phase
      })
    })
  }

  const getStatusIcon = (status: Phase['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={20} weight="fill" className="text-success" />
      case 'in-progress':
        return <Clock size={20} weight="fill" className="text-warning" />
      case 'pending':
        return <Circle size={20} className="text-muted-foreground" />
    }
  }

  const getStatusBadge = (status: Phase['status']) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-success/10 text-success border-success/30">Completed</Badge>
      case 'in-progress':
        return <Badge className="bg-warning/10 text-warning border-warning/30">In Progress</Badge>
      case 'pending':
        return <Badge variant="outline" className="text-muted-foreground">Pending</Badge>
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-accent/30">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Implementation Progress</CardTitle>
              <CardDescription>Track completed and pending implementation phases</CardDescription>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-foreground monospace">
                {completedCount}/{totalCount}
              </div>
              <div className="text-sm text-muted-foreground">Phases Complete</div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Overall Progress</span>
                <span className="font-semibold text-foreground monospace">{progressPercentage.toFixed(0)}%</span>
              </div>
              <Progress value={progressPercentage} className="h-2" />
            </div>

            <div className="grid grid-cols-3 gap-4 pt-2">
              <div className="space-y-1">
                <div className="text-2xl font-bold text-success monospace">{completedCount}</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wide">Completed</div>
              </div>
              <div className="space-y-1">
                <div className="text-2xl font-bold text-warning monospace">{inProgressCount}</div>
                <div className="text-xs text-muted-foreground uppercase tracking-wide">In Progress</div>
              </div>
              <div className="space-y-1">
                <div className="text-2xl font-bold text-muted-foreground monospace">
                  {totalCount - completedCount - inProgressCount}
                </div>
                <div className="text-xs text-muted-foreground uppercase tracking-wide">Pending</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {phasesList.map((phase) => (
          <Card
            key={phase.id}
            className={`transition-all cursor-pointer hover:border-accent/50 ${
              phase.status === 'completed'
                ? 'border-success/30 bg-success/5'
                : phase.status === 'in-progress'
                ? 'border-warning/30 bg-warning/5'
                : 'border-border'
            }`}
            onClick={() => togglePhaseStatus(phase.id)}
          >
            <CardContent className="pt-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 mt-1">{getStatusIcon(phase.status)}</div>
                <div className="flex-1 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <h3 className="font-semibold text-foreground monospace">{phase.name}</h3>
                      <p className="text-sm text-muted-foreground">{phase.description}</p>
                    </div>
                    {getStatusBadge(phase.status)}
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Key Modules</div>
                    <div className="flex flex-wrap gap-2">
                      {phase.modules.map((module) => (
                        <code
                          key={module}
                          className="text-xs bg-muted px-2 py-1 rounded text-accent monospace"
                        >
                          {module}
                        </code>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-muted bg-muted/10">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <div className="text-muted-foreground">💡</div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Click any phase to update its status</p>
              <p className="text-xs text-muted-foreground">
                Progress cycles through: Pending → In Progress → Completed → Pending
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
