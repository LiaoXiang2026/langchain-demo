import { useState, useRef, useEffect } from 'react'
import './App.css'

interface Message {
  role: 'user' | 'ai'
  text: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', text: '你好！我是 AI 助手，有什么可以帮你的？' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    setMessages(prev => [...prev, { role: 'user', text }])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      })
      if (!res.ok) throw new Error('请求失败')

      // TextDecoderStream 将字节流解码为文本流
      const textStream = res.body!.pipeThrough(new TextDecoderStream())
      const reader = textStream.getReader()
      let aiText = ''
      let buffer = ''

      // 添加空的 AI 消息，后续逐步更新
      setMessages(prev => [...prev, { role: 'ai', text: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += value

        // SSE 事件以 \n\n 分隔
        const parts = buffer.split('\n\n')
        buffer = parts.pop()!  // 最后一个可能是不完整的事件

        for (const part of parts) {
          const dataLine = part.trim()
          if (!dataLine.startsWith('data: ')) continue
          const data = dataLine.slice(6)
          if (data === '[DONE]') return

          try {
            const parsed = JSON.parse(data)
            aiText += parsed.content
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = { role: 'ai', text: aiText }
              return updated
            })
          } catch {
            // 忽略解析错误
          }
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last.role === 'ai' && !last.text) {
          updated[updated.length - 1] = { role: 'ai', text: '请求失败，请检查网络连接。' }
        }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="app">
      <div className="header">
        <h1>AI Agent</h1>
      </div>
      <div className="chat-container">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="bubble">{msg.text}</div>
          </div>
        ))}
        {loading && messages[messages.length - 1]?.text === '' && (
          <div className="message ai">
            <div className="typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          发送
        </button>
      </div>
    </div>
  )
}

export default App
