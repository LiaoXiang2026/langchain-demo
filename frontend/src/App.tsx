import { useState } from 'react'
import ChatPanel from './ChatPanel'
import KnowledgePanel from './KnowledgePanel'

type Tab = 'chat' | 'knowledge'

function App() {
  const [tab, setTab] = useState<Tab>('chat')

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <header className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-6">
          <h1 className="text-xl font-bold text-gray-800">AI Agent</h1>
          <nav className="flex gap-1">
            <button
              onClick={() => setTab('chat')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === 'chat'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              聊天
            </button>
            <button
              onClick={() => setTab('knowledge')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === 'knowledge'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              知识库管理
            </button>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-4xl w-full mx-auto p-4">
        {tab === 'chat' ? <ChatPanel /> : <KnowledgePanel />}
      </main>
    </div>
  )
}

export default App
