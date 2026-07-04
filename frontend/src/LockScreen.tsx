import { useState } from 'react'

interface LockScreenProps {
  onUnlock: () => void
}

function LockScreen({ onUnlock }: LockScreenProps) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState(false)

  const correctPassword = import.meta.env.VITE_ACCESS_PASSWORD ?? ''

  // 如果没配置密码，直接放行
  if (!correctPassword) {
    onUnlock()
    return null
  }

  const handleSubmit = (e: React.SyntheticEvent) => {
    e.preventDefault()
    if (password === correctPassword) {
      sessionStorage.setItem('corvus_unlocked', '1')
      onUnlock()
    } else {
      setError(true)
      setPassword('')
      setTimeout(() => setError(false), 1500)
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-paper">
      <form onSubmit={handleSubmit} className="w-72 flex flex-col items-center gap-6">
        <div className="flex flex-col items-center gap-1">
          <h1 className="font-serif text-[1.7rem] leading-none text-ink tracking-tight">
            Corvus
          </h1>
          <span className="smcp text-ink-3">知识检索</span>
        </div>

        <div className="w-full flex flex-col gap-3">
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="输入访问密码"
            autoFocus
            className={`w-full px-4 py-2.5 bg-transparent border rounded-none outline-none
              text-sm text-ink placeholder:text-ink-3
              transition-colors duration-200
              ${error
                ? 'border-accent animate-[shake_0.4s_ease-in-out]'
                : 'border-rule focus:border-ink'
              }`}
          />
          <button
            type="submit"
            className="w-full py-2.5 bg-ink text-paper text-sm font-medium
              tracking-wide uppercase smcp
              hover:bg-ink-2 transition-colors duration-200"
          >
            进入
          </button>
        </div>

        {error && (
          <p className="text-accent text-xs smcp">密码错误</p>
        )}
      </form>
    </div>
  )
}

export default LockScreen
