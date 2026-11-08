import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  ArrowDownRight,
  ArrowRight,
  BookOpenText,
  Check,
  CircleCheck,
  FileImage,
  FileText,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Plus,
  Settings2,
  Sparkles,
  X,
} from 'lucide-react'
import './App.css'
import { API_BASE_URL } from './config'
import AgentActivity, {
  type AgentActivityData,
  type AgentActivityStatus,
  type SectionWorkerActivity,
} from './components/AgentActivity'
import { generateBlogStream, type BlogStreamEvent } from './api/generateBlogStream'
import { fetchBlogs, fetchBlogDetail, type BlogSummary } from './api/blogs'
import { MarkdownViewer } from './components/MarkdownViewer'
import { BlogLibrary } from './components/BlogLibrary'
import { ImageLibrary } from './components/ImageLibrary'

type Destination = 'Dashboard' | 'Create Blog' | 'Blog Library' | 'Image Library' | 'Settings'

const initialAgentActivity: AgentActivityData = {
  router: 'waiting',
  researcher: 'waiting',
  planner: 'waiting',
  sectionWorkers: [],
  reducer: 'waiting',
  blogEditor: 'waiting',
  imagePipeline: 'waiting',
}

type SavedBlogInfo = { title: string | null; path: string | null }
type GenerationRunState = {
  activity: AgentActivityData
  generating: boolean
  streamStarted: boolean
  generationError: string | null
  savedFile: SavedBlogInfo | null
}

const initialGenerationRun: GenerationRunState = {
  activity: initialAgentActivity,
  generating: false,
  streamStarted: false,
  generationError: null,
  savedFile: null,
}

const activityFieldByNode = {
  router: 'router',
  researcher: 'researcher',
  planner: 'planner',
  reducer: 'reducer',
  blog_editor: 'blogEditor',
  image_pipeline: 'imagePipeline',
} as const

function applyActivityEvent(activity: AgentActivityData, event: BlogStreamEvent): AgentActivityData {
  if (!['running', 'completed', 'skipped', 'error'].includes(event.name)) return activity

  const status = event.name as AgentActivityStatus
  const node = event.data.node

  if (node === 'section_worker') {
    const workerId = event.data.worker_id
    const taskId = event.data.task_id
    if (typeof workerId !== 'number' || typeof taskId !== 'string') return activity

    const worker: SectionWorkerActivity = { workerId, taskId, status }
    const existing = activity.sectionWorkers.findIndex((item) => item.taskId === taskId)
    const sectionWorkers = [...activity.sectionWorkers]
    if (existing >= 0) sectionWorkers[existing] = worker
    else sectionWorkers.push(worker)
    sectionWorkers.sort((left, right) => left.workerId - right.workerId)
    return { ...activity, sectionWorkers }
  }

  if (typeof node !== 'string' || !Object.prototype.hasOwnProperty.call(activityFieldByNode, node)) return activity
  const field = activityFieldByNode[node as keyof typeof activityFieldByNode]
  return { ...activity, [field]: status }
}

function settleFailedActivity(
  activity: AgentActivityData,
  failureEvent?: BlogStreamEvent,
): AgentActivityData {
  let next = activity

  if (failureEvent?.name === 'error') {
    const node = failureEvent.data.node
    if (node === 'section_worker') {
      const taskId = failureEvent.data.task_id
      const worker = activity.sectionWorkers.find((item) => item.taskId === taskId)
      if (worker?.status === 'running') next = applyActivityEvent(activity, failureEvent)
    } else if (typeof node === 'string' && Object.prototype.hasOwnProperty.call(activityFieldByNode, node)) {
      const field = activityFieldByNode[node as keyof typeof activityFieldByNode]
      if (activity[field] === 'running') next = applyActivityEvent(activity, failureEvent)
    }
  }

  const settle = (status: AgentActivityStatus): AgentActivityStatus => {
    if (status === 'running') return 'error'
    if (status === 'waiting') return 'skipped'
    return status
  }

  return {
    router: settle(next.router),
    researcher: settle(next.researcher),
    planner: settle(next.planner),
    sectionWorkers: next.sectionWorkers.map((worker) => ({
      ...worker,
      status: settle(worker.status),
    })),
    reducer: settle(next.reducer),
    blogEditor: settle(next.blogEditor),
    imagePipeline: settle(next.imagePipeline),
  }
}

const destinations: { name: Destination; icon: typeof LayoutDashboard }[] = [
  { name: 'Dashboard', icon: LayoutDashboard },
  { name: 'Create Blog', icon: Plus },
  { name: 'Blog Library', icon: BookOpenText },
  { name: 'Image Library', icon: FileImage },
  { name: 'Settings', icon: Settings2 },
]

function Brand() {
  return (
    <div className="brand-lockup">
      <div className="brand-mark"><span /><span /><span /></div>
      <span className="brand-name">draft<span>well</span></span>
      <span className="brand-edition">STUDIO</span>
    </div>
  )
}

function Sidebar({ active, onNavigate, open, onClose }: {
  active: Destination
  onNavigate: (page: Destination) => void
  open: boolean
  onClose: () => void
}) {
  return (
    <>
      {open && <button className="sidebar-scrim" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="sidebar-top">
          <Brand />
          <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={onClose}><X size={19} /></button>
        </div>
        <div className="local-instance-card">
          <span className="local-instance-dot" aria-hidden="true" />
          <div className="instance-copy"><strong>Local instance</strong><span>Your writing workspace</span></div>
        </div>
        <p className="nav-label">YOUR STUDIO</p>
        <nav className="primary-nav" aria-label="Main navigation">
          {destinations.map(({ name, icon: Icon }) => (
            <button key={name} className={`nav-item ${active === name ? 'nav-item-active' : ''}`} onClick={() => { onNavigate(name); onClose() }}>
              <Icon size={18} strokeWidth={1.8} /><span>{name}</span>
              {name === 'Create Blog' && <span className="nav-plus">+</span>}
            </button>
          ))}
        </nav>
      </aside>
    </>
  )
}

type BackendStatus = 'checking' | 'online' | 'offline'

function BackendStatusIndicator({ status }: { status: BackendStatus }) {
  const label = status === 'checking' ? 'Checking' : status === 'online' ? 'Backend online' : 'Backend offline'
  return <div className={`backend-status backend-status-${status}`} role="status" aria-live="polite"><span className="backend-status-dot" /><span>{label}</span></div>
}

function PageHeader({ onMenu, active, backendStatus }: { onMenu: () => void; active: Destination; backendStatus: BackendStatus }) {
  return (
    <header className="topbar">
      <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={onMenu}><Menu size={20} /></button>
      <div className="breadcrumb"><span>Studio</span><span className="crumb-divider">/</span><strong>{active}</strong></div>
      <div className="topbar-actions"><BackendStatusIndicator status={backendStatus} /></div>
    </header>
  )
}

function SectionHeading({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) {
  return <div className="section-heading"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2>{title}</h2></div>{action}</div>
}

function StatCard({ label, value, note, icon: Icon, tone }: { label: string; value: string; note: string; icon: typeof FileText; tone: string }) {
  return <article className="stat-card"><div className="stat-top"><span>{label}</span><span className={`stat-icon ${tone}`}><Icon size={17} /></span></div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></article>
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="empty-state">
      <div className="paper-illustration" aria-hidden="true"><div className="paper-back" /><div className="paper-front"><span className="paper-kicker">YOUR NEXT STORY</span><span className="paper-line line-long" /><span className="paper-line line-mid" /><span className="paper-line line-short" /><div className="paper-spark"><Sparkles size={19} /></div></div><div className="paper-shadow" /></div>
      <p className="eyebrow">A BLANK PAGE, FULL OF POSSIBILITY</p>
      <h3>Your first story starts here.</h3>
      <p className="empty-description">Turn a good idea into a thoughtful, polished blog post.<br className="desktop-break" /> Your writing desk is ready when you are.</p>
      <button className="button button-secondary empty-cta" onClick={onCreate}><Plus size={16} /> Create your first blog</button>
    </div>
  )
}

function Dashboard({ onCreate, onNavigate, onReadBlog }: {
  onCreate: () => void
  onNavigate: (page: Destination) => void
  onReadBlog: (filename: string, title: string) => void
}) {
  const [blogs, setBlogs] = useState<BlogSummary[]>([])

  useEffect(() => {
    fetchBlogs().then(setBlogs)
  }, [])

  const totalWords = blogs.reduce((acc, b) => acc + Math.round(b.size / 6.5), 0)
  const recentBlogs = blogs.slice(0, 3)

  return (
    <div className="dashboard-page">
      <section className="welcome-row">
        <div>
          <p className="eyebrow"><span className="status-dot" /> YOUR WRITING DESK</p>
          <h1>Good afternoon,<br /><span>Nishank.</span></h1>
          <p className="welcome-copy">A clear mind and a fresh page. What would you like to write today?</p>
        </div>
        <button className="button button-primary hero-cta" onClick={onCreate}>
          <span className="cta-icon"><Plus size={19} /></span>Create new blog
          <ArrowRight size={16} className="cta-arrow" />
        </button>
      </section>

      <section className="overview-section">
        <SectionHeading
          eyebrow="YOUR ACTIVITY"
          title="A little overview"
          action={
            <button className="text-link" onClick={() => onNavigate('Blog Library')}>
              View library <ArrowRight size={14} />
            </button>
          }
        />
        <div className="stats-grid">
          <StatCard
            label="Your blogs"
            value={String(blogs.length)}
            note="Saved permanently on your local disk"
            icon={FileText}
            tone="tone-orange"
          />
          <StatCard
            label="Words written"
            value={totalWords > 0 ? `~${totalWords.toLocaleString()}` : '0'}
            note="Across all generated stories"
            icon={BookOpenText}
            tone="tone-lilac"
          />
          <StatCard
            label="Storage"
            value="Local"
            note="Stored in output/blogs/"
            icon={ArrowDownRight}
            tone="tone-green"
          />
        </div>
      </section>

      <section className="recent-section">
        <SectionHeading
          eyebrow="THE LATEST FROM YOU"
          title="Recently written"
          action={
            <button
              className="icon-button section-more"
              aria-label="Open blog library"
              onClick={() => onNavigate('Blog Library')}
            >
              <ArrowRight size={17} />
            </button>
          }
        />
        <div className="recent-panel">
          {recentBlogs.length === 0 ? (
            <EmptyState onCreate={onCreate} />
          ) : (
            <div className="recent-blogs-list">
              {recentBlogs.map((b) => (
                <div
                  key={b.filename}
                  className="recent-blog-row"
                  onClick={() => onReadBlog(b.filename, b.title)}
                >
                  <div className="recent-blog-info">
                    <h4 className="recent-blog-title">{b.title}</h4>
                    <div className="recent-blog-meta">
                      {b.topic && <span>{b.topic}</span>}
                      {b.date && <span>• {b.date}</span>}
                      <span>• ~{Math.round(b.size / 6.5)} words</span>
                    </div>
                  </div>
                  <button
                    className="button button-secondary recent-blog-btn"
                    onClick={(e) => {
                      e.stopPropagation()
                      onReadBlog(b.filename, b.title)
                    }}
                  >
                    Read story →
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function CreateBlogPage({ run, onGenerate, onReadBlog, onNavigate }: {
  run: GenerationRunState
  onGenerate: (topic: string) => void
  onReadBlog: (filename: string, title: string) => void
  onNavigate: (page: Destination) => void
}) {
  const [topic, setTopic] = useState('')

  return (
    <div className="subpage create-blog-page">
      <p className="eyebrow"><span className="status-dot" /> START WITH AN IDEA</p>
      <section className="subpage-card create-blog-card">
        <div className="subpage-icon"><Plus size={21} /></div>
        <h1>Create a new blog</h1>
        <p className="create-blog-intro">A good story begins with a good question. Start with the idea on your mind.</p>
        <div className="topic-field">
          <label htmlFor="blog-topic">What would you like to write about?</label>
          <textarea
            id="blog-topic"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            placeholder="Enter your blog topic..."
            required
            rows={5}
            disabled={run.generating}
          />
          <div className="topic-field-meta" aria-live="polite">
            <span>Give your idea a little room to breathe.</span>
            <span>{topic.length} characters</span>
          </div>
        </div>
        <div className="generate-action">
          <button
            className={`button button-primary generate-button ${run.generating ? 'generate-button-loading' : ''}`}
            type="button"
            onClick={() => onGenerate(topic)}
            disabled={!topic.trim() || run.generating}
          >
            {run.generating ? <LoaderCircle size={16} className="generate-spinner" /> : <Sparkles size={16} />}
            {run.generating ? 'Generating blog…' : 'Generate Blog'}
            {!run.generating && <ArrowRight size={15} />}
          </button>
          {run.generating && <span className="generation-connection-status">{run.streamStarted ? 'Agent activity is updating' : 'Connecting to your local backend…'}</span>}
        </div>
        {run.generationError && <p className="generation-error" role="alert">{run.generationError}</p>}
        {run.savedFile && (
          <div className="generation-result" role="status" aria-live="polite">
            <CircleCheck size={18} aria-hidden="true" />
            <div className="generation-result-content">
              <strong>{run.savedFile.title ?? 'Blog saved successfully'}</strong>
              {run.savedFile.path && <span>Saved to disk at <code>{run.savedFile.path}</code></span>}
              <div className="generation-result-actions">
                <button
                  type="button"
                  className="button button-primary read-generated-btn"
                  onClick={() => onReadBlog(run.savedFile?.path ? run.savedFile.path.split(/[/\\]/).pop() || '' : '', run.savedFile?.title || '')}
                >
                  <BookOpenText size={15} /> Read Blog Now
                </button>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => onNavigate('Blog Library')}
                >
                  View in Library →
                </button>
              </div>
            </div>
          </div>
        )}
        <AgentActivity activity={run.activity} />
      </section>
    </div>
  )
}

function DestinationPage({ active }: { active: 'Settings' }) {
  const details = {
    Settings: {
      kicker: 'MAKE IT YOURS',
      title: 'Settings',
      description: 'Your studio runs locally on your machine with Gemini Free Tier and Wikimedia Commons.',
      icon: Settings2,
    },
  }
  const detail = details[active]
  const Icon = detail.icon
  return (
    <div className="subpage">
      <p className="eyebrow"><span className="status-dot" /> {detail.kicker}</p>
      <div className="subpage-card">
        <div className="subpage-icon"><Icon size={21} /></div>
        <h1>{detail.title}</h1>
        <p>{detail.description}</p>
        <div className="coming-soon">
          <span className="coming-dot" />
          <Check size={13} /> LOCAL WORKSPACE CONNECTED
        </div>
      </div>
    </div>
  )
}

function App() {
  const [active, setActive] = useState<Destination>('Dashboard')
  const [menuOpen, setMenuOpen] = useState(false)
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking')
  const [generationRun, setGenerationRun] = useState<GenerationRunState>(initialGenerationRun)
  const [activeArticle, setActiveArticle] = useState<{ content: string; title?: string; filename?: string } | null>(null)
  const activeStream = useRef<AbortController | null>(null)

  useEffect(() => () => activeStream.current?.abort(), [])

  const handleReadBlog = async (filename: string, title?: string) => {
    const cleanFilename = filename.split(/[/\\]/).pop() || filename
    if (!cleanFilename) return
    const content = await fetchBlogDetail(cleanFilename)
    if (content) {
      setActiveArticle({ content, title, filename: cleanFilename })
    }
  }

  const handleGenerate = async (topic: string) => {
    const trimmedTopic = topic.trim()
    if (!trimmedTopic || activeStream.current) return

    const controller = new AbortController()
    activeStream.current = controller
    setGenerationRun({
      ...initialGenerationRun,
      activity: { ...initialAgentActivity, sectionWorkers: [] },
      generating: true,
    })

    let completed = false
    let receivedError = false
    try {
      for await (const event of generateBlogStream(trimmedTopic, controller.signal)) {
        if (controller.signal.aborted) break

        if (event.name === 'complete') {
          if (completed) continue
          completed = true
          setGenerationRun((current) => ({
            ...current,
            savedFile: {
              title: typeof event.data.title === 'string' ? event.data.title : null,
              path: typeof event.data.saved_file_path === 'string' ? event.data.saved_file_path : null,
            },
          }))
          continue
        }

        if (event.name === 'error') {
          receivedError = true
          setGenerationRun((current) => {
            const isWorkerOutcome = event.data.node === 'section_worker' && typeof event.data.worker_id === 'number'
            const workerNumbers = Array.isArray(event.data.worker_numbers)
              ? event.data.worker_numbers.filter((value): value is number => Number.isInteger(value) && value >= 1 && value <= 3)
              : []
            const workerFailureMessage = workerNumbers.length > 0
              ? `${workerNumbers.map((number) => `Section Worker ${number}`).join(', ')} failed. Other workers finished; downstream steps were stopped.`
              : null
            return {
              ...current,
              streamStarted: true,
              activity: isWorkerOutcome
                ? applyActivityEvent(current.activity, event)
                : settleFailedActivity(current.activity, event),
              generationError: workerFailureMessage ?? (typeof event.data.message === 'string'
                ? event.data.message
                : 'Blog generation failed. Please try again.'),
            }
          })
          continue
        }

        setGenerationRun((current) => ({
          ...current,
          streamStarted: true,
          activity: applyActivityEvent(current.activity, event),
        }))
      }

      if (!completed && !receivedError && !controller.signal.aborted) {
        setGenerationRun((current) => ({
          ...current,
          activity: settleFailedActivity(current.activity),
          generationError: 'The activity stream ended before generation finished. Please try again.',
        }))
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        const message = error instanceof Error ? error.message : ''
        const safeMessages = [
          'Could not connect to the local backend. Check that it is running and try again.',
          'The backend could not start generation. Please try again.',
          'The backend sent an unreadable activity update.',
        ]
        setGenerationRun((current) => ({
          ...current,
          activity: settleFailedActivity(current.activity),
          generationError: safeMessages.includes(message)
            ? message
            : 'The generation stream was interrupted. Check the backend and try again.',
          generating: false,
        }))
        controller.abort()
      }
    } finally {
      if (activeStream.current === controller) activeStream.current = null
      if (!controller.signal.aborted) setGenerationRun((current) => ({ ...current, generating: false }))
    }
  }

  useEffect(() => {
    const controller = new AbortController()

    fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) return false
        const health = await response.json() as { status?: string }
        return health.status === 'ok'
      })
      .then((isOnline) => setBackendStatus(isOnline ? 'online' : 'offline'))
      .catch(() => {
        if (!controller.signal.aborted) setBackendStatus('offline')
      })

    return () => controller.abort()
  }, [])

  const navigate = (page: Destination) => setActive(page)

  return (
    <div className="app-shell">
      <Sidebar active={active} onNavigate={navigate} open={menuOpen} onClose={() => setMenuOpen(false)} />
      <main className="main-column">
        <PageHeader onMenu={() => setMenuOpen(true)} active={active} backendStatus={backendStatus} />
        {active === 'Dashboard' ? (
          <Dashboard
            onCreate={() => navigate('Create Blog')}
            onNavigate={navigate}
            onReadBlog={handleReadBlog}
          />
        ) : active === 'Create Blog' ? (
          <CreateBlogPage
            run={generationRun}
            onGenerate={handleGenerate}
            onReadBlog={handleReadBlog}
            onNavigate={navigate}
          />
        ) : active === 'Blog Library' ? (
          <BlogLibrary
            onSelectBlog={handleReadBlog}
            onCreateNew={() => navigate('Create Blog')}
          />
        ) : active === 'Image Library' ? (
          <ImageLibrary />
        ) : (
          <DestinationPage active="Settings" />
        )}
      </main>

      {activeArticle && (
        <MarkdownViewer
          content={activeArticle.content}
          title={activeArticle.title}
          filename={activeArticle.filename}
          onClose={() => setActiveArticle(null)}
        />
      )}
    </div>
  )
}

export default App
