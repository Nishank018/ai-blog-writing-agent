import { API_BASE_URL } from '../config'

export type BlogSummary = {
  filename: string
  title: string
  topic: string
  date: string
  size: number
}

export type BlogDetail = {
  filename: string
  content: string
}

export type ImageAttribution = {
  filename: string
  title: string
  artist: string
  license: string
  license_url: string
  description_url: string
}

export async function fetchBlogs(): Promise<BlogSummary[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/blogs`)
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export async function fetchBlogDetail(filename: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/blogs/${encodeURIComponent(filename)}`)
    if (!res.ok) return null
    const data = await res.json() as { content?: string }
    return data.content ?? null
  } catch {
    return null
  }
}

export async function fetchImages(): Promise<ImageAttribution[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/images`)
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}
