import { useEffect, useRef, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'

const transport = new DefaultChatTransport({ api: '/api/chat' })

/** 打字动画指示器：三个跳动圆点 */
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-0.5">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }}
        />
      ))}
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

  return (
    <div className="flex flex-col h-[calc(100vh-125px)]">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto scroll-smooth">
        {!hasMessages ? (
          /* 空状态欢迎页 */
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-linear-to-br from-blue-400 to-blue-600 flex items-center justify-center mb-5 shadow-xl shadow-blue-500/20">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
              </svg>
            </div>
            <h2 className="text-xl font-bold text-slate-800 mb-2">你好，我是 AI 助手</h2>
            <p className="text-slate-500 max-w-md leading-relaxed">
              我可以回答问题、搜索知识库、进行数学计算。在下方输入你的问题开始对话。
            </p>
            {/* 快捷提示 */}
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              {['介绍一下你自己', '帮我计算 123 * 456', '搜索知识库中的内容'].map(hint => (
                <button
                  key={hint}
                  onClick={() => { setInput(hint) }}
                  className="px-3.5 py-2 rounded-full text-sm text-slate-500 bg-white border border-slate-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-all duration-200 cursor-pointer"
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* 消息列表 */
          <div className="space-y-5 pb-3">
            {messages.map(message => {
              const text = message.parts
                .filter(part => part.type === 'text')
                .map(part => part.text)
                .join('')
              const isUser = message.role === 'user'
              const isLastAI = !isUser && message.id === messages[messages.length - 1]?.id

              return (
                <div key={message.id} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
                  {/* AI 头像 */}
                  {!isUser && (
                    <div className="w-7 h-7 rounded-full bg-linear-to-br from-blue-400 to-blue-600 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                        <path d="M2 17l10 5 10-5"/>
                        <path d="M2 12l10 5 10-5"/>
                      </svg>
                    </div>
                  )}
                  <div className={`max-w-[75%] ${isUser ? 'order-first' : ''}`}>
                    {/* 发送者标签 */}
                    <p className={`text-xs font-medium mb-1 px-1 ${isUser ? 'text-right text-slate-400' : 'text-slate-400'}`}>
                      {isUser ? '你' : 'AI 助手'}
                    </p>
                    {/* 消息气泡 */}
                    <div
                      className={`px-4 py-2.5 text-sm leading-relaxed ${
                        isUser
                          ? 'bg-linear-to-br from-blue-500 to-blue-600 text-white rounded-2xl rounded-tr-md shadow-md shadow-blue-500/15'
                          : 'bg-white text-slate-700 rounded-2xl rounded-tl-md shadow-sm border border-slate-100'
                      }`}
                    >
                      {text ? (
                        <span className="whitespace-pre-wrap">{text}</span>
                      ) : isLastAI && loading ? (
                        <TypingIndicator />
                      ) : (
                        ''
                      )}
                    </div>
                  </div>
                  {/* 用户头像 */}
                  {isUser && (
                    <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                      </svg>
                    </div>
                  )}
                </div>
              )
            })}
            {/* 错误提示 */}
            {error && (
              <div className="flex justify-center">
                <div className="px-4 py-2.5 rounded-xl text-sm bg-red-50 text-red-600 border border-red-200 max-w-md text-center">
                  请求失败，请检查后端服务或网络连接。
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* 输入区域 */}
      <div className="shrink-0 pt-3">
        <div className="flex gap-2.5 items-end bg-white rounded-2xl shadow-sm border border-slate-200 p-2 focus-within:border-blue-300 focus-within:shadow-md focus-within:shadow-blue-500/5 transition-all duration-200">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息..."
            disabled={loading}
            rows={1}
            className="flex-1 px-3 py-2 bg-transparent resize-none text-sm text-slate-700 placeholder-slate-400 focus:outline-none disabled:opacity-40 max-h-32"
            style={{ minHeight: '2.5rem' }}
            onInput={e => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 128) + 'px'
            }}
          />
          <button
            onClick={() => void sendCurrentMessage()}
            disabled={loading || !input.trim()}
            className="shrink-0 w-9 h-9 rounded-xl bg-blue-500 text-white flex items-center justify-center hover:bg-blue-600 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 shadow-sm shadow-blue-500/20 active:scale-95"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        <p className="text-center text-xs text-slate-400 mt-2">
          按 Enter 发送，Shift + Enter 换行
        </p>
      </div>
    </div>
  )
}

export default ChatPanel
