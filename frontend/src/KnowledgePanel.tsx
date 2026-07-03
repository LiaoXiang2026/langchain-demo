import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from './config'

interface DocInfo {
  filename: string
  chunk_count: number
}

interface SearchResult {
  content: string
  source: string
  chunk_id: number
}

const ALLOWED_FORMATS = '.md,.pdf,.html,.htm'

/** section header — editorial, with index + oxblood tick on the active one */
function SectionHead({
  index,
  title,
  meta,
  active,
}: {
  index: string
  title: string
  meta?: string
  active?: boolean
}) {
  return (
    <header className="flex items-baseline gap-3 pb-4 mb-6 border-b border-ink">
      <span className="smcp numeral text-ink-3">{index}</span>
      <h2 className="font-serif text-2xl text-ink leading-none">{title}</h2>
      {active && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
      {meta && (
        <span className="smcp numeral text-ink-3 ml-auto">{meta}</span>
      )}
    </header>
  )
}

function KnowledgePanel() {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)
  const [filterQuery, setFilterQuery] = useState('')

  const fetchDocs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/knowledge/list`)
      const data = await res.json()
      setDocs(data)
    } catch {
      // 静默处理
    }
  }, [])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadMsg('')
    setUploadError('')

    for (const file of Array.from(files)) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch(`${API_BASE_URL}/api/knowledge/upload`, { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.json()
          setUploadError(`${file.name}: ${err.detail}`)
          continue
        }
        const result = await res.json()
        setUploadMsg(`${result.filename} 已入库 · ${result.chunk_count} 片段`)
      } catch {
        setUploadError(`${file.name}: 网络连接失败`)
      }
    }

    setUploading(false)
    fetchDocs()
  }

  const handleDelete = async (filename: string) => {
    if (!confirm(`确定移除 ${filename}？`)) return
    try {
      await fetch(`${API_BASE_URL}/api/knowledge/${encodeURIComponent(filename)}`, { method: 'DELETE' })
      fetchDocs()
    } catch {
      // 静默处理
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    setSearched(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/knowledge/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      })
      const data = await res.json()
      setSearchResults(data)
    } catch {
      setSearchResults([])
    }
    setSearching(false)
  }

  const filteredDocs = filterQuery.trim()
    ? docs.filter(d => d.filename.toLowerCase().includes(filterQuery.trim().toLowerCase()))
    : docs

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 sm:px-8 py-10 space-y-14">

        {/* 入库 + 档案 — 左右并置，窄屏堆叠 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 lg:gap-16">
        {/* 01 — 入库 */}
        <section className="lg:pr-16 lg:border-r lg:border-rule">
          <SectionHead index="01" title="入库" active={uploading} />
          <div
            className="group relative cursor-pointer border border-rule hover:border-ink-2 transition-colors duration-300"
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault()
              handleUpload(e.dataTransfer.files)
            }}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept={ALLOWED_FORMATS}
              multiple
              className="hidden"
              onChange={e => handleUpload(e.target.files)}
            />
            <div className="px-8 py-12 text-center">
              <p className="font-serif text-2xl text-ink mb-2">
                {uploading ? '入库中…' : '拖入文档，或点击选择'}
              </p>
              <p className="smcp text-ink-3">
                Markdown · PDF · HTML
              </p>
            </div>
          </div>
          {uploadMsg && (
            <p className="fade smcp text-ink-2 mt-4 pl-4 border-l border-accent">
              {uploadMsg}
            </p>
          )}
          {uploadError && (
            <p className="fade smcp text-accent mt-4 pl-4 border-l border-accent">
              {uploadError}
            </p>
          )}
        </section>

        {/* 02 — 档案 */}
        <section>
          <SectionHead
            index="02"
            title="档案"
            meta={
              docs.length > 0
                ? filterQuery.trim()
                  ? `${filteredDocs.length} / ${docs.length}`
                  : `${docs.length} 文件`
                : undefined
            }
          />
          {docs.length === 0 ? (
            <div className="py-10">
              <p className="font-serif italic text-xl text-ink-3">
                尚无文档
              </p>
              <p className="text-sm text-ink-3 mt-1">
                向上滑，上传文件以构建知识库。
              </p>
            </div>
          ) : (
            <>
              {/* 本地筛选 — 按文件名 */}
              <div className="flex items-baseline gap-3 border-b border-rule pb-2.5 mb-2">
                <span className="smcp text-ink-3 shrink-0">筛选</span>
                <input
                  type="text"
                  value={filterQuery}
                  onChange={e => setFilterQuery(e.target.value)}
                  placeholder="按文件名…"
                  className="flex-1 bg-transparent text-sm text-ink placeholder-ink-3 focus:outline-none"
                />
                {filterQuery && (
                  <button
                    onClick={() => setFilterQuery('')}
                    className="smcp text-ink-3 hover:text-ink transition-colors"
                    aria-label="清除筛选"
                  >
                    ✕
                  </button>
                )}
              </div>
              <ul className="max-h-96 overflow-y-auto">
                {filteredDocs.map((doc, i) => (
                  <li
                    key={doc.filename}
                    className="group flex items-baseline gap-5 py-4 border-t border-rule last:border-b"
                  >
                    <span className="smcp numeral text-ink-3 w-8 shrink-0">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-ink truncate">{doc.filename}</p>
                      <p className="smcp numeral text-ink-3 mt-0.5">
                        {doc.chunk_count} 片段
                      </p>
                    </div>
                    <button
                      onClick={() => handleDelete(doc.filename)}
                      className="smcp text-ink-3 hover:text-accent transition-colors duration-200 opacity-0 group-hover:opacity-100"
                    >
                      移除
                    </button>
                  </li>
                ))}
                {filteredDocs.length === 0 && (
                  <li className="py-8">
                    <p className="font-serif italic text-base text-ink-3">
                      无匹配文件
                    </p>
                  </li>
                )}
              </ul>
            </>
          )}
        </section>
        </div>

        {/* 03 — 检索 */}
        <section>
          <SectionHead index="03" title="检索" active={searching} />
          <div className="flex items-baseline gap-4 border-b border-ink pb-3">
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="输入关键词…"
              className="flex-1 bg-transparent text-lg text-ink placeholder-ink-3 focus:outline-none"
            />
            <button
              onClick={handleSearch}
              disabled={searching}
              className="group shrink-0 inline-flex items-center gap-2 disabled:opacity-40"
            >
              <span className="smcp text-accent group-hover:text-accent-2 transition-colors">
                {searching ? '检索中' : '检索'}
              </span>
              <span className="text-accent group-hover:translate-x-1 transition-transform duration-200">
                →
              </span>
            </button>
          </div>

          {searched && (
            <div className="mt-8">
              {searching ? (
                <p className="smcp text-ink-3">检索中…</p>
              ) : searchResults.length === 0 ? (
                <div className="py-6">
                  <p className="font-serif italic text-xl text-ink-3">
                    未命中
                  </p>
                  <p className="text-sm text-ink-3 mt-1">
                    换个关键词，或确认档案已入库。
                  </p>
                </div>
              ) : (
                <div className="space-y-8">
                  <p className="smcp text-ink-3">
                    命中 {String(searchResults.length).padStart(2, '0')} 条
                  </p>
                  {searchResults.map((r, i) => (
                    <article key={i} className="reveal">
                      <header className="flex items-baseline gap-3 mb-2.5">
                        <span className="smcp numeral text-ink-3">
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        <span className="smcp text-ink-2 truncate">
                          {r.source}
                        </span>
                        <span className="smcp numeral text-ink-3 shrink-0">
                          chunk {r.chunk_id}
                        </span>
                      </header>
                      <p className="text-ink-2 leading-relaxed pl-11">
                        {r.content}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

      </div>
    </div>
  )
}

export default KnowledgePanel
