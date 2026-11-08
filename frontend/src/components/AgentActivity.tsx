import {
  Circle,
  CircleAlert,
  CircleCheck,
  CircleMinus,
  LoaderCircle,
} from 'lucide-react'

export type AgentActivityStatus = 'waiting' | 'running' | 'completed' | 'skipped' | 'error'

export type SectionWorkerActivity = {
  workerId: number
  taskId: string
  status: AgentActivityStatus
}

export type AgentActivityData = {
  router: AgentActivityStatus
  researcher: AgentActivityStatus
  planner: AgentActivityStatus
  sectionWorkers: SectionWorkerActivity[]
  reducer: AgentActivityStatus
  blogEditor: AgentActivityStatus
  imagePipeline: AgentActivityStatus
}

type AgentActivityProps = {
  activity: AgentActivityData
}

const statusLabels: Record<AgentActivityStatus, string> = {
  waiting: 'Waiting',
  running: 'Running',
  completed: 'Completed',
  skipped: 'Skipped',
  error: 'Error',
}

function getSectionWorkerStatus(workers: SectionWorkerActivity[]): AgentActivityStatus {
  if (workers.length === 0) return 'waiting'
  if (workers.some((worker) => worker.status === 'error')) return 'error'
  if (workers.some((worker) => worker.status === 'running')) return 'running'
  if (workers.some((worker) => worker.status === 'waiting')) return 'waiting'
  if (workers.every((worker) => worker.status === 'skipped')) return 'skipped'
  return 'completed'
}

function StatusIndicator({ status }: { status: AgentActivityStatus }) {
  const Icon = {
    waiting: Circle,
    running: LoaderCircle,
    completed: CircleCheck,
    skipped: CircleMinus,
    error: CircleAlert,
  }[status]

  return (
    <span className={`agent-status agent-status-${status}`}>
      <Icon size={15} strokeWidth={1.8} aria-hidden="true" />
      <span>{statusLabels[status]}</span>
    </span>
  )
}

export function AgentActivity({ activity }: AgentActivityProps) {
  const steps: { key: keyof Omit<AgentActivityData, 'sectionWorkers'>; label: string }[] = [
    { key: 'router', label: 'Router' },
    { key: 'researcher', label: 'Researcher' },
    { key: 'planner', label: 'Planner' },
  ]

  return (
    <section className="agent-activity" aria-labelledby="agent-activity-title" aria-live="polite">
      <div className="agent-activity-heading">
        <div>
          <p className="eyebrow">WORKFLOW</p>
          <h2 id="agent-activity-title">Agent activity</h2>
        </div>
        <span className="agent-activity-caption">7 steps</span>
      </div>

      <ol className="agent-activity-list">
        {steps.map(({ key, label }) => (
          <li className="agent-activity-step" key={key}>
            <span className="agent-step-name">{label}</span>
            <StatusIndicator status={activity[key]} />
          </li>
        ))}

        <li className="agent-activity-step agent-worker-group">
          <span className="agent-step-name">Section Workers</span>
          <StatusIndicator status={getSectionWorkerStatus(activity.sectionWorkers)} />
          {activity.sectionWorkers.length > 0 ? (
            <ul className="agent-worker-list" aria-label="Individual section workers">
              {activity.sectionWorkers.map((worker) => (
                <li className="agent-worker-step" key={worker.taskId}>
                  <span>Worker {worker.workerId + 1}</span>
                  <StatusIndicator status={worker.status} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="agent-worker-empty">Individual workers will appear here when activity begins.</p>
          )}
        </li>

        <li className="agent-activity-step">
          <span className="agent-step-name">Reducer</span>
          <StatusIndicator status={activity.reducer} />
        </li>
        <li className="agent-activity-step">
          <span className="agent-step-name">Blog Editor</span>
          <StatusIndicator status={activity.blogEditor} />
        </li>
        <li className="agent-activity-step">
          <span className="agent-step-name">Image Pipeline</span>
          <StatusIndicator status={activity.imagePipeline} />
        </li>
      </ol>
      <p className="agent-activity-empty-note">Activity will update here when blog generation is available.</p>
    </section>
  )
}

export default AgentActivity
