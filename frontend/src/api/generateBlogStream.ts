import { API_BASE_URL } from '../config'

export type BlogStreamEventName = 'running' | 'completed' | 'skipped' | 'error' | 'complete'

export type BlogStreamEvent = {
  name: BlogStreamEventName
  data: Record<string, unknown>
}

const supportedEvents = new Set<BlogStreamEventName>([
  'running',
  'completed',
  'skipped',
  'error',
  'complete',
])

function decodeEvent(name: string, rawData: string): BlogStreamEvent | null {
  if (!supportedEvents.has(name as BlogStreamEventName)) return null

  try {
    const data: unknown = JSON.parse(rawData)
    if (typeof data !== 'object' || data === null || Array.isArray(data)) {
      throw new Error('Invalid event payload')
    }
    return { name: name as BlogStreamEventName, data: data as Record<string, unknown> }
  } catch {
    throw new Error('The backend sent an unreadable activity update.')
  }
}

export async function* generateBlogStream(
  topic: string,
  signal: AbortSignal,
): AsyncGenerator<BlogStreamEvent> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/api/generate/stream`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ topic }),
      signal,
    })
  } catch {
    if (signal.aborted) return
    throw new Error('Could not connect to the local backend. Check that it is running and try again.')
  }

  if (!response.ok || !response.body) {
    throw new Error('The backend could not start generation. Please try again.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = 'message'
  let dataLines: string[] = []

  const processLine = (line: string, events: BlogStreamEvent[]) => {
    if (line === '') {
      if (dataLines.length > 0) {
        const event = decodeEvent(eventName, dataLines.join('\n'))
        if (event) events.push(event)
      }
      eventName = 'message'
      dataLines = []
      return
    }

    if (line.startsWith(':')) return
    const separator = line.indexOf(':')
    const field = separator < 0 ? line : line.slice(0, separator)
    let value = separator < 0 ? '' : line.slice(separator + 1)
    if (value.startsWith(' ')) value = value.slice(1)

    if (field === 'event') eventName = value
    if (field === 'data') dataLines.push(value)
  }

  const drainCompleteLines = (flush = false): BlogStreamEvent[] => {
    const events: BlogStreamEvent[] = []
    let cursor = 0

    while (cursor < buffer.length) {
      const lineEnd = buffer.slice(cursor).search(/[\r\n]/)
      if (lineEnd < 0) break

      const absoluteEnd = cursor + lineEnd
      const separator = buffer[absoluteEnd]
      if (separator === '\r' && absoluteEnd === buffer.length - 1 && !flush) break

      const separatorLength = separator === '\r' && buffer[absoluteEnd + 1] === '\n' ? 2 : 1
      processLine(buffer.slice(cursor, absoluteEnd), events)
      cursor = absoluteEnd + separatorLength
    }

    buffer = buffer.slice(cursor)
    if (flush) {
      if (buffer.length > 0) {
        processLine(buffer, events)
        buffer = ''
      }
      processLine('', events)
    }

    return events
  }

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      for (const event of drainCompleteLines()) yield event
    }

    buffer += decoder.decode()
    for (const event of drainCompleteLines(true)) yield event
  } finally {
    if (signal.aborted) {
      try {
        await reader.cancel()
      } catch {
        // The fetch may already have canceled this stream.
      }
    }
    reader.releaseLock()
  }
}
