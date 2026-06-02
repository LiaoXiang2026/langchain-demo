import { useEffect, useRef, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'

// 传输层实例（模块级单例，避免重复创建）
const transport = new DefaultChatTransport({ api: '/api/chat' })

function ChatPanel() {
  const [input, setInput] = useState('')
  // 用于自动滚动到底部
  const chatEndRef = useRef<HTMLDivElement>(null)

  // AI SDK 的聊天 hook，自动管理消息状态和流式响应
  const {
    messages,
    status,
    error,
    sendMessage,
  } = useChat({ transport })

  // 消息更新时自动滚动到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 加载状态：正在提交或正在接收流式响应
  const loading = status === 'submitted' || status === 'streaming'

  // 发送当前输入的消息
  const sendCurrentMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    try {
      await sendMessage({ text })
    } catch {
      // 发送失败时恢复输入内容
      setInput(text)
    }
  }

  // 回车发送，Shift+Enter 换行
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendCurrentMessage()
    }
  }

  const hasMessages = messages.length > 0

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* 消息列表区域 */}
      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {/* 无消息时显示欢迎语 */}
        {!hasMessages && (
          <div className="flex justify-start">
            <div className="max-w-[80%] px-4 py-2 rounded-2xl text-sm bg-white text-gray-800 shadow-sm rounded-bl-md">
              你好！我是 AI 助手，有什么可以帮你的？
            </div>
          </div>
        )}
        {/* 渲染消息列表 */}
        {messages.map(message => {
          // 从消息 parts 中提取文本内容
          const text = message.parts
            .filter(part => part.type === 'text')
            .map(part => part.text)
            .join('')

          return (
            <div
              key={message.id}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] px-4 py-2 rounded-2xl text-sm ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white rounded-br-md'
                    : 'bg-white text-gray-800 shadow-sm rounded-bl-md'
                }`}
              >
                {/* 显示文本，最后一条消息无内容时显示"思考中..." */}
                {text || (loading && message.id === messages[messages.length - 1]?.id ? '思考中...' : '')}
              </div>
            </div>
          )
        })}
        {/* 错误提示 */}
        {error && (
          <div className="flex justify-start">
            <div className="max-w-[80%] px-4 py-2 rounded-2xl text-sm bg-red-50 text-red-700 border border-red-200">
              请求失败，请检查后端服务或网络连接。
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
      {/* 输入区域 */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          disabled={loading}
          className="flex-1 px-4 py-2 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
        />
        <button
          onClick={() => void sendCurrentMessage()}
          disabled={loading || !input.trim()}
          className="px-6 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          发送
        </button>
      </div>
    </div>
  )
}

export default ChatPanel
