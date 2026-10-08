import React, { useEffect, useId, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, clearConnection, getConnection, getSessionKey, setConnection } from './api'
import { AppInstall, registerAppShell } from './AppInstall'
import './style.css'

type Memory = {id: string; content: string; status: 'pending' | 'approved'}
type Message = {role: 'user' | 'assistant'; content: string; emotion: string}
type Insight = {turn_count: number; median_latency_ms: number | null; emotion_counts: Record<string, number>}
type Session = {id: string; mode: string; character_id: string; character_name: string; character_revision: number; character_greeting: string; messages: Message[]; memories: Memory[]; insights: Insight}
type SessionSummary = {id: string; character_name: string; mode: string; created: string; turn_count: number; last_active: string}
type Character = {id: string; name: string; tagline: string; description: string; greeting: string; accent_color: string; avatar_style: string; revision: number}
type Status = {provider: string; configured: boolean; model: string | null}
type Trace = {type: string; name: string; status: string; step?: number}
type Run = {reply: string; provider: string; trace: Trace[]; latency_ms: number; emotion: string}
type Tab = 'characters' | 'chat' | 'memory' | 'me'

const fallbackCharacter: Character = {id: 'nova', name: 'Nova', tagline: '陪你停靠片刻', description: '先听你说，再一起找一个小小的下一步。', greeting: '你好，我是 Nova。你愿意说说今天最在意的一件事吗？', accent_color: '#b9d8c7', avatar_style: 'nova', revision: 1}
const moodNames: Record<string, string> = {calm: '平静', bright: '轻快', low: '低落', overwhelmed: '压力'}
const modeNames: Record<string, string> = {friend: '朋友陪伴', gentle_romance: '温柔关系'}
const tabItems: {id: Tab; icon: string; label: string}[] = [{id: 'characters', icon: '✦', label: '角色'}, {id: 'chat', icon: '◌', label: '聊天'}, {id: 'memory', icon: '◇', label: '记忆'}, {id: 'me', icon: '☷', label: '我的'}]

function readKnownSessions(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(getSessionKey('harbor-sessions')) || '[]')
    const ids = Array.isArray(stored) ? stored.filter((id): id is string => typeof id === 'string' && /^[a-f0-9-]{36}$/i.test(id)) : []
    const active = localStorage.getItem(getSessionKey('harbor-session'))
    if (active && /^[a-f0-9-]{36}$/i.test(active)) ids.unshift(active)
    return [...new Set(ids)].slice(0, 20)
  } catch {return []}
}

function persistKnownSessions(ids: string[]) {
  const bounded = [...new Set(ids)].slice(0, 20)
  localStorage.setItem(getSessionKey('harbor-sessions'), JSON.stringify(bounded))
  return bounded
}

function shortDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '本设备会话' : date.toLocaleString('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'})
}

function Portrait({character = fallbackCharacter, mood = 'calm', small = false}: {character?: Character; mood?: string; small?: boolean}) {
  const gradientId = `hair-${useId().replace(/:/g, '')}`
  const variant = ({nova: 0, sage: 2, ember: 1} as Record<string, number>)[character.avatar_style] ?? 0
  const palettes = [{hair: '#253f5a', shadow: '#10283f', coat: '#89b7ac', pin: '#f5d29a'}, {hair: '#574451', shadow: '#362c43', coat: '#b49fae', pin: '#f2c9c1'}, {hair: '#465044', shadow: '#2a352d', coat: '#b9b088', pin: '#d8ddb1'}]
  const palette = palettes[variant]
  return <div className={`portrait ${small ? 'small' : ''} portrait-${variant}`} data-mood={mood}>
    <svg viewBox="0 0 280 320" role="img" aria-label={`${character.name} 的原创二维角色头像`}>
      <defs><linearGradient id={gradientId} x2="1" y2="1"><stop stopColor={palette.hair}/><stop offset="1" stopColor={palette.shadow}/></linearGradient></defs>
      <circle cx="140" cy="148" r="118" fill={character.accent_color} opacity=".15"/>
      <path d="M64 259 Q46 86 107 59 Q179 23 216 108 L219 260Z" fill={`url(#${gradientId})`}/>
      <path d="M51 320Q49 254 116 246L163 246Q227 253 234 320" fill={palette.coat}/>
      <path d="M119 220L118 262Q140 286 164 261L161 220" fill="#edba9e"/>
      <ellipse cx="141" cy="162" rx="66" ry="82" fill="#f7ceb1"/>
      <path d="M74 156Q65 64 145 67Q208 67 212 136Q181 118 164 84Q146 123 74 156" fill={palette.hair}/>
      <path d="M102 159Q112 153 122 159M160 159Q170 153 180 159" stroke="#35495a" strokeWidth="3" fill="none" strokeLinecap="round"/>
      <ellipse className="eye" cx="113" cy="173" rx="5" ry="7" fill="#344e51"/><ellipse className="eye" cx="170" cy="173" rx="5" ry="7" fill="#344e51"/>
      <ellipse cx="98" cy="193" rx="12" ry="5" fill="#df938b" opacity=".4"/><ellipse cx="184" cy="193" rx="12" ry="5" fill="#df938b" opacity=".4"/>
      <path d="M131 211Q142 220 155 210" stroke="#b9796d" strokeWidth="3" fill="none" strokeLinecap="round"/>
      <path d="M207 126L212 186Q205 236 180 262L194 186Z" fill={palette.hair}/>
      <path d="M85 242L107 263L97 309M180 259L192 290" stroke="#d1ded1" strokeWidth="3" fill="none"/>
      <circle cx="207" cy="121" r="7" fill={palette.pin}/><path d="M195 121H219M207 109V133" stroke={palette.pin} strokeWidth="2"/>
    </svg>
    {!small && <><span className="portrait-orbit orbit-one">✧</span><span className="portrait-orbit orbit-two">·</span></>}
  </div>
}

export function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [characters, setCharacters] = useState<Character[]>([])
  const [catalogState, setCatalogState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [selectedCharacterId, setSelectedCharacterId] = useState('nova')
  const [session, setSession] = useState<Session | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [adult, setAdult] = useState(false)
  const [mode, setMode] = useState('friend')
  const [tab, setTab] = useState<Tab>('characters')
  const [desktopDetail, setDesktopDetail] = useState<'memory' | 'me'>('memory')
  const [draft, setDraft] = useState('')
  const [pendingText, setPendingText] = useState('')
  const [memoryDraft, setMemoryDraft] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const [lastRun, setLastRun] = useState<Run | null>(null)
  const [keyboardOpen, setKeyboardOpen] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [connection, setConnectionDraft] = useState(getConnection)
  const [connectionNotice, setConnectionNotice] = useState('')
  const retry = useRef<{sid: string; text: string; id: string} | null>(null)
  const knownIds = useRef<string[]>(readKnownSessions())
  const messagesEnd = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const composing = useRef(false)
  const connectionEpoch = useRef(0)
  const listRequest = useRef(0)

  async function refreshSessions(ids = knownIds.current) {
    const epoch = connectionEpoch.current
    const request = ++listRequest.current
    if (!ids.length) {setSessions([]); return}
    const response = await api<{items: SessionSummary[]}>(`/sessions?ids=${encodeURIComponent(ids.join(','))}`)
    if (epoch !== connectionEpoch.current || request !== listRequest.current) return
    setSessions(response.items)
    knownIds.current = persistKnownSessions(response.items.map(item => item.id))
  }

  useEffect(() => {
    let cancelled = false
    const epoch = connectionEpoch.current
    const current = () => !cancelled && epoch === connectionEpoch.current
    api<Status>('/status').then(value => {if (current()) setStatus(value)}).catch(e => {if (current()) setError((e as Error).message)})
    api<{items: Character[]}>('/characters').then(value => {if (current()) {setCharacters(value.items); setCatalogState('ready')}}).catch(e => {if (current()) {setCatalogState('error'); setError((e as Error).message)}})
    const sid = localStorage.getItem(getSessionKey('harbor-session'))
    const restore = sid ? api<Session>(`/sessions/${sid}`).then(value => {
      if (current()) {setSession(value); setSelectedCharacterId(value.character_id || 'nova'); setMode(value.mode); setTab('chat')}
    }).catch(e => {if (current()) setError(`上次会话暂时未能恢复：${(e as Error).message}`)}) : Promise.resolve()
    restore.finally(() => {if (current()) setRestoring(false)})
    refreshSessions().catch(() => {})
    return () => {cancelled = true}
  }, [])

  useEffect(() => {
    const viewport = window.visualViewport
    const update = () => {
      document.documentElement.style.setProperty('--app-height', `${viewport?.height || window.innerHeight}px`)
      setKeyboardOpen(Boolean(viewport && window.innerHeight - viewport.height > 140))
    }
    update(); viewport?.addEventListener('resize', update); window.addEventListener('resize', update)
    return () => {viewport?.removeEventListener('resize', update); window.removeEventListener('resize', update)}
  }, [])

  useEffect(() => {
    const frame = requestAnimationFrame(() => messagesEnd.current?.scrollIntoView({block: 'end', behavior: 'auto'}))
    return () => cancelAnimationFrame(frame)
  }, [session?.id, session?.messages.length, sending, tab])

  useEffect(() => {
    if (input.current) {input.current.style.height = 'auto'; input.current.style.height = `${Math.min(112, input.current.scrollHeight)}px`}
  }, [draft])

  useEffect(() => {
    if (characters.length && !characters.some(item => item.id === selectedCharacterId)) setSelectedCharacterId(characters[0].id)
  }, [characters, selectedCharacterId])

  async function refresh(sid: string) {setSession(await api<Session>(`/sessions/${sid}`))}

  async function start() {
    if (!adult || busy || !characters.some(item => item.id === selectedCharacterId)) return
    if (knownIds.current.length >= 20) {setError('本设备已保存 20 个会话入口。请先在“我的”删除不再需要的会话，再开启新对话。'); return}
    setBusy(true); setError('')
    try {
      const created = await api<{id: string}>('/sessions', 'POST', {adult_confirmed: adult, mode, character_id: selectedCharacterId})
      knownIds.current = persistKnownSessions([created.id, ...knownIds.current])
      localStorage.setItem(getSessionKey('harbor-session'), created.id)
      await refresh(created.id)
      setDraft(''); setMemoryDraft(''); setLastRun(null); retry.current = null; setTab('chat')
      refreshSessions().catch(() => {})
    } catch (e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function restoreSession(sid: string) {
    if (busy) return
    setBusy(true); setError('')
    try {
      const restored = await api<Session>(`/sessions/${sid}`)
      setSession(restored); setSelectedCharacterId(restored.character_id || 'nova'); setMode(restored.mode)
      localStorage.setItem(getSessionKey('harbor-session'), sid)
      setDraft(''); setMemoryDraft(''); setLastRun(null); retry.current = null; setTab('chat')
    } catch (e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function send(text = draft) {
    if (!session || !text.trim() || busy) return
    const sid = session.id
    setBusy(true); setSending(true); setError(''); setDraft(''); setPendingText(text)
    const request = retry.current?.sid === sid && retry.current.text === text ? retry.current : {sid, text, id: crypto.randomUUID()}
    retry.current = request
    try {
      const result = await api<Run>(`/sessions/${sid}/chat`, 'POST', {message: text, request_id: request.id})
      setLastRun(result); await refresh(sid); retry.current = null
      refreshSessions().catch(() => {})
    } catch (e) {setError((e as Error).message); setDraft(text)} finally {setBusy(false); setSending(false); setPendingText('')}
  }

  async function memoryAction(mid: string, action: 'approve' | 'delete') {
    if (!session || busy) return
    setBusy(true); setError('')
    try {await api(`/sessions/${session.id}/memories/${mid}/${action}`, 'POST'); await refresh(session.id)} catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function addMemory() {
    if (!session || !memoryDraft.trim() || busy) return
    setBusy(true); setError('')
    try {await api(`/sessions/${session.id}/memories`, 'POST', {content: memoryDraft.trim()}); setMemoryDraft(''); await refresh(session.id)} catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function clear(all: boolean) {
    if (!session || busy || !confirm(all ? '删除当前会话、记忆、运行记录和人工评审？此操作不能撤销，其他会话保留。' : '清空当前对话、待确认记忆及相关人工评审？已确认记忆将保留。')) return
    const sid = session.id
    setBusy(true); setError('')
    try {
      await api(`/sessions/${sid}${all ? '' : '/history'}`, 'DELETE'); setLastRun(null); retry.current = null; setDraft(''); setMemoryDraft('')
      if (all) {
        knownIds.current = persistKnownSessions(knownIds.current.filter(id => id !== sid))
        localStorage.removeItem(getSessionKey('harbor-session')); setSession(null); setTab('characters')
      } else await refresh(sid)
      refreshSessions().catch(() => {})
    } catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function reloadService() {
    const epoch = connectionEpoch.current
    setError(''); setCatalogState('loading')
    try {
      const [service, catalog] = await Promise.all([api<Status>('/status'), api<{items: Character[]}>('/characters')])
      if (epoch !== connectionEpoch.current) return
      setStatus(service); setCharacters(catalog.items); setCatalogState('ready'); await refreshSessions()
    } catch(e) {if (epoch === connectionEpoch.current) {setCatalogState('error'); setError((e as Error).message)}}
  }

  async function saveConnection(reset = false) {
    if (busy) return
    setConnectionNotice(''); setError('')
    try {
      if (reset) clearConnection(); else setConnection(connection)
      setBusy(true); connectionEpoch.current += 1
      setConnectionDraft(getConnection())
      setSession(null); setSessions([]); setLastRun(null); retry.current = null
      setStatus(null); setCharacters([]); setCatalogState('loading'); setDraft(''); setMemoryDraft(''); setRestoring(false)
      knownIds.current = readKnownSessions()
      setConnectionNotice('已更新连接。不同后端的会话入口独立保留；会话不会跨设备自动同步。访问码只在当前浏览器会话保存。')
      await reloadService()
      const sid = localStorage.getItem(getSessionKey('harbor-session'))
      if (sid) {
        const restored = await api<Session>(`/sessions/${sid}`)
        setSession(restored); setSelectedCharacterId(restored.character_id || 'nova'); setMode(restored.mode)
      }
    } catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  function goToTab(next: Tab) {
    setTab(next)
    if (next === 'memory' || next === 'me') setDesktopDetail(next)
  }

  const selectedCharacter = characters.find(item => item.id === selectedCharacterId) || fallbackCharacter
  const currentCharacter = {...(characters.find(item => item.id === session?.character_id) || fallbackCharacter), name: session?.character_name || 'Nova'}
  const characterName = session?.character_name || currentCharacter.name
  const mock = status?.provider === 'mock'
  const pendingCount = session?.memories.filter(memory => memory.status === 'pending').length || 0

  return <div className={`app-shell tab-${tab} detail-${desktopDetail} ${keyboardOpen ? 'keyboard-open' : ''}`}>
    <header className="topbar">
      <button className="brand" onClick={() => goToTab('characters')} aria-label="港湾，查看角色"><span className="brand-icon">◒</span><span><strong>harbor<span className="brand-dot">.</span></strong><small>港湾 · AI 陪伴</small></span></button>
      <div className="topbar-right"><span className={`provider-pill ${mock ? 'mock' : ''}`} title={mock ? '模拟模型只演示流程' : '实际可用性以聊天请求结果为准'}><i/>{status ? mock ? '模拟演示' : status.configured ? 'API 已配置' : '模型待配置' : '连接服务…'}</span><button className="desktop-account icon-button" aria-label="我的会话与设置" onClick={() => goToTab('me')}>☷</button></div>
    </header>
    {error && <div className="global-error" role="alert"><span>{error}</span>{retry.current && session?.id === retry.current.sid && <button disabled={busy} onClick={() => send(retry.current!.text)}>重试发送</button>}<button className="error-dismiss" onClick={() => setError('')} aria-label="关闭错误提示">×</button></div>}
    <main className="layout">
      <section className="character-panel page-panel" aria-label="角色选择">
        <div className="page-heading"><p className="eyebrow">YOUR LITTLE HARBOR</p><h1>找到你的<br/>停靠点<span>。</span></h1><p className="muted">原创 AI 角色。由你决定相处的方式。</p></div>
        <div className="character-hero"><span className="hero-constellation">✧</span><Portrait character={selectedCharacter}/><div className="hero-name"><h2>{selectedCharacter.name}<span>✦</span></h2><span className="tag">AI 角色 · v{selectedCharacter.revision}</span></div><p className="character-tagline">{selectedCharacter.tagline}</p><p className="character-copy">{selectedCharacter.description}</p></div>
        <div className="section-title"><h3>选择角色</h3><span>原创二维形象</span></div>
        <div className="character-options" aria-label="可用角色">
          {!characters.length && <div className="catalog-empty"><p>{catalogState === 'ready' ? '当前暂无公开角色，请在后台发布角色。' : catalogState === 'error' ? '暂未取得角色，请检查连接设置。' : '正在获取可用角色…'}</p><button className="text-button" onClick={reloadService}>重新连接</button></div>}
          {characters.map(character => <button disabled={busy} key={character.id} className={`character-card ${selectedCharacterId === character.id ? 'selected' : ''}`} onClick={() => setSelectedCharacterId(character.id)} aria-pressed={selectedCharacterId === character.id}><Portrait character={character} small/><strong>{character.name}</strong><span>{character.tagline}</span>{selectedCharacterId === character.id && <b className="selection-check">✓</b>}</button>)}
        </div>
        <div className="section-title mode-title"><h3>相处方式</h3><span>随时可开启新会话</span></div>
        <div className="mode-options"><button disabled={busy} className={mode === 'friend' ? 'selected' : ''} onClick={() => setMode('friend')} aria-pressed={mode === 'friend'}><span>◌ 朋友陪伴</span><small>轻松、平等、认真倾听</small></button><button disabled={busy} className={mode === 'gentle_romance' ? 'selected' : ''} onClick={() => setMode('gentle_romance')} aria-pressed={mode === 'gentle_romance'}><span>♡ 温柔关系</span><small>成年人，温和、非露骨</small></button></div>
        <label className="adult-check"><input type="checkbox" checked={adult} disabled={busy} onChange={e => setAdult(e.target.checked)}/><span>我已满 18 岁，了解对方是 AI，记忆由我确认，服务不提供心理诊断。</span></label>
        <button className="primary start-chat" disabled={!adult || busy || !status || !characters.length} onClick={start}>{busy && !sending ? '正在处理…' : `与 ${selectedCharacter.name} 开启${session ? '新' : ''}对话`}<span>↗</span></button>
        {session && <p className="micro">新对话独立保存。已有会话可在“我的”中恢复。</p>}
        <p className="footer-note">陪伴可以暂停，记忆可以删除。<br/>这是一款开发中的成年人 AI 陪伴原型。</p>
      </section>

      <section className="conversation-panel page-panel" aria-label="对话">
        <div className="conversation-header"><div className="chat-avatar"><Portrait character={currentCharacter} small/></div><div className="conversation-title"><h2>{session ? characterName : '从一句你好开始'}</h2><p>{session ? `${modeNames[session.mode] || session.mode} · AI 角色` : '为自己留一小段安静的时间'}</p></div><button className="icon-button session-shortcut" aria-label="查看本设备会话" onClick={() => goToTab('me')}>☷</button></div>
        {mock && <div className="demo-notice"><span>模拟模式</span>固定回复与工具流程演示，真实聊天质量待 API 接入后评估。</div>}
        {restoring && !session ? <div className="welcome"><div className="welcome-symbol">◌</div><h3>正在恢复你的停靠点…</h3><p>会话仍保存在当前服务端。</p></div> : !session ? <div className="welcome"><div className="welcome-symbol">☾</div><h3>今天，不必着急。</h3><p>选一个角色，留下一句话。<br/>你决定话题，也决定哪些事值得被记住。</p><button className="primary" onClick={() => goToTab('characters')}>选择角色 <span>↗</span></button><div className="welcome-features"><span>◇ 记忆须确认</span><span>◌ 会话独立保存</span><span>✧ 明确 AI 身份</span></div></div> : <>
          <div className="messages" aria-live="polite" aria-busy={sending}>
            {session.messages.length === 0 && <div className="empty-chat"><Portrait character={currentCharacter} small/><p>{session.character_greeting || currentCharacter.greeting}</p><span>试着说说今天发生的一件小事。</span></div>}
            {session.messages.map((message, index) => <div key={index} className={`message ${message.role}`}><span className="speaker">{message.role === 'assistant' ? characterName : '我'}</span><div className="bubble">{message.content}</div></div>)}
            {pendingText && <div className="message user pending-message"><span className="speaker">我 · 发送中</span><div className="bubble">{pendingText}</div></div>}
            {sending && <div className="typing" role="status"><span/><span/><span/><em>正在回应这一轮…</em></div>}
            <div ref={messagesEnd} className="messages-end"/>
          </div>
          <div className="composer-area"><div className="starters">{['今天有点压力', '记住：我喜欢海边散步', '你还记得我吗？'].map(text => <button disabled={busy} key={text} onClick={() => send(text)}>{text}</button>)}</div>
            <form onSubmit={e => {e.preventDefault(); if (!composing.current) void send()}}><textarea ref={input} aria-label="消息" placeholder="慢慢说，我在听…" rows={1} value={draft} maxLength={2000} disabled={busy} onChange={e => setDraft(e.target.value)} onCompositionStart={() => {composing.current = true}} onCompositionEnd={() => {composing.current = false}} onKeyDown={e => {if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && !composing.current && e.keyCode !== 229) {e.preventDefault(); void send()}}}/><button type="submit" aria-label="发送消息" disabled={busy || !draft.trim()}>↑</button></form>
            <p className="composer-note"><span>你掌握对话的节奏。</span><span className="desktop-composer-hint">Enter 发送 · Shift + Enter 换行</span></p>
          </div>
        </>}
      </section>

      <aside className="details-column">
        <div className="panel-tabs"><button className={desktopDetail === 'memory' ? 'active' : ''} onClick={() => goToTab('memory')}>记忆手札{pendingCount > 0 && <span className="count-badge">{pendingCount}</span>}</button><button className={desktopDetail === 'me' ? 'active' : ''} onClick={() => goToTab('me')}>我的会话</button></div>
        <section className="memory-panel page-panel" aria-label="记忆管理">
          <div className="page-heading"><p className="eyebrow">ONLY WHAT YOU CHOOSE</p><h2>记忆手札<span>◇</span></h2><p className="muted">留下一点点，让下次更好地认识你。</p></div>
          {session ? <><div className="session-context"><span>当前会话</span><strong>{characterName}</strong><small>{modeNames[session.mode]} · v{session.character_revision || 1}</small></div><div className="memory-explainer"><span>◇</span><p>AI 可以提出记忆建议。确认后才进入长期记忆检索；近期聊天仍作为上下文。不同会话不共用记忆。</p></div>
            {!session.memories.length && <div className="memory-empty"><span>▱</span><h3>手札还是空白的</h3><p>在聊天中说“记住：我喜欢海边散步”，<br/>或者在下方写一条你愿意保存的事。</p></div>}
            <div className="memory-list">{session.memories.map(memory => <article className="memory-card" key={memory.id}><span className={`memory-status ${memory.status}`}><i/>{memory.status === 'pending' ? '等待你确认' : '已确认的记忆'}</span><p>{memory.content}</p><div>{memory.status === 'pending' && <button disabled={busy} onClick={() => memoryAction(memory.id, 'approve')}>✓ 确认记住</button>}<button disabled={busy} className="text-button" onClick={() => memoryAction(memory.id, 'delete')}>{memory.status === 'pending' ? '不保存' : '删除记忆'}</button></div></article>)}</div>
            <form className="memory-form" onSubmit={e => {e.preventDefault(); void addMemory()}}><label htmlFor="manual-memory">我想主动记下</label><textarea id="manual-memory" maxLength={300} rows={3} disabled={busy} placeholder="例如：比起建议，我有时更需要被认真听见。" value={memoryDraft} onChange={e => setMemoryDraft(e.target.value)}/><div><span>{memoryDraft.length}/300</span><button disabled={busy || !memoryDraft.trim()}>确认并保存 ↗</button></div></form>
            <p className="micro">删除一条记忆不会抹去旧聊天内容。如需彻底移除，请在“我的”中删除当前会话。</p>
          </> : <div className="memory-empty"><span>◇</span><h3>先开启一段对话</h3><p>记忆属于具体会话，只有你确认后才会生效。</p><button className="secondary" onClick={() => goToTab('characters')}>去选择角色 ↗</button></div>}
        </section>

        <section className="account-panel page-panel" aria-label="我的会话与设置">
          <div className="page-heading"><p className="eyebrow">YOUR SPACE, YOUR PACE</p><h2>我的停靠点<span>◒</span></h2><p className="muted">管理会话、数据与应用设置。</p></div>
          <div className="section-title"><h3>本设备会话</h3><button className="text-button" disabled={busy} onClick={() => goToTab('characters')}>＋ 新对话</button></div>
          <p className="micro session-list-note">这里最多保存 20 个会话入口。聊天数据在服务端，换浏览器不会自动同步入口；丢失入口后无法从这里恢复。</p>
          <div className="session-list">{sessions.length ? sessions.map(item => <button key={item.id} disabled={busy} className={`session-card ${item.id === session?.id ? 'current' : ''}`} onClick={() => restoreSession(item.id)}><span className="session-card-icon">◌</span><span><strong>{item.character_name || 'AI 角色'}{item.id === session?.id && <i>当前</i>}</strong><small>{modeNames[item.mode] || item.mode} · {item.turn_count} 轮</small><small>{shortDate(item.last_active || item.created)}</small></span><b>↗</b></button>) : <div className="small-empty">还没有可恢复的会话。<br/>在“角色”中开启新的停靠点。</div>}</div>
          <div className="settings-block"><div className="section-title"><h3>应用与连接</h3><button className="text-button" disabled={busy} onClick={reloadService}>刷新</button></div><div className="setting-row"><span>当前模型</span><strong>{status ? mock ? '模拟流程' : status.model || '待配置' : '尚未连接'}</strong></div><div className="setting-row"><span>数据范围</span><strong>当前服务端 / 当前会话</strong></div><AppInstall/><a className="admin-entry" href="?view=admin"><span>⚙ 管理后台<small>角色配置、服务设置与运行概览</small></span><b>↗</b></a></div>
          <details className="connection-card"><summary>手机 / 远程后端连接 <span>⌄</span></summary><p className="micro">填写部署方提供的 HTTPS API 地址及演示访问码。访问码不是模型 API 密钥；不要把模型密钥放在这里。远程服务需先完成受控部署。</p><form className="connection-form" onSubmit={e => {e.preventDefault(); void saveConnection()}}><label htmlFor="connection-url">后端地址</label><input id="connection-url" type="url" autoComplete="url" placeholder="https://your-api.example.com" value={connection.baseUrl} onChange={e => setConnectionDraft({...connection, baseUrl: e.target.value})}/><label htmlFor="connection-code">演示访问码</label><input id="connection-code" type="password" autoComplete="off" placeholder="由部署方提供，按需填写" value={connection.accessToken} onChange={e => setConnectionDraft({...connection, accessToken: e.target.value})}/><div><button type="submit" disabled={busy}>保存连接</button><button className="text-button" type="button" disabled={busy} onClick={() => saveConnection(true)}>恢复默认</button></div></form>{connectionNotice && <p className="connection-notice" role="status">{connectionNotice}</p>}<p className="micro">网页版可留空，使用当前站点的后端。原生手机 App 需要可访问的 HTTPS 后端。会话入口不会跨设备自动同步。</p></details>
          <details className="privacy-card"><summary>隐私与使用边界 <span>⌄</span></summary><p>对话和已确认记忆保存在当前服务端的数据库。浏览器保存会话入口及当前连接设置，不保存模型 API 密钥。会话入口相当于当前会话的访问凭据，请勿分享。</p><p>启用真实模型时，对话和必要上下文会发送至你配置的模型服务。请勿填写证件、账户密码或其他不愿分享的隐私信息。</p><p>这里的角色始终是 AI。本应用不提供心理诊断、治疗或紧急服务。你可以随时暂停、清空历史或删除整个会话。</p></details>
          {session && <><details className="insights-card"><summary>当前会话观察 <span>⌄</span></summary><p className="micro">以下是当前会话的流程统计。关键词标签只是初步规则，不是情绪识别或医学结论。</p><div className="metrics"><div><span>已完成</span><strong>{session.insights.turn_count}<small> 轮</small></strong></div><div><span>服务端中位耗时</span><strong>{session.insights.median_latency_ms ?? '—'}<small> ms</small></strong></div></div><p className="micro">模拟模型耗时不能代表真实 LLM 的回复速度。</p><div className="mood-bars">{Object.entries(session.insights.emotion_counts).map(([key, value]) => <div key={key}><span>{moodNames[key] || key}</span><div><i style={{width: `${value / Math.max(session.insights.turn_count, 1) * 100}%`}}/></div><b>{value}</b></div>)}</div></details>
            <details className="trace"><summary>最近一轮的工具轨迹 <span>⌄</span></summary>{lastRun ? <><p className="micro">只展示可观察动作，不显示模型私有推理。切换会话后此面板重置。</p>{lastRun.trace.map((item, index) => <div key={index}><span>{String(index + 1).padStart(2, '0')}</span><code>{item.name}</code><b>{item.status}</b></div>)}</> : <p className="micro">在当前会话完成一轮对话后显示。</p>}</details>
            <div className="data-actions"><h3>当前会话数据</h3><button disabled={busy} onClick={() => clear(false)}><span>清空聊天历史<small>保留已确认记忆，清除建议与相关评审</small></span><b>↗</b></button><button className="danger" disabled={busy} onClick={() => clear(true)}><span>删除整个会话<small>移除聊天、记忆、运行记录和评审，不可撤销</small></span><b>×</b></button></div>
          </>}
          <div className="lab-note"><span>HARBOR COMPANION</span><p>开发中的 AI 陪伴应用。<br/>真实模型的人设、记忆与回应质量仍需独立评估。</p></div>
        </section>
      </aside>
    </main>
    <nav className="mobile-nav" aria-label="应用主导航">{tabItems.map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => goToTab(item.id)} aria-current={tab === item.id ? 'page' : undefined}><span>{item.icon}{item.id === 'memory' && pendingCount > 0 && <i>{pendingCount}</i>}</span><small>{item.label}</small></button>)}</nav>
  </div>
}

const AdminApp = React.lazy(() => import('./admin/AdminApp'))

function Root() {
  const [management, setManagement] = useState(() => window.location.pathname === '/admin'
    || new URLSearchParams(window.location.search).get('view') === 'admin')
  function leaveManagement() {
    window.history.replaceState(null, '', '/')
    setManagement(false)
  }
  return management
    ? <React.Suspense fallback={<div className="welcome" role="status">正在打开管理后台…</div>}><AdminApp onExit={leaveManagement}/></React.Suspense>
    : <App/>
}

void registerAppShell()
createRoot(document.getElementById('root')!).render(<React.StrictMode><Root/></React.StrictMode>)
