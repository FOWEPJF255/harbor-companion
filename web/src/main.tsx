import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Memory = {id: string; content: string; status: 'pending' | 'approved'}
type Message = {role: 'user' | 'assistant'; content: string; emotion: string}
type Insight = {turn_count: number; median_latency_ms: number | null; emotion_counts: Record<string, number>}
type Session = {id: string; mode: string; messages: Message[]; memories: Memory[]; insights: Insight}
type Status = {provider: string; configured: boolean; model: string | null}
type Trace = {type: string; name: string; status: string; step?: number}
type Run = {reply: string; provider: string; trace: Trace[]; latency_ms: number; emotion: string}

async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {method, headers: body ? {'Content-Type': 'application/json'} : {}, body: body ? JSON.stringify(body) : undefined})
  if (!response.ok) {
    const detail = await response.json().catch(() => ({detail: '服务暂时不可用，请检查后端。'}))
    throw new Error(typeof detail.detail === 'string' ? detail.detail : '输入内容不符合要求。')
  }
  return response.json()
}

const moodNames: Record<string, string> = {calm: '平静', bright: '轻快', low: '低落', overwhelmed: '需要放松'}

function Portrait({mood = 'calm', small = false}: {mood?: string; small?: boolean}) {
  return <div className={`portrait ${small ? 'small' : ''}`} data-mood={mood}>
    <svg viewBox="0 0 280 320" role="img" aria-label="Nova 的原创二维角色头像">
      <defs><linearGradient id={small ? 'hair-small' : 'hair'} x2="1" y2="1"><stop stopColor="#253f5a"/><stop offset="1" stopColor="#0a233b"/></linearGradient></defs>
      <circle cx="140" cy="148" r="118" fill="#d4e5df" opacity=".1"/>
      <path d="M64 259 Q46 86 107 59 Q179 23 216 108 L219 260Z" fill={`url(#${small ? 'hair-small' : 'hair'})`}/>
      <path d="M51 320Q49 254 116 246L163 246Q227 253 234 320" fill="#8bb7b1"/>
      <path d="M119 220L118 262Q140 286 164 261L161 220" fill="#edba9e"/>
      <ellipse cx="141" cy="162" rx="66" ry="82" fill="#f7ceb1"/>
      <path d="M74 156Q65 64 145 67Q208 67 212 136Q181 118 164 84Q146 123 74 156" fill="#1d354e"/>
      <path d="M102 159Q112 153 122 159M160 159Q170 153 180 159" stroke="#35495a" strokeWidth="3" fill="none" strokeLinecap="round"/>
      <ellipse className="eye" cx="113" cy="173" rx="5" ry="7" fill="#344e51"/><ellipse className="eye" cx="170" cy="173" rx="5" ry="7" fill="#344e51"/>
      <ellipse cx="98" cy="193" rx="12" ry="5" fill="#df938b" opacity=".4"/><ellipse cx="184" cy="193" rx="12" ry="5" fill="#df938b" opacity=".4"/>
      <path d="M131 211Q142 220 155 210" stroke="#b9796d" strokeWidth="3" fill="none" strokeLinecap="round"/>
      <path d="M207 126L212 186Q205 236 180 262L194 186Z" fill="#1d354e"/>
      <path d="M85 242L107 263L97 309M180 259L192 290" stroke="#c1d6ca" strokeWidth="3" fill="none"/>
      <circle cx="207" cy="121" r="7" fill="#f5d29a"/><path d="M195 121H219M207 109V133" stroke="#f5d29a" strokeWidth="2"/>
    </svg>
  </div>
}

function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [adult, setAdult] = useState(false)
  const [mode, setMode] = useState('friend')
  const [draft, setDraft] = useState('')
  const [memoryDraft, setMemoryDraft] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [lastRun, setLastRun] = useState<Run | null>(null)
  const [panel, setPanel] = useState<'memory' | 'insight'>('memory')
  const retry = useRef<{sid: string; text: string; id: string} | null>(null)

  useEffect(() => {
    api<Status>('/status').then(setStatus).catch(() => setError('后端尚未启动，请运行 scripts/start.ps1。'))
    const sid = localStorage.getItem('harbor-session')
    if (sid) api<Session>(`/sessions/${sid}`).then(setSession).catch(() => localStorage.removeItem('harbor-session'))
  }, [])

  async function refresh(sid: string) {setSession(await api<Session>(`/sessions/${sid}`))}
  async function start() {
    setBusy(true); setError('')
    try {
      const s = await api<{id: string}>('/sessions', 'POST', {adult_confirmed: adult, mode})
      localStorage.setItem('harbor-session', s.id); await refresh(s.id)
    } catch (e) {setError((e as Error).message)} finally {setBusy(false)}
  }
  async function send(text = draft) {
    if (!session || !text.trim() || busy) return
    setBusy(true); setError(''); setDraft('')
    const request = retry.current?.sid === session.id && retry.current.text === text
      ? retry.current : {sid: session.id, text, id: crypto.randomUUID()}
    retry.current = request
    try {
      const r = await api<Run>(`/sessions/${session.id}/chat`, 'POST', {message: text, request_id: request.id})
      setLastRun(r); await refresh(session.id); retry.current = null
    } catch (e) {setError((e as Error).message); setDraft(text)} finally {setBusy(false)}
  }
  async function memoryAction(mid: string, action: string) {
    if (!session) return
    setError('')
    try {await api(`/sessions/${session.id}/memories/${mid}/${action}`, 'POST'); await refresh(session.id)} catch(e) {setError((e as Error).message)}
  }
  async function addMemory() {
    if (!session || !memoryDraft.trim()) return
    setError('')
    try {await api(`/sessions/${session.id}/memories`, 'POST', {content: memoryDraft}); setMemoryDraft(''); await refresh(session.id)} catch(e) {setError((e as Error).message)}
  }
  async function clear(all: boolean) {
    if (!session || busy || !confirm(all ? '删除当前会话、记忆和本地运行记录？' : '清空对话和待确认记忆？已确认记忆将保留。')) return
    setError('')
    try {
      await api(`/sessions/${session.id}${all ? '' : '/history'}`, 'DELETE'); setLastRun(null); retry.current = null
      if (all) {localStorage.removeItem('harbor-session'); setSession(null)} else await refresh(session.id)
    } catch(e) {setError((e as Error).message)}
  }

  const mood = lastRun?.emotion || session?.messages.at(-1)?.emotion || 'calm'
  const mock = status?.provider === 'mock'
  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#"><span className="brand-icon">◒</span><strong>harbor</strong><span className="version">COMPANION LAB / 0.1</span></a>
      <span className={`provider-pill ${mock ? 'mock' : ''}`}><i/> {status ? mock ? '模拟模型 · 框架演示' : `${status.model || '模型待配置'}` : '连接本地服务…'}</span>
    </header>
    <main className="layout">
      <aside className="character-panel">
        <p className="eyebrow">A LITTLE SPACE TO LAND</p><h1>陪你<br/>停靠片刻<span>。</span></h1>
        <Portrait mood={mood}/>
        <div className="character-title"><h2>Nova <span>✦</span></h2><span className="tag">AI 陪伴角色</span></div>
        <p className="character-copy">不急着给出答案。<br/>先听你说，再一起找一个小小的下一步。</p>
        <div className="character-status"><i/> {moodNames[mood] || '平静'} <span>· {session?.mode === 'gentle_romance' ? '温柔关系' : '朋友陪伴'}</span></div>
        <div className="principles"><span>透明身份</span><span>可删除记忆</span><span>随时暂停</span></div>
        <p className="footer-note">本地研究原型 · 面向成年人<br/>不是心理诊断或紧急服务</p>
      </aside>

      <section className="conversation-panel" aria-label="对话">
        <div className="conversation-header"><div><h2>今天，想聊点什么？</h2><p>{session ? '你决定话题，也决定我们记住什么。' : '为自己留一小段安静的时间。'}</p></div><span className="flower">✳</span></div>
        {mock && <div className="demo-notice"><strong>DEMO MODE</strong> 当前是固定回复与工具流程演示，不代表真实模型的对话质量。</div>}
        {error && <div className="error" role="alert">{error}</div>}
        {!session ? <div className="welcome"><div className="welcome-symbol">☾</div><h3>从一句“你好”开始。</h3><p>选择一种相处方式，记忆默认需要你确认。<br/>接入真实 API 后，可体验并评估模型的多轮回应。</p>
          <div className="mode-options"><button className={mode === 'friend' ? 'selected' : ''} onClick={() => setMode('friend')}>◌ 朋友陪伴<small>轻松、平等、认真倾听</small></button><button className={mode === 'gentle_romance' ? 'selected' : ''} onClick={() => setMode('gentle_romance')}>♡ 温柔关系<small>成年人、非露骨、可随时停止</small></button></div>
          <label className="adult-check"><input type="checkbox" checked={adult} onChange={e => setAdult(e.target.checked)}/> 我已满 18 岁，了解这是 AI 角色与本地演示。</label>
          <button className="primary" disabled={!adult || busy || !status} onClick={start}>开启对话 <span>↗</span></button>
        </div> : <>
          <div className="messages" aria-live="polite">
            {session.messages.length === 0 && <div className="empty-chat"><Portrait small/><p>你好，我是 Nova。<br/>你愿意说说今天最在意的一件事吗？</p></div>}
            {session.messages.map((m, i) => <div key={i} className={`message ${m.role}`}><span className="speaker">{m.role === 'assistant' ? 'NOVA' : 'YOU'}</span><div className="bubble">{m.content}</div></div>)}
            {busy && <div className="typing" role="status"><span/><span/><span/>正在处理这一轮…</div>}
          </div>
          <div className="composer-area"><div className="starters">{['今天有点压力', '记住：我喜欢海边散步', '你还记得我吗？', '看看会话统计'].map(x => <button disabled={busy} key={x} onClick={() => send(x)}>{x}</button>)}</div>
            <form onSubmit={e => {e.preventDefault(); void send()}}><textarea aria-label="消息" placeholder="慢慢说，我在听…" value={draft} maxLength={2000} onChange={e => setDraft(e.target.value)} onKeyDown={e => {if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {e.preventDefault(); void send()}}}/><button type="submit" aria-label="发送" disabled={busy || !draft.trim()}>↑</button></form>
            <p className="composer-note">Enter 发送 · Shift + Enter 换行 · 内容保存在本地；使用 API 时会发送给你配置的模型服务。</p>
          </div>
        </>}
      </section>

      <aside className="details-panel">
        <div className="panel-tabs"><button className={panel === 'memory' ? 'active' : ''} onClick={() => setPanel('memory')}>记忆手札</button><button className={panel === 'insight' ? 'active' : ''} onClick={() => setPanel('insight')}>会话观察</button></div>
        {panel === 'memory' ? <><div className="section-label">WHAT WE KEEP <span>◇</span></div><h3>你选择留下的事。</h3><p className="muted">模型只能提出建议。<br/>确认后，它才成为可用记忆。<br/>删除记忆不会抹去旧聊天；彻底移除请删除整个会话。</p>
          {!session?.memories.length && <div className="memory-empty">还没有记忆。<br/>可以说“记住：我喜欢海边散步”。</div>}
          {session?.memories.map(m => <article className="memory-card" key={m.id}><span className={`memory-status ${m.status}`}>{m.status === 'pending' ? '等待你确认' : '你已确认'}</span><p>{m.content}</p><div>{m.status === 'pending' && <button disabled={busy} onClick={() => memoryAction(m.id, 'approve')}>确认记住</button>}<button disabled={busy} className="text-button" onClick={() => memoryAction(m.id, 'delete')}>{m.status === 'pending' ? '不保存' : '删除'}</button></div></article>)}
          {session && <form className="memory-form" onSubmit={e => {e.preventDefault(); void addMemory()}}><input maxLength={300} aria-label="手动添加记忆" placeholder="写一条你愿意保存的记忆" value={memoryDraft} onChange={e => setMemoryDraft(e.target.value)}/><button disabled={busy || !memoryDraft.trim()}>确认并保存 ↗</button></form>}
        </> : <><div className="section-label">LOCAL INSIGHTS <span>↗</span></div><h3>把流程看清楚。</h3><p className="muted">只聚合当前会话，不作情绪诊断。</p><div className="metrics"><div><span>已完成对话</span><strong>{session?.insights.turn_count || 0}<small> 轮</small></strong></div><div><span>服务端中位耗时</span><strong>{session?.insights.median_latency_ms ?? '—'}<small> ms</small></strong></div></div><p className="micro">模拟模型耗时不能代表真实 LLM 速度。</p><div className="mood-bars">{Object.entries(session?.insights.emotion_counts || {}).map(([key, value]) => <div key={key}><span>{moodNames[key] || key}</span><i style={{width: `${Math.max(6, value / (session?.insights.turn_count || 1) * 100)}%`}}/><b>{value}</b></div>)}</div></>}
        <details className="trace"><summary>查看最近一轮的工具轨迹 <span>⌄</span></summary>{lastRun ? <><p className="micro">仅展示可观察动作，不记录私有推理。</p>{lastRun.trace.map((x, i) => <div key={i}><span>{String(i + 1).padStart(2, '0')}</span><code>{x.name}</code><b>{x.status}</b></div>)}</> : <p className="micro">完成一轮对话后显示。</p>}</details>
        {session && <div className="data-actions"><button disabled={busy} onClick={() => clear(false)}>清空对话，保留已确认记忆</button><button disabled={busy} onClick={() => clear(true)}>删除当前会话的全部数据</button></div>}
        <div className="lab-note"><span>FRAMEWORK FIRST</span><p>真实模型评测待 API 接入后完成。<br/>人格一致性 · 记忆正确性 · 情绪回应</p></div>
      </aside>
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
