import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import type { AdminAuthMode, AdminView, Character, CharacterInput, Operations, Overview, ProviderStatus, Review, SessionDetail, SessionSummary } from './types'
import { readLanguage, storeLanguage, type Language } from '../i18n'
import { adminTranslator } from './i18n'
import OperationsPanel from './OperationsPanel'
import './admin.css'

type AdminAppProps = { onExit?: () => void }
type AuthResponse = { token: string; expires_in: number }
type ReviewInput = { session_id: string; run_id: string; persona_score: number; empathy_score: number; memory_score: number; note: string }

const views: Array<{ id: AdminView; title: string; glyph: string; subtitle: string }> = [
  { id: 'overview', title: '运行总览', glyph: '◈', subtitle: '查看当前后端数据与运行状态' },
  { id: 'characters', title: '角色工作室', glyph: '✧', subtitle: '编写人设、管理角色与发布状态' },
  { id: 'sessions', title: '会话记录', glyph: '◷', subtitle: '先看概要，按需查看私密内容' },
  { id: 'reviews', title: '质量评审', glyph: '◇', subtitle: '积累人工判断，不把模拟结果当效果' },
  { id: 'provider', title: '模型连接', glyph: '⌁', subtitle: '查看配置状态，密钥留在服务端' },
  { id: 'operations', title: '运行控制', glyph: '⌘', subtitle: '查看单进程限额与脱敏动作审计' },
]

const emptyCharacter = (): CharacterInput => ({
  name: '', tagline: '', description: '', system_prompt: '', greeting: '',
  accent_color: '#b8cbb0', avatar_style: 'nova', enabled: false,
})
const emptyReview = (): ReviewInput => ({ session_id: '', run_id: '', persona_score: 3, empathy_score: 3, memory_score: 3, note: '' })
const shortId = (id: string) => id.length > 14 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id

export default function AdminApp({ onExit }: AdminAppProps) {
  const [language, setLanguage] = useState<Language>(readLanguage)
  const t = adminTranslator(language)
  useEffect(() => {
    storeLanguage(language)
    document.title = language === 'en' ? 'Harbor · Management studio' : '港湾 · 管理工作台'
  }, [language])
  const formatTime = (value: string | null | undefined) => {
    if (!value) return t('尚无记录')
    const timestamp = new Date(value)
    return Number.isNaN(timestamp.getTime()) ? value : timestamp.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', { hour12: false })
  }
  const modeName = (mode: string) => mode === 'gentle_romance' ? t('温柔关系') : mode === 'friend' ? t('朋友陪伴') : mode
  const [initialized, setInitialized] = useState<boolean | null>(null)
  const [canInitialize, setCanInitialize] = useState(false)
  const [token, setToken] = useState<string | null>(null)
  const tokenRef = useRef<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<number | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [view, setView] = useState<AdminView>('overview')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [characters, setCharacters] = useState<Character[]>([])
  const [characterId, setCharacterId] = useState<string | null>(null)
  const [characterForm, setCharacterForm] = useState<CharacterInput | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [privacyAcknowledged, setPrivacyAcknowledged] = useState(false)
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [reviews, setReviews] = useState<Review[]>([])
  const [reviewForm, setReviewForm] = useState<ReviewInput>(emptyReview)
  const [provider, setProvider] = useState<ProviderStatus | null>(null)
  const [operations, setOperations] = useState<Operations | null>(null)
  const [authMode, setAuthMode] = useState<AdminAuthMode | null>(null)

  const canReviewSession = (session: SessionSummary | undefined) => !!session && (authMode === 'local_demo'
    || (authMode === 'accounts' && (session.review_access_allowed === true || session.review_access_allowed === 1)))
  const reviewPermission = (session: SessionSummary) => authMode === 'local_demo' ? t('本机演示审阅')
    : authMode === null ? t('权限状态待确认') : canReviewSession(session) ? t('用户已授权审阅') : t('未授权原文审阅')

  const logout = useCallback(() => {
    tokenRef.current = null
    setToken(null)
    setExpiresAt(null)
    setDetail(null)
    setSessions([])
    setReviews([])
    setCharacters([])
    setOverview(null)
    setProvider(null)
    setOperations(null)
    setAuthMode(null)
    setLoading(false)
    setCharacterForm(null)
    setPrivacyAcknowledged(false)
    setReviewForm(emptyReview())
    setPassword('')
    setConfirmation('')
    setNotice('')
  }, [])

  const request = useCallback(async <T,>(path: string, method = 'GET', body?: unknown, publicRequest = false): Promise<T> => {
    const activeToken = publicRequest ? null : tokenRef.current
    if (!publicRequest && !activeToken) throw new Error('请先登录管理员账号。')
    let payload: T
    try {
      payload = await api<T>(`/admin${path}`, method, body, activeToken ?? undefined)
    } catch (issue) {
      if (issue instanceof ApiError && issue.status === 401 && activeToken && activeToken === tokenRef.current) logout()
      if (issue instanceof ApiError && issue.status === 403 && path === '/bootstrap'
          && issue.sourceMessage === '请在后端服务器本机浏览器初始化管理员。') {
        setCanInitialize(false)
        throw new Error('先在服务器本机初始化管理员，再配置手机或远程访问。')
      }
      throw issue
    }
    if (!publicRequest && activeToken !== tokenRef.current) throw new Error('登录状态已改变，请重新操作。')
    return payload
  }, [logout])

  const loadSetup = useCallback(async () => {
    setError('')
    try {
      const status = await request<{ initialized: boolean; can_initialize: boolean }>('/setup-status', 'GET', undefined, true)
      setInitialized(status.initialized)
      setCanInitialize(status.can_initialize)
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : '初始化状态读取失败。')
    }
  }, [request])

  useEffect(() => { void loadSetup() }, [loadSetup])
  useEffect(() => {
    if (!token || !expiresAt) return
    const timer = window.setTimeout(() => {
      logout()
      setError('本次登录已到期，请重新登录。')
    }, Math.max(0, expiresAt - Date.now()))
    return () => window.clearTimeout(timer)
  }, [token, expiresAt, logout])

  const loadView = useCallback(async (target: AdminView) => {
    const loadToken = tokenRef.current
    if (!loadToken) return
    setLoading(true)
    setError('')
    if (target === 'sessions') setDetail(null)
    try {
      const status = await api<{ auth_mode: unknown }>('/status', 'GET', undefined, loadToken)
      if (loadToken !== tokenRef.current) return
      if (status.auth_mode !== 'local_demo' && status.auth_mode !== 'accounts') throw new Error('无法确认后端账户模式，原文审阅暂不可用。')
      setAuthMode(status.auth_mode)
      if (target === 'overview') setOverview(await request<Overview>('/overview'))
      if (target === 'characters') setCharacters((await request<{ items: Character[] }>('/characters')).items)
      if (target === 'sessions') setSessions((await request<{ items: SessionSummary[] }>('/sessions')).items)
      if (target === 'reviews') {
        const [reviewData, sessionData] = await Promise.all([
          request<{ items: Review[] }>('/reviews'), request<{ items: SessionSummary[] }>('/sessions'),
        ])
        setReviews(reviewData.items)
        setSessions(sessionData.items)
      }
      if (target === 'provider') setProvider(await request<ProviderStatus>('/provider-status'))
      if (target === 'operations') setOperations(await request<Operations>('/operations'))
    } catch (issue) {
      if (loadToken === tokenRef.current) {
        setAuthMode(null)
        setError(issue instanceof Error ? issue.message : '数据读取失败。')
      }
    } finally { if (loadToken === tokenRef.current) setLoading(false) }
  }, [request])

  useEffect(() => {
    if (token) void loadView(view)
    setDetail(null)
    setPrivacyAcknowledged(false)
  }, [token, view, loadView])

  async function authenticate(event: FormEvent) {
    event.preventDefault()
    if (initialized === null) return
    if (!initialized && password !== confirmation) { setError('两次输入的密码不一致。'); return }
    setBusy(true)
    setError('')
    try {
      const result = await request<AuthResponse>(initialized ? '/login' : '/bootstrap', 'POST', { username: username.trim(), password }, true)
      tokenRef.current = result.token
      setToken(result.token)
      setExpiresAt(Date.now() + result.expires_in * 1000)
      setInitialized(true)
      setPassword('')
      setConfirmation('')
      setView('overview')
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : '登录未完成。')
    } finally { setBusy(false) }
  }

  async function saveCharacter(event: FormEvent) {
    event.preventDefault()
    if (!characterForm) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await request(characterId ? `/characters/${encodeURIComponent(characterId)}` : '/characters', characterId ? 'PUT' : 'POST', characterForm)
      setCharacterForm(null)
      setNotice('角色已保存。发布状态决定新会话能否选择该角色，已有会话仍保留原记录。')
      await loadView('characters')
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : '角色保存失败。')
    } finally { setBusy(false) }
  }

  async function setCharacterEnabled(character: Character) {
    setBusy(true)
    setError('')
    setNotice('')
    const { name, tagline, description, system_prompt, greeting, accent_color, avatar_style, enabled } = character
    try {
      await request(`/characters/${encodeURIComponent(character.id)}`, 'PUT', { name, tagline, description, system_prompt, greeting, accent_color, avatar_style, enabled: !enabled })
      setNotice(enabled ? '角色已归档，不再出现在新会话选择中。' : '角色已发布，可在新会话中选择。')
      await loadView('characters')
    } catch (issue) {
      setError(issue instanceof Error ? issue.message : '角色状态更新失败。')
    } finally { setBusy(false) }
  }

  async function readSession(id: string) {
    if (!privacyAcknowledged || !canReviewSession(sessions.find(session => session.id === id))) return
    setBusy(true)
    setError('')
    setDetail(null)
    try { setDetail(await request<SessionDetail>(`/sessions/${encodeURIComponent(id)}`)) }
    catch (issue) { setError(issue instanceof Error ? issue.message : '会话读取失败。') }
    finally { setBusy(false) }
  }

  async function saveReview(event: FormEvent) {
    event.preventDefault()
    if (!canReviewSession(sessions.find(session => session.id === reviewForm.session_id))) {
      setError('用户尚未授予此会话的原文审阅权限。')
      return
    }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await request('/reviews', 'POST', { ...reviewForm, run_id: reviewForm.run_id.trim() || null })
      setReviewForm(emptyReview())
      setNotice('人工评审已记录。评分仅代表本次观察，不能替代完整效果评估。')
      await loadView('reviews')
    } catch (issue) { setError(issue instanceof Error ? issue.message : '评审保存失败。') }
    finally { setBusy(false) }
  }

  function editCharacter(character?: Character) {
    setCharacterId(character?.id ?? null)
    setCharacterForm(character ? {
      name: character.name, tagline: character.tagline, description: character.description,
      system_prompt: character.system_prompt, greeting: character.greeting,
      accent_color: character.accent_color, avatar_style: character.avatar_style, enabled: character.enabled,
    } : emptyCharacter())
    setNotice('')
    setError('')
  }

  async function endLogin() {
    const activeToken = tokenRef.current
    setBusy(true)
    try {
      if (activeToken) await api('/admin/logout', 'POST', undefined, activeToken)
    } catch {
      // Clear local credentials even when the backend cannot revoke an expired token.
    } finally {
      logout()
      setError('')
      setBusy(false)
    }
  }

  const heading = views.find(item => item.id === view)!

  if (!token) return <div className="admin-root admin-auth-shell">
    <div className="admin-auth-story">
      <span className="admin-brand-mark">⌁</span>
      <p className="admin-kicker">HARBOR / LOCAL STUDIO</p>
      <h1>{t('让陪伴有温度，')}<br /><span>{t('也有边界。')}</span></h1>
      <p>{t('角色、记忆与评审，在这里管理。')}<br />{t('原始聊天保存在当前后端，真实效果由证据说明。')}</p>
      <div className="admin-story-orbit" aria-hidden="true"><i /><b>✧</b><i /></div>
      <button className="admin-text-button" type="button" onClick={onExit ?? (() => { window.location.href = '/' })}>{t('← 返回陪伴应用')}</button>
    </div>
    <section className="admin-auth-card" aria-labelledby="admin-auth-title">
      <label className="admin-language-control"><span>{t('界面语言')}</span><select aria-label={t('界面语言')} value={language} onChange={event => setLanguage(event.target.value as Language)}><option value="zh">中文</option><option value="en">English</option></select></label><span className="admin-kicker">{t('后端管理工作台')}</span>
      <h2 id="admin-auth-title">{initialized === false ? canInitialize ? t('创建管理员') : t('等待本机初始化') : initialized ? t('管理员登录') : t('连接管理服务')}</h2>
      <p>{initialized === false ? canInitialize ? t('首次本机运行，请为工作台设置独立账号和密码。') : t('先在服务器本机初始化管理员，再配置手机或远程访问。') : t('使用当前后端的管理员账号登录。关闭或刷新页面后需要重新登录。')}</p>
      {error && <div className="admin-alert admin-alert-error" role="alert">{t(error)}</div>}
      {initialized === null ? <div className="admin-empty"><p>{error ? t('尚未取得初始化状态。') : t('正在读取初始化状态…')}</p><button type="button" className="admin-button" onClick={() => void loadSetup()}>{t('重新连接')}</button></div> : !initialized && !canInitialize ? <div className="admin-empty"><p>{t('初始化入口只在服务端本机开放。')}</p><button type="button" className="admin-button" onClick={() => void loadSetup()}>{t('重新读取状态')}</button></div> :
        <form onSubmit={authenticate} className="admin-form">
          <label>{t('管理员账号')}<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} minLength={3} maxLength={40} pattern="[A-Za-z0-9_.\-]+" required placeholder={t("3–40 位英文、数字或 _ . -")} /></label>
          <label>{t('密码')}<input type="password" autoComplete={initialized ? 'current-password' : 'new-password'} value={password} onChange={event => setPassword(event.target.value)} minLength={12} maxLength={128} required placeholder={initialized ? t('输入密码') : t('至少 12 位，建议使用密码管理器')} /></label>
          {!initialized && <label>{t('再次输入密码')}<input type="password" autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} minLength={12} maxLength={128} required placeholder={t("确认密码")} /></label>}
          <button className="admin-button admin-button-primary" type="submit" disabled={busy}>{busy ? t('正在处理…') : initialized ? t('进入工作台 →') : t('创建并进入 →')}</button>
        </form>}
      <div className="admin-auth-footnote"><span>◎</span><p>{t('登录凭据仅保存在当前页面内存。此工作台面向本机原型，公开部署前需要独立的访问控制与 HTTPS。')}</p></div>
    </section>
  </div>

  return <div className="admin-root admin-workspace">
    <aside className="admin-sidebar">
      <div className="admin-logo"><span>⌁</span><div><strong>{t('港湾')}</strong><small>{t('管理工作台')}</small></div></div>
      <div className="admin-local-badge"><i /> {t('后端管理 · 私密数据')}</div>
      <nav className="admin-nav" aria-label={t("管理功能")}>{views.map(item => <button key={item.id} type="button" className={view === item.id ? 'active' : ''} aria-current={view === item.id ? 'page' : undefined} onClick={() => { setView(item.id); setError(''); setNotice('') }}><span aria-hidden="true">{item.glyph}</span>{t(item.title)}</button>)}</nav>
      <div className="admin-sidebar-bottom"><label className="admin-language-control"><span>{t('界面语言')}</span><select aria-label={t('界面语言')} value={language} onChange={event => setLanguage(event.target.value as Language)}><option value="zh">中文</option><option value="en">English</option></select></label><p>{t('原型工作台')}<br />{t('先记录事实，再评价效果。')}</p><button type="button" className="admin-text-button" onClick={onExit ?? (() => { window.location.href = '/' })}>{t('← 返回陪伴应用')}</button><button type="button" className="admin-text-button" disabled={busy} onClick={() => void endLogin()}>{t('退出登录')}</button></div>
    </aside>
    <main className="admin-main">
      <header className="admin-header"><div><p className="admin-kicker">HARBOR / OPERATIONS</p><h1>{t(heading.title)}</h1><p>{t(heading.subtitle)}</p></div><button className="admin-button admin-button-quiet" type="button" disabled={loading || busy} onClick={() => void loadView(view)}>{loading ? t('刷新中…') : t('↻ 刷新数据')}</button></header>
      {error && <div className="admin-alert admin-alert-error" role="alert">{t(error)}</div>}
      {notice && <div className="admin-alert admin-alert-success" role="status">{t(notice)}</div>}
      {loading && <p className="admin-loading" role="status">{t('正在读取当前后端数据…')}</p>}

      {view === 'overview' && <>
        <div className="admin-callout"><span aria-hidden="true">✧</span><div><strong>{t('每一次对话，都值得被认真复盘。')}</strong><p>{t('这里展示运行记录与人工评审。模拟回复可以验证流程，真实陪伴质量仍需模型接入后的场景评估。')}</p></div></div>
        {overview ? <>
          <div className="admin-metric-grid">{[
            [t('会话'), overview.session_count, t('当前后端已建立的会话')], [t('对话轮次'), overview.turn_count, t('已保存的成功运行记录')],
            [t('已发布角色'), overview.active_character_count, t('新会话可选')], [t('人工评审'), overview.reviews_count, t('逐条观察与评分')],
          ].map(([label, value, hint]) => <article className="admin-metric-card" key={String(label)}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>)}</div>
          <div className="admin-two-column"><section className="admin-panel"><h2>{t('记忆与确认')}</h2><p className="admin-subtle">{t('模型提议与用户确认分开记录。')}</p><div className="admin-stat-row"><span>{t('记忆记录总数')}</span><strong>{overview.memory_count}</strong></div><div className="admin-stat-row"><span>{t('待确认提议')}</span><strong>{overview.pending_memory_count}</strong></div><p className="admin-note">{t('待确认记忆不会作为已批准的长期记忆使用。')}</p></section>
            <section className="admin-panel"><h2>{t('调用来源与耗时')}</h2><div className="admin-stat-row"><span>{t('平均服务端耗时')}</span><strong>{overview.average_latency_ms == null ? t('暂无记录') : `${Math.round(overview.average_latency_ms)} ms`}</strong></div>{Object.entries(overview.provider_counts).map(([name, count]) => <div className="admin-stat-row" key={name}><span><code>{name}</code></span><strong>{count} {t('次')}</strong></div>)}<p className="admin-note">{t('含服务端处理，不等于端到端体验。模拟调用耗时不能作为真实模型速度。')}</p></section></div>
          {overview.scope && <p className="admin-note">{t('总览是当前服务端的汇总计数。在账户模式下，查看会话原文仍需该用户单独授权。')}</p>}
        </> : !loading && <div className="admin-empty">{t('暂无总览数据。可先刷新或在陪伴应用发起会话。')}</div>}
      </>}

      {view === 'characters' && <>
        <div className="admin-section-toolbar"><p>{t('人设描述的是角色风格，身份与安全边界由运行时共同约束。')}</p><button type="button" className="admin-button admin-button-primary" disabled={busy} onClick={() => editCharacter()}>{t('＋ 新建角色')}</button></div>
        {characterForm && <section className="admin-panel admin-editor"><div className="admin-panel-heading"><h2>{characterId ? t('编辑角色') : t('新建角色')}</h2><button type="button" className="admin-text-button" disabled={busy} onClick={() => setCharacterForm(null)}>{t('取消编辑')}</button></div><form className="admin-form" onSubmit={saveCharacter}>
          <div className="admin-form-grid"><label>{t('角色名称')}<input value={characterForm.name} onChange={event => setCharacterForm({ ...characterForm, name: event.target.value })} required maxLength={40} placeholder={t("例：Nova")} /></label><label>{t('一句话介绍')}<input value={characterForm.tagline} onChange={event => setCharacterForm({ ...characterForm, tagline: event.target.value })} required maxLength={80} placeholder={t("例：陪你整理日常的小小港湾")} /></label></div>
          <label>{t('公开简介')}<textarea value={characterForm.description} onChange={event => setCharacterForm({ ...characterForm, description: event.target.value })} required maxLength={600} rows={3} placeholder={t("写给用户看的角色风格与能力说明")} /></label>
          <label>{t('角色提示词')}<textarea className="admin-code-input" value={characterForm.system_prompt} onChange={event => setCharacterForm({ ...characterForm, system_prompt: event.target.value })} required maxLength={6000} rows={7} placeholder={t("定义语气、表达习惯、能力范围；不要写密钥或真实私人信息")} /><small>{t('提示词不能覆盖成年人准入、AI 身份披露及用户确认边界。')}</small></label>
          <label>{t('开场白')}<textarea value={characterForm.greeting} onChange={event => setCharacterForm({ ...characterForm, greeting: event.target.value })} required maxLength={600} rows={3} placeholder={t("例：你好，我是 AI 伙伴 Nova。今天想从哪里开始？")} /></label>
          <div className="admin-form-grid"><label>{t('角色配色')}<div className="admin-color-field"><input type="color" aria-label={t("选择角色配色")} value={characterForm.accent_color} onChange={event => setCharacterForm({ ...characterForm, accent_color: event.target.value })} /><code>{characterForm.accent_color}</code></div></label><label>{t('头像风格')}<select value={characterForm.avatar_style} onChange={event => setCharacterForm({ ...characterForm, avatar_style: event.target.value as CharacterInput['avatar_style'] })}><option value="nova">{t('Nova · 轻柔')}</option><option value="sage">{t('Sage · 平静')}</option><option value="ember">{t('Ember · 温暖')}</option></select></label></div>
          <label className="admin-checkbox"><input type="checkbox" checked={characterForm.enabled} onChange={event => setCharacterForm({ ...characterForm, enabled: event.target.checked })} /><span>{t('发布角色，允许新会话选择')}</span></label><div className="admin-form-actions"><button className="admin-button admin-button-primary" disabled={busy} type="submit">{busy ? t('正在保存…') : t('保存角色')}</button><span className="admin-note">{t('修改会记录新的角色版本。')}</span></div>
        </form></section>}
        <div className="admin-character-grid">{characters.map(character => <article className="admin-panel admin-character-card" key={character.id}><div className="admin-character-top"><div className={`admin-avatar admin-avatar-${character.avatar_style}`} aria-hidden="true">{character.avatar_style === 'sage' ? '✺' : character.avatar_style === 'ember' ? '✦' : '✧'}</div><span className={`admin-status ${character.enabled ? 'published' : ''}`}>{character.enabled ? t('已发布') : t('已归档')}</span></div><h2>{character.name}</h2><p className="admin-character-tagline">{character.tagline}</p><p className="admin-character-description">{character.description}</p><div className="admin-character-meta"><span>{t('版本')} {character.revision}</span><span>{t('更新')} {formatTime(character.updated)}</span></div><div className="admin-card-actions"><button className="admin-button" disabled={busy} type="button" onClick={() => editCharacter(character)}>{t('编辑人设')}</button><button className="admin-text-button" disabled={busy} type="button" onClick={() => void setCharacterEnabled(character)}>{character.enabled ? t('归档角色') : t('发布角色')}</button></div></article>)}</div>
        {!characters.length && !loading && <div className="admin-empty">{t('暂无角色。新建一个角色，先保存为草稿再发布。')}</div>}
      </>}

      {view === 'sessions' && <>
        <div className="admin-privacy-box"><strong>{t('会话默认只展示概要。')}</strong><p>{t('查看原文会在当前页面显示聊天和记忆，其中可能包含私人信息。不要把原文、截图或评审中的敏感内容上传到公开仓库。')}</p><p>{t('账户模式下，只有用户在陪伴应用中授予审阅权限后，管理员才能查看原文与添加评审。勾选说明不会代替用户授权。')}</p><label className="admin-checkbox"><input type="checkbox" checked={privacyAcknowledged} onChange={event => { setPrivacyAcknowledged(event.target.checked); if (!event.target.checked) setDetail(null) }} /><span>{t('我理解上述说明，并仅查看当前后端允许审阅的聊天内容')}</span></label></div>
        <div className="admin-panel admin-table-panel"><div className="admin-table-scroll"><table className="admin-table"><thead><tr><th>{t('会话 / 角色')}</th><th>{t('模式')}</th><th>{t('轮次')}</th><th>{t('记忆')}</th><th>{t('最近活动')}</th><th>{t('审阅权限')}</th><th>{t('操作')}</th></tr></thead><tbody>{sessions.map(session => <tr key={session.id}><td><strong>{session.character_name || session.character_id}</strong><code title={session.id}>{shortId(session.id)}</code></td><td>{modeName(session.mode)}</td><td>{session.turn_count}</td><td>{session.memory_count}</td><td>{formatTime(session.last_active ?? session.created)}</td><td><span className={`admin-status ${canReviewSession(session) ? 'published' : ''}`}>{reviewPermission(session)}</span></td><td><button className="admin-button admin-button-small" disabled={!privacyAcknowledged || busy || loading || !canReviewSession(session)} type="button" onClick={() => void readSession(session.id)}>{t('查看聊天与记忆')}</button></td></tr>)}</tbody></table></div>{!sessions.length && !loading && <div className="admin-empty">{t('暂无会话记录。')}</div>}</div>
        {detail && privacyAcknowledged && <section className="admin-panel admin-session-detail"><div className="admin-panel-heading"><div><h2>{detail.session.character_name} {t('· 会话详情')}</h2><code>{detail.session.id}</code></div><button type="button" className="admin-text-button" onClick={() => setDetail(null)}>{t('隐藏内容')}</button></div><p className="admin-note">{t('只读查看。管理端不会替用户回复，也不会替用户确认记忆。')}</p><div className="admin-chat-transcript">{detail.messages.map((message, index) => <article className={`admin-transcript-message ${message.role === 'user' ? 'from-user' : ''}`} key={`${message.created}-${index}`}><header><strong>{message.role === 'user' ? t('用户') : message.role === 'assistant' ? detail.session.character_name : message.role}</strong><time>{formatTime(message.created)}</time></header><p>{message.content}</p></article>)}{!detail.messages.length && <p className="admin-note">{t('该会话尚无已保存的聊天内容。')}</p>}</div><h3>{t('记忆记录')}</h3><div className="admin-memory-list">{detail.memories.map(memory => <article key={memory.id}><span className={`admin-status ${memory.status === 'approved' ? 'published' : ''}`}>{memory.status === 'approved' ? t('用户已确认') : t('待用户确认')}</span><p>{memory.content}</p></article>)}{!detail.memories.length && <p className="admin-note">{t('暂无记忆记录。')}</p>}</div><h3>{t('运行概要')}</h3><div className="admin-turn-list">{detail.turns.map(turn => <article key={turn.id}><div><code>{shortId(turn.id)}</code><span>{turn.provider}</span><span>{turn.emotion}</span><span>{Math.round(turn.latency_ms)} ms</span></div><small>{formatTime(turn.created)}</small></article>)}</div><button className="admin-button" type="button" onClick={() => { setReviewForm({ ...emptyReview(), session_id: detail.session.id }); setView('reviews'); setNotice(t('已选择会话。请根据实际观察填写人工评分。')) }}>{t('为这次会话添加评审 →')}</button></section>}
      </>}

      {view === 'reviews' && <>
        <div className="admin-callout"><span aria-hidden="true">◇</span><div><strong>{t('评分用于复盘，不代表已验证的成功率。')}</strong><p>{t('1 分表示明显未达到，3 分表示基本符合，5 分表示在本次观察中表现稳定。模拟回复和真实模型记录要分开解读。')}</p></div></div>
        <section className="admin-panel"><h2>{t('新增人工评审')}</h2><p className="admin-subtle">{t('账户模式下，评审也需要用户的会话审阅授权。')}</p><form className="admin-form" onSubmit={saveReview}><div className="admin-form-grid"><label>{t('关联会话')}<select value={reviewForm.session_id} onChange={event => setReviewForm({ ...reviewForm, session_id: event.target.value })} required><option value="">{t('选择已观察的会话')}</option>{sessions.map(session => <option key={session.id} value={session.id} disabled={!canReviewSession(session)}>{session.character_name} · {shortId(session.id)} · {session.turn_count} {t('轮')} · {reviewPermission(session)}</option>)}</select></label><label>{t('运行 ID（可选）')}<input value={reviewForm.run_id} onChange={event => setReviewForm({ ...reviewForm, run_id: event.target.value })} maxLength={80} placeholder={t("仅评审某轮时填写运行 ID")} /></label></div><div className="admin-score-grid">{([
          ['persona_score', t('人设一致性'), t('是否保持设定与 AI 身份')], ['empathy_score', t('回应与共情'), t('是否理解语境，避免空泛劝慰')], ['memory_score', t('记忆使用'), t('是否准确引用已确认的信息')],
        ] as const).map(([field, label, hint]) => <label key={field}>{label}<select value={reviewForm[field]} onChange={event => setReviewForm({ ...reviewForm, [field]: Number(event.target.value) })}>{[1, 2, 3, 4, 5].map(score => <option key={score} value={score}>{score} / 5</option>)}</select><small>{hint}</small></label>)}</div><label>{t('评审说明')}<textarea value={reviewForm.note} onChange={event => setReviewForm({ ...reviewForm, note: event.target.value })} rows={4} maxLength={2000} required placeholder={t("写具体观察、问题和下一步调整。避免复制真实姓名、联系方式或整段私人聊天。")} /><small>{reviewForm.note.length} {t('/ 2000 字符')}</small></label><button type="submit" disabled={busy || loading || !canReviewSession(sessions.find(session => session.id === reviewForm.session_id))} className="admin-button admin-button-primary">{busy ? t('正在保存…') : t('保存评审')}</button></form></section>
        <div className="admin-section-heading"><h2>{t('评审记录')}</h2><span>{reviews.length} {t('条已读取记录')}</span></div><div className="admin-review-list">{reviews.map(review => <article className="admin-panel" key={review.id}><div className="admin-panel-heading"><code>{shortId(review.session_id)}</code><span className="admin-status">{review.provider === 'mock' ? t('模拟流程') : review.provider || t('来源未记载')}</span></div><div className="admin-review-scores"><span>{t('人设')} <b>{review.persona_score}/5</b></span><span>{t('共情')} <b>{review.empathy_score}/5</b></span><span>{t('记忆')} <b>{review.memory_score}/5</b></span></div><p className="admin-review-note">{review.note}</p><small className="admin-note">{formatTime(review.created)}{review.run_id ? ` · ${t('运行')} ${shortId(review.run_id)}` : t(' · 会话整体评审')}</small></article>)}</div>{!reviews.length && !loading && <div className="admin-empty">{t('尚无人工评审，完成一段对话后再记录观察。')}</div>}
      </>}

      {view === 'provider' && <>
        <div className="admin-callout"><span aria-hidden="true">⌁</span><div><strong>{t('密钥由服务端环境管理。')}</strong><p>{t('此页面只查看连接状态，不接收、不保存、不显示 API 密钥。修改后端 .env 后重启服务，让新配置生效。')}</p></div></div>
        {provider && <section className="admin-panel"><div className="admin-panel-heading"><h2>{t('当前配置')}</h2><span className={`admin-status ${provider.configured ? 'published' : ''}`}>{provider.provider === 'mock' ? t('模拟模式') : provider.configured ? t('配置已填写') : t('等待配置')}</span></div><dl className="admin-definition-list"><div><dt>{t('运行提供方')}</dt><dd><code>{provider.provider}</code></dd></div><div><dt>{t('模型名称')}</dt><dd>{provider.model || t('尚未填写')}</dd></div><div><dt>{t('API 地址')}</dt><dd className="admin-break">{provider.api_base || t('尚未填写')}</dd></div><div><dt>{t('服务端密钥')}</dt><dd>{provider.credentials_set ? t('已设置（内容不可查看）') : t('尚未设置')}</dd></div><div><dt>{t('配置完整性')}</dt><dd>{provider.provider === 'mock' ? t('模拟流程可用；真实 API 配置需单独检查') : provider.configured ? t('必要字段已填写；不代表连接已验证') : t('尚未完成必要配置')}</dd></div><div><dt>{t('真实模型质量')}</dt><dd>{t('待真实模型场景评估')}</dd></div></dl></section>}
        <section className="admin-panel admin-provider-guide"><h2>{t('接入步骤')}</h2><ol><li>{t('在后端本机的')} <code>.env</code> {t('填写提供方、API 地址、模型名和密钥。')}</li><li>{t('重启服务，刷新本页确认配置状态。')}</li><li>{t('进入陪伴应用，用自建的合成场景检查上下文、记忆、工具调用和错误处理。')}</li><li>{t('添加人工评审，保存可公开的脱敏效果证据。')}</li></ol><p className="admin-note">{t('真实调用失败会显示错误，不会自动替换为模拟回复。')}</p></section>
      </>}
      {view === 'operations' && <OperationsPanel data={operations} loading={loading} language={language} />}
      <footer className="admin-footer">{t('HarborCompanion · 单人原型管理工作台')} <span>{t('AI 身份披露 / 记忆需确认 / 质量凭证据')}</span></footer>
    </main>
  </div>
}
