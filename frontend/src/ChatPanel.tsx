import { useEffect, useRef, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { API_BASE_URL } from './config'

const transport = new DefaultChatTransport({ api: `${API_BASE_URL}/api/chat` })

const PROMPTS = [
  '介绍一下你自己',
  '帮我计算 123 × 456',
  '搜索知识库中的内容',
]

/** the composing mark — a quiet pulse, no bouncing dots */
function ComposingMark() {
  return <span className="compose smcp text-ink-3">composing</span>
}

type MarkdownMessageProps = { content: string }

function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
      components={{
        a: ({ href, children, ...props }) => (
          <a href={href} target="_blank" rel="noreferrer" {...props}>
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

type ExchangeProps = {
  index: number
  isUser: boolean
  children: React.ReactNode
}

/** monochrome stamp avatar — no gradients, no color icons */
function Avatar({ isUser }: { isUser: boolean }) {
  if (isUser) {
    return (
      <span className="shrink-0 w-9 h-9 rounded-full bg-ink flex items-center justify-center">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--color-paper)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
        </svg>
      </span>
    )
  }
  return (
    <span className="shrink-0 w-9 h-9 rounded-full bg-accent flex items-center justify-center">
      <span className="smcp text-paper leading-none">AI</span>
    </span>
  )
}

/** a single exchange in the transcript — labelled, ruled, never bubbled */
function Exchange({ index, isUser, children }: ExchangeProps) {
  return (
    <article className={`reveal flex gap-3.5 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <Avatar isUser={isUser} />
      <div className={`flex flex-col min-w-0 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <header className={`flex items-center gap-3 mb-3 w-full ${isUser ? 'flex-row-reverse' : ''}`}>
          <span className="smcp numeral text-ink-3">{String(index).padStart(2, '0')}</span>
          <span className="smcp text-ink">{isUser ? 'You' : 'Corvus'}</span>
          <span className="flex-1 h-px bg-rule" />
        </header>
        <div className={`w-full ${isUser ? 'border-r-2 border-ink pr-5 text-right' : ''}`}>{children}</div>
      </div>
    </article>
  )
}

function EmptyState({ onPick }: { onPick: (s: string) => void }) {
  return (
    <div className="flex flex-col justify-center min-h-full py-20">
      <div className="reveal">
        <p className="smcp text-ink-3 mb-5">— Corvus</p>
        <h2 className="font-serif text-5xl sm:text-6xl text-ink leading-[1.05] mb-6 tracking-tight">
          有何见教？
        </h2>
        <p className="text-ink-2 max-w-md leading-relaxed mb-14">
          向知识库提问，或自由对话。检索、推理、计算，皆可。
        </p>
        <div>
          {PROMPTS.map((p, i) => (
            <button
              key={p}
              onClick={() => onPick(p)}
              className="group w-full text-left flex items-baseline gap-5 py-4 border-t border-rule last:border-b transition-colors"
            >
              <span className="smcp numeral text-ink-3 w-8 shrink-0">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="text-ink-2 group-hover:text-ink transition-colors">
                {p}
              </span>
              <span className="ml-auto text-ink-3 group-hover:text-accent group-hover:translate-x-1 transition-all duration-300">
                →
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function ChatPanel() {
  const [input, setInput] = useState('')
  const chatEndRef = useRef<HTMLDivElement>(null)

  const { messages, status, error, sendMessage } = useChat({ transport })

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loading = status === 'submitted' || status === 'streaming'

  const sendCurrentMessage = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    try {
      await sendMessage({ text })
    } catch {
      setInput(text)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendCurrentMessage()
    }
  }

  const hasMessages = messages.length > 0
  const canSend = input.trim().length > 0 && !loading

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* transcript */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 sm:px-8">
          {!hasMessages ? (
            <EmptyState onPick={setInput} />
          ) : (
            <div className="py-10 space-y-11">
              {messages.map((message, idx) => {
                const text = message.parts
                  .filter(part => part.type === 'text')
                  .map(part => part.text)
                  .join('')
                const isUser = message.role === 'user'
                const isLastAI =
                  !isUser && message.id === messages[messages.length - 1]?.id

                return (
                  <Exchange key={message.id} index={idx + 1} isUser={isUser}>
                    {!text && isLastAI && loading ? (
                      <ComposingMark />
                    ) : isUser ? (
                      <p className="whitespace-pre-wrap text-ink leading-relaxed">
                        {text}
                      </p>
                    ) : (
                      <div className="x-markdown-wrapper">
                        <MarkdownMessage content={text} />
                      </div>
                    )}
                  </Exchange>
                )
              })}

              {error && (
                <div className="border-l-2 border-accent pl-4 py-1">
                  <p className="smcp text-accent mb-1.5">Error</p>
                  <p className="text-sm text-ink-2">
                    请求失败，请检查后端服务或网络连接。
                  </p>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* input — docked, framed */}
      <div className="shrink-0 border-t border-rule bg-paper">
        <div className="max-w-3xl mx-auto px-6 sm:px-8 py-5">
          <div className="flex items-end gap-4 border border-ink-2 bg-paper-2 px-5 py-4 transition-colors duration-200 focus-within:border-ink">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题…"
              disabled={loading}
              rows={1}
              className="flex-1 bg-transparent resize-none text-base text-ink placeholder-ink-3 focus:outline-none disabled:opacity-40 max-h-40 py-1.5"
              style={{ minHeight: '1.75rem' }}
              onInput={e => {
                const el = e.currentTarget
                el.style.height = 'auto'
                el.style.height = Math.min(el.scrollHeight, 160) + 'px'
              }}
            />
            <button
              onClick={() => void sendCurrentMessage()}
              disabled={!canSend}
              className="shrink-0 inline-flex items-center gap-2 bg-ink text-paper px-5 py-2.5 hover:bg-ink-2 disabled:bg-ink-3 disabled:cursor-not-allowed transition-colors duration-200"
              aria-label="发送"
            >
              <span className="smcp">发送</span>
              <span className="text-base leading-none">→</span>
            </button>
          </div>
          <p className="smcp text-ink-3 mt-3">
            Enter 发送 · Shift + Enter 换行
          </p>
        </div>
      </div>
    </div>
  )
}

export default ChatPanel
