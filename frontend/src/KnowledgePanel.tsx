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
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)

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

    for (const file of Array.from(files)) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch('/knowledge/upload', { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.json()
          setUploadMsg(`上传失败: ${err.detail}`)
          continue
        }
        const result = await res.json()
        setUploadMsg(`已上传 ${result.filename}，${result.chunk_count} 个片段`)
      } catch {
        setUploadMsg('上传失败，请检查网络连接')
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
    <div className="space-y-6">
      {/* 上传区 */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">上传文档</h2>
        <div
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
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
          <p className="text-gray-500">
            {uploading ? '处理中...' : '拖拽文件到此处，或点击选择文件'}
          </p>
          <p className="text-xs text-gray-400 mt-2">
            支持格式：TXT、Markdown、PDF、Word、Excel
          </p>
        </div>
        {uploadMsg && (
          <p className="mt-2 text-sm text-green-600">{uploadMsg}</p>
        )}
      </div>

      {/* 文档列表 */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">已入库文档</h2>
        {docs.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无文档，请上传文件</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {docs.map(doc => (
              <div key={doc.filename} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-gray-700">{doc.filename}</p>
                  <p className="text-xs text-gray-400">{doc.chunk_count} 个片段</p>
                </div>
                <button
                  onClick={() => handleDelete(doc.filename)}
                  className="text-red-500 hover:text-red-700 text-sm transition-colors"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 搜索测试 */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">知识库搜索</h2>
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="输入搜索内容..."
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
          >
            {searching ? '搜索中...' : '搜索'}
          </button>
        </div>
        {searchResults.length > 0 && (
          <div className="space-y-3">
            {searchResults.map((r, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-400 mb-1">来源: {r.source} (片段 #{r.chunk_id})</p>
                <p className="text-sm text-gray-700">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default KnowledgePanel
