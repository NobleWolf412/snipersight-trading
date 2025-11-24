import { useLocalStorage } from '@/hooks/useLocalStorage'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { CheckCircle, Circle, Clock } from '@phosphor-icons/react'

interface Task {
    id: string
    label: string
    completed: boolean
}

interface Phase {
    id: string
    name: string
    description: string
    tasks: Task[]
}

const initialPhases: Phase[] = [
    {
        id: 'phase1',
        name: 'Phase 1: Foundation',
        description: 'Shared models, contracts, configuration system',
        tasks: [
            { id: 'p1t1', label: 'Set up Python project structure', completed: false },
            { id: 'p1t2', label: 'Create shared models (data, smc, indicators)', completed: false },
            { id: 'p1t3', label: 'Define contracts (API boundaries)', completed: false },
            { id: 'p1t4', label: 'Build configuration system', completed: false },
            { id: 'p1t5', label: 'Create CLI skeleton', completed: false }
        ]
    },
    {
        id: 'phase2',
        name: 'Phase 2: Data Layer',
        description: 'Exchange adapters, caching, ingestion pipeline',
        tasks: [
            { id: 'p2t1', label: 'Implement Binance adapter', completed: false },
            { id: 'p2t2', label: 'Implement Bybit adapter', completed: false },
            { id: 'p2t3', label: 'Build caching system', completed: false },
            { id: 'p2t4', label: 'Create ingestion pipeline', completed: false },
            { id: 'p2t5', label: 'Add deterministic test fixtures', completed: false }
        ]
    },
    {
        id: 'phase3',
        name: 'Phase 3: Analysis Layer',
        description: 'Indicators, SMC detection, confluence scoring',
        tasks: [
            { id: 'p3t1', label: 'Build indicator computation', completed: false },
            { id: 'p3t2', label: 'Implement SMC detection (OBs, FVGs)', completed: false },
            { id: 'p3t3', label: 'Implement BOS/CHoCH detection', completed: false },
            { id: 'p3t4', label: 'Create confluence scoring engine', completed: false },
            { id: 'p3t5', label: 'Build trade planner', completed: false }
        ]
    },
    {
        id: 'phase4',
        name: 'Phase 4: Risk & Execution',
        description: 'Risk management, notifications, executor',
        tasks: [
            { id: 'p4t1', label: 'Implement risk management', completed: false },
            { id: 'p4t2', label: 'Build notification system', completed: false },
            { id: 'p4t3', label: 'Create executor layer', completed: false },
            { id: 'p4t4', label: 'Add telemetry', completed: false },
            { id: 'p4t5', label: 'Implement safeguards', completed: false }
        ]
    },
    {
        id: 'phase5',
        name: 'Phase 5: Orchestration',
        description: 'Pipeline controller, context management, hooks',
        tasks: [
            { id: 'p5t1', label: 'Build pipeline controller', completed: false },
            { id: 'p5t2', label: 'Implement context management', completed: false },
            { id: 'p5t3', label: 'Create hook system', completed: false },
            { id: 'p5t4', label: 'Build CLI', completed: false },
            { id: 'p5t5', label: 'Wire up bot loop', completed: false }
        ]
    },
    {
        id: 'phase6',
        name: 'Phase 6: Quality & Testing',
        description: 'Tests, backtest framework, verification',
        tasks: [
            { id: 'p6t1', label: 'Implement quality gates', completed: false },
            { id: 'p6t2', label: 'Build backtest framework', completed: false },
            { id: 'p6t3', label: 'Create verification checklist', completed: false },
            { id: 'p6t4', label: 'Add comprehensive test coverage', completed: false },
            { id: 'p6t5', label: 'Performance profiling', completed: false }
        ]
    }
]

export function ProgressTrackerDetailed() {
    const [phases, setPhases] = useLocalStorage<Phase[]>('snipersight-progress-detailed', initialPhases)

    const toggleTask = (phaseId: string, taskId: string) => {
        setPhases((currentPhases) => {
            const phasesToUpdate = currentPhases ?? initialPhases
            return phasesToUpdate.map(phase =>
                phase.id === phaseId
                    ? {
                        ...phase,
                        tasks: phase.tasks.map(task =>
                            task.id === taskId
                                ? { ...task, completed: !task.completed }
                                : task
                        )
                    }
                    : phase
            )
        })
    }

    const calculatePhaseProgress = (phase: Phase) => {
        const completed = phase.tasks.filter(t => t.completed).length
        return (completed / phase.tasks.length) * 100
    }

    const getPhaseStatus = (phase: Phase): 'completed' | 'in-progress' | 'pending' => {
        const progress = calculatePhaseProgress(phase)
        if (progress === 100) return 'completed'
        if (progress > 0) return 'in-progress'
        return 'pending'
    }

    const currentPhases = phases ?? initialPhases
    const overallProgress = currentPhases.reduce((acc, p) => acc + calculatePhaseProgress(p), 0) / currentPhases.length

    return (
        <div className="grid gap-6">
            <Card className="border-accent/30">
                <CardHeader>
                    <CardTitle>Implementation Progress</CardTitle>
                    <CardDescription>
                        Track your SniperSight implementation tasks (progress persists between sessions)
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div>
                            <div className="flex justify-between mb-2">
                                <span className="text-sm font-medium text-foreground">Overall Progress</span>
                                <span className="text-sm text-muted-foreground">{Math.round(overallProgress)}%</span>
                            </div>
                            <Progress value={overallProgress} className="h-3" />
                        </div>
                    </div>
                </CardContent>
            </Card>

            <div className="grid gap-4">
                {currentPhases.map((phase) => {
                    const progress = calculatePhaseProgress(phase)
                    const status = getPhaseStatus(phase)

                    return (
                        <Card key={phase.id} className="border-border/50">
                            <CardHeader>
                                <div className="flex items-start justify-between">
                                    <div className="flex items-start gap-3">
                                        {status === 'completed' ? (
                                            <CheckCircle size={24} weight="fill" className="text-success mt-1" />
                                        ) : status === 'in-progress' ? (
                                            <Clock size={24} weight="fill" className="text-warning mt-1" />
                                        ) : (
                                            <Circle size={24} className="text-muted-foreground mt-1" />
                                        )}
                                        <div>
                                            <CardTitle className="text-lg">{phase.name}</CardTitle>
                                            <CardDescription>{phase.description}</CardDescription>
                                        </div>
                                    </div>
                                    <Badge variant={
                                        status === 'completed' ? 'default' :
                                            status === 'in-progress' ? 'secondary' :
                                                'outline'
                                    }>
                                        {Math.round(progress)}%
                                    </Badge>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    <Progress value={progress} className="h-2 mb-3" />
                                    <ul className="space-y-3">
                                        {phase.tasks.map((task) => (
                                            <li key={task.id} className="flex items-start gap-3">
                                                <Checkbox
                                                    id={task.id}
                                                    checked={task.completed}
                                                    onCheckedChange={() => toggleTask(phase.id, task.id)}
                                                    className="mt-0.5"
                                                />
                                                <label
                                                    htmlFor={task.id}
                                                    className={`text-sm cursor-pointer select-none ${task.completed
                                                        ? 'text-muted-foreground line-through'
                                                        : 'text-foreground'
                                                        }`}
                                                >
                                                    {task.label}
                                                </label>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </CardContent>
                        </Card>
                    )
                })}
            </div>
        </div>
    )
}
