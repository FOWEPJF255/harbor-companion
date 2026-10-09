import { useEffect, useRef, useState } from 'react'
import { ApiError, localizeApiMessage } from '../api'
import type { Language } from '../i18n'
import { profileSections, sectionNames, type ProfileSnapshot } from '../persona'

type Props = {
  characterId: string; characterName: string; currentRevision: number; language: Language; disabled: boolean
  request: <T>(path: string, method?: string, body?: unknown) => Promise<T>
  onClose: () => void; onRestored: () => Promise<void>
}
export default function PersonaHistory({characterId, characterName, currentRevision, language, disabled, request, onClose, onRestored}: Props) {
  const en = language === 'en'
  const [items, setItems] = useState<ProfileSnapshot[]>([])
  const [chosen, setChosen] = useState<number | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [restored, setRestored] = useState(false)
  const [reload, setReload] = useState(0)
  const active = useRef(true)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    let cancelled = false
    active.current = true
    heading.current?.focus()
    setBusy(true); setError(''); setItems([]); setChosen(null); setConfirmed(false)
    void request<{items: ProfileSnapshot[]}>(`/characters/${encodeURIComponent(characterId)}/revisions`).then(result => {
      if (!cancelled && active.current) {setItems(result.items); setChosen(result.items[0]?.revision ?? null)}
    }).catch(issue => {if (!cancelled && active.current) setError(issue instanceof ApiError ? issue.sourceMessage : issue instanceof Error ? issue.message : 'Service unavailable. Please try again later.')}).finally(() => {if (!cancelled && active.current) setBusy(false)})
    return () => {cancelled = true; active.current = false}
  }, [characterId, reload, request])
  async function restore() {
    if (!confirmed || chosen === null || busy || disabled) return
    setBusy(true); setError(''); setRestored(false)
    try {
      await request(`/characters/${encodeURIComponent(characterId)}/restore`, 'POST', {revision: chosen})
      if (!active.current) return
      setConfirmed(false); setRestored(true)
      await onRestored()
      if (active.current) setReload(value => value + 1)
    } catch (issue) {if (active.current) setError(issue instanceof ApiError ? issue.sourceMessage : issue instanceof Error ? issue.message : 'Service unavailable. Please try again later.')}
    finally {if (active.current) setBusy(false)}
  }
  const snapshot = items.find(item => item.revision === chosen)
  return <section className="admin-panel admin-persona-history">
    <div className="admin-panel-heading"><h2 tabIndex={-1} ref={heading}>{characterName} · {en ? 'Revision history' : '版本历史'}</h2><button type="button" className="admin-text-button" disabled={busy} onClick={onClose}>{en ? 'Close' : '关闭'}</button></div>
    <p className="admin-note">{en ? `Current character revision: ${currentRevision}. Restore copies all historical character fields, including published/archived status, into a new revision. It does not overwrite history or existing sessions.` : `当前角色版本：${currentRevision}。恢复会把该版本全部角色字段（含发布 / 归档状态）复制为新版本，不覆盖历史或已有会话。`}</p>
    {error && <div className="admin-alert admin-alert-error" role="alert">{localizeApiMessage(error, language)} <button type="button" className="admin-text-button" disabled={busy} onClick={() => setReload(value => value + 1)}>{en ? 'Reload history' : '重新读取历史'}</button></div>}
    {restored && <p className="admin-alert admin-alert-success" role="status">{en ? 'Restored into a new revision. Existing sessions still keep their own snapshots.' : '已恢复为一个新版本。已有会话仍保留原来的档案快照。'}</p>}
    {busy && <p className="admin-note" role="status">{en ? 'Working…' : '正在处理…'}</p>}
    <label className="admin-revision-select">{en ? 'Inspect revision' : '查看版本'}<select value={chosen ?? ''} disabled={busy || disabled || !items.length} onChange={event => {setChosen(Number(event.target.value)); setConfirmed(false)}}>{items.map(item => <option key={item.revision} value={item.revision}>v{item.revision} · {item.name}{item.created ? ` · ${new Date(item.created).toLocaleString(language === 'en' ? 'en-US' : 'zh-CN')}` : ''}</option>)}</select></label>
    {snapshot && <div className="admin-revision-preview"><p className="admin-persona-fiction">{en ? 'Fictional AI character settings, not a real biography.' : '虚构 AI 角色设定，不是真人的经历。'}</p>{typeof snapshot.enabled === 'boolean' && <p>{en ? 'Saved publication status' : '当时发布状态'}: {snapshot.enabled ? (en ? 'Published' : '已发布') : (en ? 'Archived' : '已归档')}</p>}<details><summary>{en ? 'Saved public copy (original language)' : '当时公开文案（原文）'}</summary><p>{snapshot.tagline}</p><p>{snapshot.description}</p><p>{snapshot.greeting}</p><small>{en ? 'The historical internal character prompt is also restored, but not displayed in this public-copy preview.' : '历史内部角色提示词也会恢复，这里只预览公开文案。'}</small></details>{snapshot.profile ? <><p>{en ? 'Fictional age' : '设定年龄'}: {snapshot.profile.age}</p>{profileSections.map(section => <details key={section}><summary>{sectionNames[language][section]}</summary><p>{snapshot.profile!.sections[section][language]}</p></details>)}</> : <p>{en ? 'Legacy version: no structured profile was recorded.' : '旧版本：当时未记录结构化档案。'}</p>}</div>}
    {!items.length && !busy && <p className="admin-note">{en ? 'No revision records returned.' : '没有读取到版本记录。'}</p>}
    <label className="admin-checkbox"><input type="checkbox" checked={confirmed} disabled={busy || disabled || !snapshot} onChange={event => setConfirmed(event.target.checked)}/><span>{en ? `I explicitly choose to restore all character fields from revision ${chosen ?? '—'} into a new version, including its published/archived status. Existing sessions will not change.` : `我明确选择将版本 ${chosen ?? '—'} 的全部角色字段恢复为新版本，包括当时的发布 / 归档状态。已有会话不会改变。`}</span></label>
    <button type="button" className="admin-button admin-button-primary" disabled={!confirmed || !snapshot || busy || disabled} onClick={() => void restore()}>{en ? 'Restore selected revision' : '恢复选中的版本'}</button>
  </section>
}
