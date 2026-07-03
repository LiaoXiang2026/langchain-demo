import { useState } from 'react'
import ChatPanel from './ChatPanel'
import KnowledgePanel from './KnowledgePanel'

type Tab = 'chat' | 'knowledge'

const TABS: { id: Tab; index: string; label: string }[] = [
  { id: 'chat', index: '01', label: '对话' },
  { id: 'knowledge', index: '02', label: '知识库' },
]

function App() {
  const [tab, setTab] = useState<Tab>('chat')

  return (
    <div className="h-screen flex flex-col bg-paper text-ink">
      <header className="shrink-0 border-b border-rule">
        <div className="max-w-3xl mx-auto px-6 sm:px-8 h-16 flex items-center justify-between">
          {/* wordmark */}
          <div className="flex items-baseline gap-3">
            <h1 className="font-serif text-[1.7rem] leading-none text-ink tracking-tight">
              Corvus
            </h1>
            <span className="smcp text-ink-3 hidden sm:inline">知识检索</span>
          </div>

          {/* nav — text links, underline on active */}
          <nav className="flex items-center gap-7">
            {TABS.map(({ id, index, label }) => {
              const active = tab === id
              return (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className="group relative pb-2"
                  aria-current={active ? 'page' : undefined}
                >
                  <span className="inline-flex items-baseline gap-2">
                    <span className="smcp numeral text-ink-3">{index}</span>
                    <span
                      className={`text-sm transition-colors duration-200 ${
                        active ? 'text-ink' : 'text-ink-3 group-hover:text-ink-2'
                      }`}
                    >
                      {label}
                    </span>
                  </span>
                  <span
                    className={`absolute bottom-0 left-0 right-0 h-px bg-ink transition-opacity duration-300 ${
                      active ? 'opacity-100' : 'opacity-0'
                    }`}
                  />
                </button>
              )
            })}
          </nav>
        </div>
      </header>

      <main className="flex-1 min-h-0 flex flex-col">
        {tab === 'chat' ? <ChatPanel /> : <KnowledgePanel />}
      </main>
    </div>
  )
}

export default App
