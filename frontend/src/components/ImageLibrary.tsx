import { useState, useEffect } from 'react'
import { Check, Copy, ExternalLink, FileImage, RefreshCw } from 'lucide-react'
import { fetchImages, type ImageAttribution } from '../api/blogs'
import { API_BASE_URL } from '../config'

export function ImageLibrary() {
  const [images, setImages] = useState<ImageAttribution[]>([])
  const [loading, setLoading] = useState(true)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  const loadImages = async () => {
    setLoading(true)
    const list = await fetchImages()
    setImages(list)
    setLoading(false)
  }

  useEffect(() => {
    loadImages()
  }, [])

  const handleCopyMarkdown = async (img: ImageAttribution, idx: number) => {
    const markdown = `![${img.title || 'Image'}](/api/images/files/${encodeURIComponent(img.filename)})`
    try {
      await navigator.clipboard.writeText(markdown)
      setCopiedIndex(idx)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch {
      // Fallback
    }
  }

  return (
    <div className="subpage image-library-page">
      <div className="library-top-bar">
        <div>
          <p className="eyebrow"><span className="status-dot" /> MEDIA ARCHIVE</p>
          <h1>Image Library</h1>
          <p className="library-subtitle">
            All free Wikimedia Commons images collected during blog generation ({images.length} {images.length === 1 ? 'image' : 'images'}).
          </p>
        </div>
        <div className="library-actions">
          <button className="button button-ghost" onClick={loadImages} title="Refresh image library">
            <RefreshCw size={15} className={loading ? 'generate-spinner' : ''} /> Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="library-loading">
          <span className="local-instance-dot" /> Loading images...
        </div>
      ) : images.length === 0 ? (
        <div className="empty-state">
          <div className="subpage-icon"><FileImage size={24} /></div>
          <h3>No images in your library yet</h3>
          <p className="empty-description">
            When you generate blogs with image research enabled, free Wikimedia images will be saved here automatically.
          </p>
        </div>
      ) : (
        <div className="image-grid">
          {images.map((img, idx) => {
            const fileUrl = `${API_BASE_URL}/api/images/files/${encodeURIComponent(img.filename)}`
            const cleanTitle = (img.title || img.filename).replace(/^File:/, '')

            return (
              <article key={`${img.filename}-${idx}`} className="image-card">
                <div className="image-thumb-container">
                  <img
                    src={fileUrl}
                    alt={cleanTitle}
                    className="image-thumb"
                    loading="lazy"
                    onError={(e) => {
                      // Fallback if image load fails
                      (e.target as HTMLElement).style.display = 'none'
                    }}
                  />
                </div>
                <div className="image-card-details">
                  <h4 className="image-card-title" title={cleanTitle}>{cleanTitle}</h4>
                  <div className="image-card-meta">
                    {img.artist && <span className="image-artist">By {img.artist}</span>}
                    {img.license && <span className="image-license-badge">{img.license}</span>}
                  </div>
                  <div className="image-card-actions">
                    <button
                      className="button button-secondary image-copy-btn"
                      onClick={() => handleCopyMarkdown(img, idx)}
                    >
                      {copiedIndex === idx ? <Check size={13} /> : <Copy size={13} />}
                      {copiedIndex === idx ? 'Copied' : 'Copy MD'}
                    </button>
                    {img.description_url && (
                      <a
                        href={img.description_url}
                        target="_blank"
                        rel="noreferrer"
                        className="button button-ghost image-source-btn"
                        title="View on Wikimedia Commons"
                      >
                        <ExternalLink size={13} /> Source
                      </a>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default ImageLibrary
