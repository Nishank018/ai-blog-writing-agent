import { useState, useEffect } from 'react'
import { BookOpenText, Calendar, Clock, FileText, Plus, RefreshCw, Search } from 'lucide-react'
import { fetchBlogs, type BlogSummary } from '../api/blogs'

type BlogLibraryProps = {
  onSelectBlog: (filename: string, title: string) => void
  onCreateNew: () => void
}

export function BlogLibrary({ onSelectBlog, onCreateNew }: BlogLibraryProps) {
  const [blogs, setBlogs] = useState<BlogSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const loadBlogs = async () => {
    setLoading(true)
    const list = await fetchBlogs()
    setBlogs(list)
    setLoading(false)
  }

  useEffect(() => {
    loadBlogs()
  }, [])

  const filtered = blogs.filter((b) => {
    const q = search.toLowerCase()
    return (b.title || '').toLowerCase().includes(q) || (b.topic || '').toLowerCase().includes(q)
  })

  return (
    <div className="subpage blog-library-page">
      <div className="library-top-bar">
        <div>
          <p className="eyebrow"><span className="status-dot" /> YOUR PERMANENT ARCHIVE</p>
          <h1>Blog Library</h1>
          <p className="library-subtitle">
            All your generated blogs saved locally on your machine ({blogs.length} {blogs.length === 1 ? 'story' : 'stories'}).
          </p>
        </div>
        <div className="library-actions">
          <button className="button button-ghost" onClick={loadBlogs} title="Refresh library">
            <RefreshCw size={15} className={loading ? 'generate-spinner' : ''} /> Refresh
          </button>
          <button className="button button-primary" onClick={onCreateNew}>
            <Plus size={16} /> New Blog
          </button>
        </div>
      </div>

      <div className="library-search-box">
        <Search size={17} className="search-icon" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by title, topic, or keyword..."
          className="search-input"
        />
        {search && (
          <button className="clear-search" onClick={() => setSearch('')}>
            Clear
          </button>
        )}
      </div>

      {loading ? (
        <div className="library-loading">
          <span className="local-instance-dot" /> Loading your local blogs...
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="subpage-icon"><BookOpenText size={24} /></div>
          <h3>{search ? 'No matching blogs found' : 'No blogs in your library yet'}</h3>
          <p className="empty-description">
            {search ? 'Try a different search keyword.' : 'Generate your first blog to start building your personal library.'}
          </p>
          {!search && (
            <button className="button button-primary empty-cta" onClick={onCreateNew}>
              <Plus size={16} /> Create your first blog
            </button>
          )}
        </div>
      ) : (
        <div className="blogs-grid">
          {filtered.map((b) => {
            const approxWords = Math.round(b.size / 6.5)
            const approxMins = Math.max(1, Math.ceil(approxWords / 220))

            return (
              <article
                key={b.filename}
                className="blog-card"
                onClick={() => onSelectBlog(b.filename, b.title)}
                tabIndex={0}
                role="button"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onSelectBlog(b.filename, b.title)
                  }
                }}
              >
                {b.topic && <span className="blog-card-topic">{b.topic}</span>}
                <h3 className="blog-card-title">{b.title}</h3>
                <div className="blog-card-meta">
                  {b.date && (
                    <span className="blog-meta-item">
                      <Calendar size={13} /> {b.date}
                    </span>
                  )}
                  <span className="blog-meta-item">
                    <Clock size={13} /> {approxMins} min read
                  </span>
                  <span className="blog-meta-item">
                    <FileText size={13} /> ~{approxWords} words
                  </span>
                </div>
                <div className="blog-card-footer">
                  <span className="read-action">Read story →</span>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default BlogLibrary
