import { useState, type ReactNode } from 'react'
import { Check, Copy, Download, X, Clock, FileText, ArrowLeft } from 'lucide-react'
import { API_BASE_URL } from '../config'

type MarkdownViewerProps = {
  content: string
  title?: string | null
  filename?: string | null
  onClose?: () => void
}

export function MarkdownViewer({ content, title, filename, onClose }: MarkdownViewerProps) {
  const [copied, setCopied] = useState(false)

  // Strip frontmatter for reading body and extract metadata if available
  let body = content
  let metaTopic = ''
  let metaDate = ''

  if (content.startsWith('---')) {
    const parts = content.split('---')
    if (parts.length >= 3) {
      const frontmatter = parts[1]
      body = parts.slice(2).join('---').trim()
      for (const line of frontmatter.split('\n')) {
        if (line.startsWith('topic:')) metaTopic = line.replace('topic:', '').trim().replace(/['"]/g, '')
        if (line.startsWith('date:')) metaDate = line.replace('date:', '').trim()
      }
    }
  }

  const wordCount = body.trim().split(/\s+/).filter(Boolean).length
  const readTimeMin = Math.max(1, Math.ceil(wordCount / 220))

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback if clipboard API is unavailable
    }
  }

  const handleDownload = () => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename || `${(title || 'blog').toLowerCase().replace(/\s+/g, '-')}.md`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  // Simple line-based markdown renderer
  const renderLine = (line: string, index: number) => {
    const trimmed = line.trim()

    // Images: ![alt](url)
    const imageMatch = trimmed.match(/^!\[(.*?)\]\((.*?)\)$/)
    if (imageMatch) {
      const alt = imageMatch[1]
      let src = imageMatch[2]
      // Rewrite local relative image path to backend static files endpoint
      if (!src.startsWith('http://') && !src.startsWith('https://')) {
        const imageName = src.split(/[/\\]/).pop() || src
        src = `${API_BASE_URL}/api/images/files/${encodeURIComponent(imageName)}`
      }
      return (
        <figure key={index} className="reader-figure">
          <img src={src} alt={alt} className="reader-image" loading="lazy" />
          {alt && <figcaption className="reader-caption">{alt}</figcaption>}
        </figure>
      )
    }

    // Headings
    if (trimmed.startsWith('# ')) {
      return <h1 key={index} className="reader-h1">{renderInline(trimmed.slice(2))}</h1>
    }
    if (trimmed.startsWith('## ')) {
      return <h2 key={index} className="reader-h2">{renderInline(trimmed.slice(3))}</h2>
    }
    if (trimmed.startsWith('### ')) {
      return <h3 key={index} className="reader-h3">{renderInline(trimmed.slice(4))}</h3>
    }
    if (trimmed.startsWith('#### ')) {
      return <h4 key={index} className="reader-h4">{renderInline(trimmed.slice(5))}</h4>
    }

    // Blockquotes
    if (trimmed.startsWith('> ')) {
      return (
        <blockquote key={index} className="reader-blockquote">
          {renderInline(trimmed.slice(2))}
        </blockquote>
      )
    }

    // Horizontal Rule
    if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
      return <hr key={index} className="reader-hr" />
    }

    // Bullet Lists
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      return (
        <li key={index} className="reader-li">
          {renderInline(trimmed.slice(2))}
        </li>
      )
    }

    // Numbered lists
    const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (numMatch) {
      return (
        <li key={index} className="reader-li reader-ol-item" value={parseInt(numMatch[1], 10)}>
          {renderInline(numMatch[2])}
        </li>
      )
    }

    // Empty lines
    if (!trimmed) {
      return <div key={index} className="reader-spacer" />
    }

    // Paragraph
    return <p key={index} className="reader-p">{renderInline(line)}</p>
  }

  // Inline formatting helper: bold, italic, citations, inline code
  const renderInline = (text: string) => {
    // Replace citations [Source X] with badge
    const citationRegex = /\[Source\s+(\d+)\]/g
    const parts: (string | ReactNode)[] = []
    let lastIndex = 0
    let match: RegExpExecArray | null

    while ((match = citationRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }
      parts.push(
        <span key={`cite-${match.index}`} className="citation-badge">
          Source {match[1]}
        </span>
      )
      lastIndex = match.index + match[0].length
    }
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }

    return (
      <>
        {parts.map((part, i) => {
          if (typeof part !== 'string') return part

          // Handle simple bold **bold**
          const boldParts = part.split(/\*\*(.*?)\*\*/g)
          return boldParts.map((sub, j) => {
            if (j % 2 === 1) return <strong key={`${i}-${j}`}>{sub}</strong>

            // Handle simple italic *italic*
            const italicParts = sub.split(/\*(.*?)\*/g)
            return italicParts.map((item, k) => {
              if (k % 2 === 1) return <em key={`${i}-${j}-${k}`}>{item}</em>
              return item
            })
          })
        })}
      </>
    )
  }

  return (
    <div className="reader-modal">
      <div className="reader-backdrop" onClick={onClose} />
      <div className="reader-card">
        <header className="reader-header">
          <div className="reader-header-left">
            {onClose && (
              <button className="button button-ghost reader-back-btn" onClick={onClose}>
                <ArrowLeft size={16} /> Back
              </button>
            )}
            <div className="reader-meta-pills">
              <span className="reader-pill"><Clock size={13} /> {readTimeMin} min read</span>
              <span className="reader-pill"><FileText size={13} /> {wordCount} words</span>
              {metaDate && <span className="reader-pill">{metaDate}</span>}
            </div>
          </div>
          <div className="reader-actions">
            <button className="button button-secondary reader-action-btn" onClick={handleCopy}>
              {copied ? <Check size={15} className="reader-copied-icon" /> : <Copy size={15} />}
              {copied ? 'Copied' : 'Copy Markdown'}
            </button>
            <button className="button button-secondary reader-action-btn" onClick={handleDownload} title="Download .md file">
              <Download size={15} /> Download
            </button>
            {onClose && (
              <button className="icon-button reader-close-btn" aria-label="Close reader" onClick={onClose}>
                <X size={18} />
              </button>
            )}
          </div>
        </header>

        {metaTopic && (
          <div className="reader-topic-bar">
            <span>TOPIC</span> <strong>{metaTopic}</strong>
          </div>
        )}

        <article className="reader-body">
          {body.split('\n').map((line, idx) => renderLine(line, idx))}
        </article>
      </div>
    </div>
  )
}

export default MarkdownViewer
