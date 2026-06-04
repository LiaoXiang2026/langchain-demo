import { useState, useEffect, useCallback } from 'react'

interface DocInfo {
  filename: string
  chunk_count: number
}

interface SearchResult {
  content: string
  source: string
  chunk_id: number
}

const ALLOWED_FORMATS = '.txt,.md,.pdf,.docx,.xlsx,.xls'

function KnowledgePanel() {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searched, setSearched] = useState(false)

  const fetchDocs = useCallback(async () => {
    try {
      const res = await fetch('/knowledge/list')
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
        const res = await fetch('/knowledge/upload', { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.json()
          setUploadError(`${file.name}: ${err.detail}`)
          continue
        }
        const result = await res.json()
        setUploadMsg(`${result.filename} 上传成功 (${result.chunk_count} 个片段)`)
      } catch {
        setUploadError(`${file.name}: 网络连接失败`)
      }
    }

    setUploading(false)
    fetchDocs()
  }

  const handleDelete = async (filename: string) => {
    if (!confirm(`确定删除 ${filename}？`)) return
    try {
      await fetch(`/knowledge/${encodeURIComponent(filename)}`, { method: 'DELETE' })
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
      const res = await fetch('/knowledge/search', {
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

  return (
    <div className="space-y-5">
      {/* 上传区 */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <h2 className="font-semibold text-slate-800">上传文档</h2>
          </div>
        </div>
        <div className="p-5">
          <div
            className="relative border-2 border-dashed border-slate-200 rounded-xl p-10 text-center hover:border-blue-300 hover:bg-blue-50/30 transition-all duration-200 cursor-pointer group"
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
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3 group-hover:bg-blue-100 transition-colors duration-200">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="group-hover:stroke-blue-500 transition-colors duration-200">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="12" y1="18" x2="12" y2="12"/>
                <line x1="9" y1="15" x2="15" y2="15"/>
              </svg>
            </div>
            <p className="text-slate-500 text-sm font-medium">
              {uploading ? '处理中...' : '拖拽文件到此处，或点击选择文件'}
            </p>
            <p className="text-xs text-slate-400 mt-1.5">
              支持 TXT、Markdown、PDF、Word、Excel
            </p>
          </div>
          {uploadMsg && (
            <p className="mt-3 text-sm text-green-600 bg-green-50 px-3 py-2 rounded-lg">{uploadMsg}</p>
          )}
          {uploadError && (
            <p className="mt-3 text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{uploadError}</p>
          )}
        </div>
      </div>

      {/* 文档列表 */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
                <polyline points="13 2 13 9 20 9"/>
              </svg>
            </div>
            <h2 className="font-semibold text-slate-800">已入库文档</h2>
          </div>
          {docs.length > 0 && (
            <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{docs.length} 个文件</span>
          )}
        </div>
        <div className="p-5">
          {docs.length === 0 ? (
            <div className="text-center py-8">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-2.5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <p className="text-slate-400 text-sm">暂无文档，请上传文件构建知识库</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {docs.map(doc => (
                <div key={doc.filename} className="flex items-center justify-between py-3 first:pt-0 last:pb-0 group">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                      </svg>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-700 truncate">{doc.filename}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{doc.chunk_count} 个片段</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.filename)}
                    className="shrink-0 px-3 py-1.5 text-xs text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all duration-200 opacity-0 group-hover:opacity-100"
                  >
                    删除
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 搜索 */}
      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </div>
            <h2 className="font-semibold text-slate-800">知识库搜索</h2>
          </div>
        </div>
        <div className="p-5">
          <div className="flex gap-2.5">
            <div className="flex-1 relative">
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="输入关键词搜索知识库..."
                className="w-full pl-4 pr-4 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 transition-all duration-200"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={searching}
              className="px-5 py-2.5 bg-slate-800 text-white text-sm font-medium rounded-xl hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 shadow-sm active:scale-95"
            >
              {searching ? '搜索中...' : '搜索'}
            </button>
          </div>

          {/* 搜索结果 */}
          {searched && (
            <div className="mt-4">
              {searching ? (
                <div className="text-center py-8 text-sm text-slate-400">搜索中...</div>
              ) : searchResults.length === 0 ? (
                <div className="text-center py-8">
                  <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-2.5">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8"/>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                  </div>
                  <p className="text-slate-400 text-sm">未找到相关结果</p>
                </div>
              ) : (
                <div className="space-y-2.5">
                  <p className="text-xs text-slate-400">找到 {searchResults.length} 条结果</p>
                  {searchResults.map((r, i) => (
                    <div key={i} className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-medium text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">
                          #{r.chunk_id}
                        </span>
                        <span className="text-xs text-slate-400 truncate">{r.source}</span>
                      </div>
                      <p className="text-sm text-slate-700 leading-relaxed">{r.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default KnowledgePanel
