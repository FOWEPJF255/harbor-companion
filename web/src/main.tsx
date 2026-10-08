import React, { useEffect, useId, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, ApiError, clearConnection, getConnection, getSessionKey, setConnection } from './api'
import { AppInstall, isNativeApp, registerAppShell } from './AppInstall'
import { analysisQuestions, readLanguage, starters, storeLanguage, translator, type Language, type TextKey } from './i18n'
import './style.css'

type Memory = {id: string; content: string; status: 'pending' | 'approved'}
type Message = {role: 'user' | 'assistant'; content: string; emotion: string}
type Insight = {turn_count: number; median_latency_ms: number | null; emotion_counts: Record<string, number>}
type Session = {id: string; mode: string; character_id: string; character_name: string; character_revision: number; character_greeting: string; messages: Message[]; memories: Memory[]; insights: Insight}
type SessionSummary = {id: string; character_name: string; mode: string; created: string; turn_count: number; last_active: string}
type Character = {id: string; name: string; tagline: string; description: string; greeting: string; accent_color: string; avatar_style: string; revision: number}
type Status = {provider: string; configured: boolean; model: string | null}
type Trace = {type?: string; name?: string; status?: string; step?: number; input?: unknown; observation?: unknown; [key: string]: unknown}
type Run = {reply: string; provider: string; trace: Trace[]; latency_ms: number; emotion: string}
type Analysis = {answer: string; plan: unknown; result: unknown; trace: Trace[]; source: unknown; scope: unknown}
type Tab = 'characters' | 'chat' | 'memory' | 'me' | 'data'

const fallbackCharacter: Character = {id: 'nova', name: 'Nova', tagline: '陪你停靠片刻', description: '先听你说，再一起找一个小小的下一步。', greeting: '你好，我是 Nova。你愿意说说今天最在意的一件事吗？', accent_color: '#b9d8c7', avatar_style: 'nova', revision: 1}
const tabItems: {id: Tab; icon: string; label: TextKey}[] = [{id: 'characters', icon: '✦', label: 'characters'}, {id: 'chat', icon: '◌', label: 'chat'}, {id: 'memory', icon: '◇', label: 'memory'}, {id: 'me', icon: '☷', label: 'me'}]

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

function shortDate(value: string, language: Language) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? translator(language)('savedOnDevice') : date.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})
}

function JsonValue({value}: {value: unknown}) {
  return <pre className="observable-json">{typeof value === 'string' ? value : JSON.stringify(value ?? null, null, 2)}</pre>
}

function TraceList({items, language}: {items: Trace[]; language: Language}) {
  const t = translator(language)
  return <div className="observable-trace">{items.map((item, index) => <details className="trace-step" key={index}><summary><span>{String(index + 1).padStart(2, '0')}</span><code>{String(item.name || item.operation || item.type || 'step')}</code><b>{item.status || '—'}</b></summary><h4>{t('traceRecord')}</h4><JsonValue value={item}/></details>)}</div>
}

function Portrait({character = fallbackCharacter, mood = 'calm', small = false, language = 'zh'}: {character?: Character; mood?: string; small?: boolean; language?: Language}) {
  const gradientId = `hair-${useId().replace(/:/g, '')}`
  const variant = ({nova: 0, sage: 2, ember: 1} as Record<string, number>)[character.avatar_style] ?? 0
  const palettes = [{hair: '#253f5a', shadow: '#10283f', coat: '#89b7ac', pin: '#f5d29a'}, {hair: '#574451', shadow: '#362c43', coat: '#b49fae', pin: '#f2c9c1'}, {hair: '#465044', shadow: '#2a352d', coat: '#b9b088', pin: '#d8ddb1'}]
  const palette = palettes[variant]
  return <div className={`portrait ${small ? 'small' : ''} portrait-${variant}`} data-mood={mood}>
    <svg viewBox="0 0 280 320" role="img" aria-label={translator(language)('portraitLabel', {name: character.name})}>
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
  const [language, setLanguage] = useState<Language>(readLanguage)
  const t = translator(language)
  const modeNames: Record<string, string> = {friend: t('friend'), gentle_romance: t('romance')}
  const moodNames: Record<string, string> = language === 'en' ? {calm: 'Calm', bright: 'Bright', low: 'Low', overwhelmed: 'Stress'} : {calm: '平静', bright: '轻快', low: '低落', overwhelmed: '压力'}
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
  const [reuseMemories, setReuseMemories] = useState(false)
  const [editingMemory, setEditingMemory] = useState<string | null>(null)
  const [correction, setCorrection] = useState('')
  const [question, setQuestion] = useState('')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const [lastRun, setLastRun] = useState<Run | null>(null)
  const [failedTrace, setFailedTrace] = useState<Trace[]>([])
  const [analysisFailure, setAnalysisFailure] = useState<Trace[]>([])
  const [online, setOnline] = useState(navigator.onLine)
  const [keyboardOpen, setKeyboardOpen] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [connection, setConnectionDraft] = useState(getConnection)
  const [connectionNotice, setConnectionNotice] = useState('')
  const retry = useRef<{sid: string; text: string; id: string; language: Language} | null>(null)
  const knownIds = useRef<string[]>(readKnownSessions())
  const messagesEnd = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const composing = useRef(false)
  const connectionEpoch = useRef(0)
  const listRequest = useRef(0)

  useEffect(() => {storeLanguage(language)}, [language])
  useEffect(() => {
    const sync = () => setOnline(navigator.onLine)
    window.addEventListener('online', sync); window.addEventListener('offline', sync)
    return () => {window.removeEventListener('online', sync); window.removeEventListener('offline', sync)}
  }, [])

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
    }).catch(e => {if (current()) setError(translator(readLanguage())('restoreError', {error: (e as Error).message}))}) : Promise.resolve()
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
    if (knownIds.current.length >= 20) {setError(t('sessionLimit')); return}
    setBusy(true); setError('')
    try {
      const created = await api<{id: string}>('/sessions', 'POST', {adult_confirmed: adult, mode, character_id: selectedCharacterId, language, ...(reuseMemories && session ? {memory_from_session_id: session.id} : {})})
      knownIds.current = persistKnownSessions([created.id, ...knownIds.current])
      localStorage.setItem(getSessionKey('harbor-session'), created.id)
      await refresh(created.id)
      setDraft(''); setMemoryDraft(''); setEditingMemory(null); setReuseMemories(false); setLastRun(null); setFailedTrace([]); retry.current = null; setTab('chat')
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
      setDraft(''); setMemoryDraft(''); setEditingMemory(null); setReuseMemories(false); setLastRun(null); setFailedTrace([]); retry.current = null; setTab('chat')
    } catch (e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function send(text = draft) {
    if (!session || !text.trim() || busy) return
    const sid = session.id
    setBusy(true); setSending(true); setError(''); setDraft(''); setPendingText(text); setLastRun(null); setFailedTrace([])
    const request = retry.current?.sid === sid && retry.current.text === text ? retry.current : {sid, text, id: crypto.randomUUID(), language}
    retry.current = request
    try {
      const result = await api<Run>(`/sessions/${sid}/chat`, 'POST', {message: text, request_id: request.id, language: request.language})
      setLastRun(result); await refresh(sid); retry.current = null
      refreshSessions().catch(() => {})
    } catch (e) {setError((e as Error).message); setDraft(text); if (e instanceof ApiError && e.trace.length) setFailedTrace(e.trace as Trace[])} finally {setBusy(false); setSending(false); setPendingText('')}
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

  async function correctMemory() {
    if (!session || !editingMemory || busy) return
    if (!correction.trim()) {setError(t('memoryEditError')); return}
    setBusy(true); setError('')
    try {
      await api(`/sessions/${session.id}/memories/${editingMemory}`, 'PUT', {content: correction.trim()})
      await refresh(session.id); setEditingMemory(null); setCorrection('')
    } catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }

  async function runAnalysis(text = question) {
    if (busy) return
    if (!text.trim()) {setError(t('questionError')); return}
    const epoch = connectionEpoch.current
    setBusy(true); setAnalyzing(true); setQuestion(text); setError(''); setAnalysis(null); setAnalysisFailure([])
    try {
      const result = await api<Analysis>('/data-agent', 'POST', {question: text.trim()})
      if (epoch === connectionEpoch.current) setAnalysis(result)
    } catch(e) {if (epoch === connectionEpoch.current) {setError((e as Error).message); if (e instanceof ApiError && e.trace.length) setAnalysisFailure(e.trace as Trace[])}} finally {setBusy(false); setAnalyzing(false)}
  }

  async function clear(all: boolean) {
    if (!session || busy || !confirm(t(all ? 'deleteConfirm' : 'clearConfirm'))) return
    const sid = session.id
    setBusy(true); setError('')
    try {
      await api(`/sessions/${sid}${all ? '' : '/history'}`, 'DELETE'); setLastRun(null); setFailedTrace([]); retry.current = null; setDraft(''); setMemoryDraft(''); setEditingMemory(null); setReuseMemories(false)
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
      setEditingMemory(null); setReuseMemories(false); setAnalysis(null); setFailedTrace([]); setAnalysisFailure([])
      setStatus(null); setCharacters([]); setCatalogState('loading'); setDraft(''); setMemoryDraft(''); setRestoring(false)
      knownIds.current = readKnownSessions()
      setConnectionNotice(t('connectionUpdated'))
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

  return <div className={`app-shell tab-${tab} detail-${desktopDetail} language-${language} ${keyboardOpen ? 'keyboard-open' : ''}`}>
    <header className="topbar">
      <button className="brand" onClick={() => goToTab('characters')} aria-label={t('brandHome')}><span className="brand-icon">◒</span><span><strong>harbor<span className="brand-dot">.</span></strong><small>{t('brand')}</small></span></button>
      <div className="topbar-right"><label className="language-control"><span className="sr-only">{t('language')}</span><select aria-label={t('language')} value={language} onChange={event => setLanguage(event.target.value as Language)}><option value="zh">中文</option><option value="en">EN</option></select></label><span className={`provider-pill ${mock ? 'mock' : ''}`} title={t(mock ? 'mockHint' : 'apiHint')}><i/>{status ? mock ? t('mockStatus') : status.configured ? t('apiConfigured') : t('modelPending') : t('connecting')}</span><button className="desktop-account icon-button" aria-label={t('accountLabel')} onClick={() => goToTab('me')}>☷</button></div>
    </header>
    {error && <div className="global-error" role="alert"><span>{error}</span>{retry.current && session?.id === retry.current.sid && <button disabled={busy} onClick={() => send(retry.current!.text)}>{t('retry')}</button>}<button className="error-dismiss" onClick={() => setError('')} aria-label={t('dismiss')}>×</button></div>}
    <main className="layout">
      <section className="character-panel page-panel" aria-label={t('chooseCharacter')}>
        <div className="page-heading"><p className="eyebrow">YOUR LITTLE HARBOR</p><h1>{t('characterTitle')}</h1><p className="muted">{t('characterSubtitle')}</p></div>
        <div className="character-hero"><span className="hero-constellation">✧</span><Portrait character={selectedCharacter} language={language}/><div className="hero-name"><h2>{selectedCharacter.name}<span>✦</span></h2><span className="tag">{t('aiRole')} · v{selectedCharacter.revision}</span></div><p className="character-tagline">{selectedCharacter.tagline}</p><p className="character-copy">{selectedCharacter.description}</p></div>
        {language === 'en' && <p className="original-copy-note">{t('originalCopy')}</p>}
        <div className="section-title"><h3>{t('chooseCharacter')}</h3><span>{t('originalArt')}</span></div>
        <div className="character-options" aria-label={t('chooseCharacter')}>
          {!characters.length && <div className="catalog-empty"><p>{t(catalogState === 'ready' ? 'catalogEmpty' : catalogState === 'error' ? 'catalogError' : 'catalogLoading')}</p><button className="text-button" onClick={reloadService}>{t('reconnect')}</button></div>}
          {characters.map(character => <button disabled={busy} key={character.id} className={`character-card ${selectedCharacterId === character.id ? 'selected' : ''}`} onClick={() => setSelectedCharacterId(character.id)} aria-pressed={selectedCharacterId === character.id}><Portrait character={character} small language={language}/><strong>{character.name}</strong><span>{character.tagline}</span>{selectedCharacterId === character.id && <b className="selection-check">✓</b>}</button>)}
        </div>
        <div className="section-title mode-title"><h3>{t('relationship')}</h3><span>{t('newAnytime')}</span></div>
        <div className="mode-options"><button disabled={busy} className={mode === 'friend' ? 'selected' : ''} onClick={() => setMode('friend')} aria-pressed={mode === 'friend'}><span>◌ {t('friend')}</span><small>{t('friendHint')}</small></button><button disabled={busy} className={mode === 'gentle_romance' ? 'selected' : ''} onClick={() => setMode('gentle_romance')} aria-pressed={mode === 'gentle_romance'}><span>♡ {t('romance')}</span><small>{t('romanceHint')}</small></button></div>
        {session && <div className="memory-reuse"><label><input type="checkbox" checked={reuseMemories} disabled={busy} onChange={event => setReuseMemories(event.target.checked)}/><span>{t('shareMemory', {name: characterName})}</span></label><p>{t(reuseMemories ? 'shareHint' : 'isolatedHint')}</p></div>}
        <label className="adult-check"><input type="checkbox" checked={adult} disabled={busy} onChange={event => setAdult(event.target.checked)}/><span>{t('adult')}</span></label>
        <button className="primary start-chat" disabled={!adult || busy || !status || !characters.length} onClick={start}>{busy && !sending ? t('processing') : t(session ? 'startNew' : 'start', {name: selectedCharacter.name})}<span>↗</span></button>
        {session && <p className="micro">{t('previousSessions')}</p>}
        <p className="footer-note">{t('footer')}</p>
      </section>

      <section className="conversation-panel page-panel" aria-label={t('chat')}>
        <div className="conversation-header"><div className="chat-avatar"><Portrait character={currentCharacter} small language={language}/></div><div className="conversation-title"><h2>{session ? characterName : t('welcomeTitle')}</h2><p>{session ? `${modeNames[session.mode] || session.mode} · ${t('aiRole')}` : t('welcomeSubtitle')}</p></div><button className="icon-button session-shortcut" aria-label={t('viewSessions')} onClick={() => goToTab('me')}>☷</button></div>
        {mock && <div className="demo-notice"><span>{t('mockMode')}</span>{t('mockBanner')}</div>}
        {restoring && !session ? <div className="welcome"><div className="welcome-symbol">◌</div><h3>{t('restoring')}</h3><p>{t('storedBackend')}</p></div> : !session ? <div className="welcome"><div className="welcome-symbol">☾</div><h3>{t('notRush')}</h3><p>{t('welcomeCopy')}</p><button className="primary" onClick={() => goToTab('characters')}>{t('chooseCharacter')}<span>↗</span></button><div className="welcome-features"><span>◇ {t('consentFeature')}</span><span>◌ {t('sessionFeature')}</span><span>✧ {t('identityFeature')}</span></div></div> : <>
          <div className="messages" aria-live="polite" aria-busy={sending}>
            {session.messages.length === 0 && <div className="empty-chat"><Portrait character={currentCharacter} small language={language}/><p>{session.character_greeting || currentCharacter.greeting}</p><span>{t('firstMessage')}</span>{language === 'en' && <span>{t('originalCopy')}</span>}</div>}
            {session.messages.map((message, index) => <div key={index} className={`message ${message.role}`}><span className="speaker">{message.role === 'assistant' ? characterName : t('you')}</span><div className="bubble">{message.content}</div></div>)}
            {pendingText && <div className="message user pending-message"><span className="speaker">{t('you')} · {t('sending')}</span><div className="bubble">{pendingText}</div></div>}
            {sending && <div className="typing" role="status"><span/><span/><span/><em>{t('responding')}</em></div>}
            <div ref={messagesEnd} className="messages-end"/>
          </div>
          <div className="composer-area"><div className="starters">{starters[language].map(text => <button disabled={busy} key={text} onClick={() => send(text)}>{text}</button>)}</div>
            <form onSubmit={event => {event.preventDefault(); if (!composing.current) void send()}}><textarea ref={input} aria-label={t('messageLabel')} placeholder={t('messagePlaceholder')} rows={1} value={draft} maxLength={2000} disabled={busy} onChange={event => setDraft(event.target.value)} onCompositionStart={() => {composing.current = true}} onCompositionEnd={() => {composing.current = false}} onKeyDown={event => {if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !composing.current && event.keyCode !== 229) {event.preventDefault(); void send()}}}/><button type="submit" aria-label={t('sendMessage')} disabled={busy || !draft.trim()}>↑</button></form>
            <p className="composer-note"><span>{t('yourPace')}</span><span className="desktop-composer-hint">{t('enterHint')}</span></p>
          </div>
        </>}
      </section>

      <section className="data-panel page-panel" aria-label={t('dataAgent')}>
        <div className="data-header"><button className="text-button" onClick={() => goToTab('me')}>← {t('back')}</button><span>DATA AGENT / SYNTHETIC</span></div>
        <div className="page-heading"><p className="eyebrow">QUESTION → QUERY → EVIDENCE</p><h2>{t('dataTitle')}</h2><p className="muted">{t('dataSubtitle')}</p></div>
        <div className="demo-notice data-notice">{t('dataBoundary')}</div>
        <form className="analysis-form" onSubmit={event => {event.preventDefault(); void runAnalysis()}}><label htmlFor="analysis-question">{t('dataQuestion')}</label><textarea id="analysis-question" rows={3} maxLength={300} disabled={busy} value={question} placeholder={t('dataPlaceholder')} onChange={event => setQuestion(event.target.value)}/><div className="analysis-examples">{analysisQuestions[language].map(text => <button type="button" disabled={busy} key={text} onClick={() => setQuestion(text)}>{text}</button>)}</div><button className="primary" disabled={busy || !question.trim()} type="submit">{t(analyzing ? 'analyzing' : 'analyze')}<span>↗</span></button></form>
        <div className="analysis-results" aria-live="polite" aria-busy={analyzing}>{analyzing ? <p className="micro">{t('analyzing')}</p> : !analysis ? <>{analysisFailure.length > 0 && <details className="analysis-detail" open><summary>{t('failureTrace')}</summary><TraceList items={analysisFailure} language={language}/></details>}<div className="small-empty">{t('dataEmpty')}</div></> : <><article className="analysis-answer"><h3>{t('dataAnswer')}</h3><p>{analysis.answer}</p></article><div className="analysis-provenance"><section><h3>{t('dataSource')}</h3><JsonValue value={analysis.source}/></section><section><h3>{t('dataScope')}</h3><JsonValue value={analysis.scope}/></section></div><details className="analysis-detail" open><summary>{t('dataPlan')}</summary><JsonValue value={analysis.plan}/></details><details className="analysis-detail" open><summary>{t('dataResult')}</summary><JsonValue value={analysis.result}/></details><details className="analysis-detail"><summary>{t('dataTrace')}</summary><p className="micro">{t('traceHint')}</p><TraceList items={analysis.trace || []} language={language}/></details></>}</div>
      </section>

      <aside className="details-column">
        <div className="panel-tabs"><button className={desktopDetail === 'memory' ? 'active' : ''} onClick={() => goToTab('memory')}>{t('memoryTitle')}{pendingCount > 0 && <span className="count-badge">{pendingCount}</span>}</button><button className={desktopDetail === 'me' ? 'active' : ''} onClick={() => goToTab('me')}>{t('deviceSessions')}</button></div>
        <section className="memory-panel page-panel" aria-label={t('memoryTitle')}>
          <div className="page-heading"><p className="eyebrow">ONLY WHAT YOU CHOOSE</p><h2>{t('memoryTitle')}<span>◇</span></h2><p className="muted">{t('memorySubtitle')}</p></div>
          {session ? <><div className="session-context"><span>{t('currentSession')}</span><strong>{characterName}</strong><small>{modeNames[session.mode]} · v{session.character_revision || 1}</small></div><div className="memory-explainer"><span>◇</span><p>{t('memoryExplanation')}</p></div><p className="pending-lifetime">{t('pendingHint')}</p>
            {!session.memories.length && <div className="memory-empty"><span>▱</span><h3>{t('memoryEmptyTitle')}</h3><p>{t('memoryEmptyHint')}</p></div>}
            <div className="memory-list">{session.memories.map(memory => <article className="memory-card" key={memory.id}><span className={`memory-status ${memory.status}`}><i/>{t(memory.status === 'pending' ? 'pending' : 'approved')}</span>{editingMemory === memory.id ? <form className="correction-form" onSubmit={event => {event.preventDefault(); void correctMemory()}}><label htmlFor={`correction-${memory.id}`}>{t('correctionLabel')}</label><textarea id={`correction-${memory.id}`} rows={3} maxLength={300} value={correction} disabled={busy} onChange={event => setCorrection(event.target.value)}/><div><button disabled={busy || !correction.trim()}>{t('saveCorrection')}</button><button disabled={busy} type="button" className="text-button" onClick={() => setEditingMemory(null)}>{t('cancel')}</button></div></form> : <><p>{memory.content}</p><div>{memory.status === 'pending' && <button disabled={busy} onClick={() => memoryAction(memory.id, 'approve')}>✓ {t('approve')}</button>}<button disabled={busy} className="text-button" onClick={() => {setEditingMemory(memory.id); setCorrection(memory.content)}}>{t(memory.status === 'pending' ? 'editApprove' : 'correct')}</button><button disabled={busy} className="text-button" onClick={() => memoryAction(memory.id, 'delete')}>{t(memory.status === 'pending' ? 'reject' : 'deleteMemory')}</button></div></>}</article>)}</div>
            <form className="memory-form" onSubmit={event => {event.preventDefault(); void addMemory()}}><label htmlFor="manual-memory">{t('manualMemory')}</label><textarea id="manual-memory" maxLength={300} rows={3} disabled={busy} placeholder={t('memoryPlaceholder')} value={memoryDraft} onChange={event => setMemoryDraft(event.target.value)}/><div><span>{memoryDraft.length}/300</span><button disabled={busy || !memoryDraft.trim()}>{t('saveMemory')} ↗</button></div></form>
            <p className="micro">{t('memoryDeleteHint')}</p>
          </> : <div className="memory-empty"><span>◇</span><h3>{t('startFirst')}</h3><p>{t('memoryNoSession')}</p><button className="secondary" onClick={() => goToTab('characters')}>{t('chooseCharacter')} ↗</button></div>}
        </section>

        <section className="account-panel page-panel" aria-label={t('accountLabel')}>
          <div className="page-heading"><p className="eyebrow">YOUR SPACE, YOUR PACE</p><h2>{t('myTitle')}<span>◒</span></h2><p className="muted">{t('mySubtitle')}</p></div>
          <div className="section-title"><h3>{t('deviceSessions')}</h3><button className="text-button" disabled={busy} onClick={() => goToTab('characters')}>＋ {t('newChat')}</button></div>
          <p className="micro session-list-note">{t('deviceHint')}</p>
          <div className="session-list">{sessions.length ? sessions.map(item => <button key={item.id} disabled={busy} className={`session-card ${item.id === session?.id ? 'current' : ''}`} onClick={() => restoreSession(item.id)}><span className="session-card-icon">◌</span><span><strong>{item.character_name || t('aiRole')}{item.id === session?.id && <i>{t('current')}</i>}</strong><small>{modeNames[item.mode] || item.mode} · {item.turn_count} {t('turns')}</small><small>{shortDate(item.last_active || item.created, language)}</small></span><b>↗</b></button>) : <div className="small-empty">{t('noSessions')}</div>}</div>
          <button className="data-agent-entry" onClick={() => goToTab('data')}><span>◈ {t('dataAgent')}<small>{t('dataEntryHint')}</small></span><b>↗</b></button>
          <div className="settings-block"><div className="section-title"><h3>{t('appConnection')}</h3><button className="text-button" disabled={busy} onClick={reloadService}>{t('refresh')}</button></div><div className="setting-row"><span>{t('currentModel')}</span><strong>{status ? mock ? t('mockFlow') : status.model || t('pendingConfig') : t('disconnected')}</strong></div><div className="setting-row"><span>{t('dataRange')}</span><strong>{t('currentBackend')}</strong></div>{!online && language === 'en' && <p className="connection-notice" role="status">{t('offline')}</p>}{language === 'zh' ? <AppInstall/> : !isNativeApp() && <details className="install-guide"><summary>{t('installTitle')}</summary><p>{t('installHint')}</p><small>{t('installBoundary')}</small></details>}<a className="admin-entry" href="?view=admin"><span>⚙ {t('admin')}<small>{t('adminHint')}</small></span><b>↗</b></a></div>
          <details className="connection-card"><summary>{t('connectionTitle')}<span>⌄</span></summary><p className="micro">{t('connectionHint')}</p><form className="connection-form" onSubmit={event => {event.preventDefault(); void saveConnection()}}><label htmlFor="connection-url">{t('backendAddress')}</label><input id="connection-url" type="url" autoComplete="url" placeholder="https://your-api.example.com" value={connection.baseUrl} onChange={event => setConnectionDraft({...connection, baseUrl: event.target.value})}/><label htmlFor="connection-code">{t('demoCode')}</label><input id="connection-code" type="password" autoComplete="off" placeholder={t('demoCodePlaceholder')} value={connection.accessToken} onChange={event => setConnectionDraft({...connection, accessToken: event.target.value})}/><div><button type="submit" disabled={busy}>{t('saveConnection')}</button><button className="text-button" type="button" disabled={busy} onClick={() => saveConnection(true)}>{t('resetConnection')}</button></div></form>{connectionNotice && <p className="connection-notice" role="status">{connectionNotice}</p>}<p className="micro">{t('connectionFooter')}</p></details>
          <details className="privacy-card"><summary>{t('privacyTitle')}<span>⌄</span></summary><p>{t('privacy1')}</p><p>{t('privacy2')}</p><p>{t('privacy3')}</p></details>
          {session && <><details className="insights-card"><summary>{t('insights')}<span>⌄</span></summary><p className="micro">{t('insightsHint')}</p><div className="metrics"><div><span>{t('completed')}</span><strong>{session.insights.turn_count}<small> {t('turns')}</small></strong></div><div><span>{t('medianTime')}</span><strong>{session.insights.median_latency_ms ?? '—'}<small> ms</small></strong></div></div><p className="micro">{t('mockTime')}</p><div className="mood-bars">{Object.entries(session.insights.emotion_counts).map(([key, value]) => <div key={key}><span>{moodNames[key] || key}</span><div><i style={{width: `${value / Math.max(session.insights.turn_count, 1) * 100}%`}}/></div><b>{value}</b></div>)}</div></details>
            <details className="trace"><summary>{t(failedTrace.length ? 'failureTrace' : 'traceTitle')}<span>⌄</span></summary>{lastRun || failedTrace.length ? <><p className="micro">{t('traceHint')}</p><TraceList items={failedTrace.length ? failedTrace : lastRun!.trace} language={language}/></> : <p className="micro">{t('traceEmpty')}</p>}</details>
            <div className="data-actions"><h3>{t('sessionData')}</h3><button disabled={busy} onClick={() => clear(false)}><span>{t('clearHistory')}<small>{t('clearHistoryHint')}</small></span><b>↗</b></button><button className="danger" disabled={busy} onClick={() => clear(true)}><span>{t('deleteSession')}<small>{t('deleteSessionHint')}</small></span><b>×</b></button></div>
          </>}
          <div className="lab-note"><span>HARBOR COMPANION</span><p>{t('labNote')}</p></div>
        </section>
      </aside>
    </main>
    <nav className="mobile-nav" aria-label={t('navLabel')}>{tabItems.map(item => <button key={item.id} className={tab === item.id ? 'active' : ''} onClick={() => goToTab(item.id)} aria-current={tab === item.id ? 'page' : undefined}><span>{item.icon}{item.id === 'memory' && pendingCount > 0 && <i>{pendingCount}</i>}</span><small>{t(item.label)}</small></button>)}</nav>
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
    ? <React.Suspense fallback={<div className="welcome" role="status">{translator(readLanguage())('adminLoading')}</div>}><AdminApp onExit={leaveManagement}/></React.Suspense>
    : <App/>
}

void registerAppShell()
createRoot(document.getElementById('root')!).render(<React.StrictMode><Root/></React.StrictMode>)
