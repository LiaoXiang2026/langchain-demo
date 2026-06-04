import { useState } from 'react'
import ChatPanel from './ChatPanel'
import KnowledgePanel from './KnowledgePanel'

type Tab = 'chat' | 'knowledge'

function App() {
  const [tab, setTab] = useState<Tab>('chat')

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* 顶部导航 */}
      <header className="bg-linear-to-r from-slate-800 via-slate-800 to-slate-700 border-b border-slate-700/50 sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Logo 图标 */}
            <div className="w-8 h-8 rounded-lg bg-linear-to-br from-blue-400 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
              </svg>
            </div>
            <h1 className="text-lg font-bold text-white tracking-tight">AI Agent</h1>
          </div>
          <nav className="flex bg-slate-700/50 rounded-lg p-1 gap-0.5">
            <button
              onClick={() => setTab('chat')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${
                tab === 'chat'
                  ? 'bg-white/15 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <span className="flex items-center gap-1.5">
                {/* 聊天气泡图标 */}
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                聊天
              </span>
            </button>
            <button
              onClick={() => setTab('knowledge')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all duration-200 ${
                tab === 'knowledge'
                  ? 'bg-white/15 text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              }`}
            >
              <span className="flex items-center gap-1.5">
                {/* 数据库图标 */}
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3"/>
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
                </svg>
                知识库
              </span>
            </button>
          </nav>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-5">
        {tab === 'chat' ? <ChatPanel /> : <KnowledgePanel />}
      </main>
    </div>
  )
}

export default App
