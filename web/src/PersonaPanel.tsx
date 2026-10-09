import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { api, ApiError, localizeApiMessage } from './api'
import { identityContext, identityIsCurrent, StaleIdentityError, userApi } from './user-auth'
import type { Language } from './i18n'
import { personaTranslator, profileSections, sectionNames, type ProfileSection, type ProfileSnapshot, type ProfileTarget } from './persona'
import './persona.css'

type Props = {
  target: ProfileTarget | null; language: Language; currentSessionId?: string; busy: boolean
  portrait?: ReactNode
  onClose: () => void; onChoose: (characterId: string) => void; onAsk: (question: string) => Promise<boolean>; onLanguage: (language: Language) => void
}

export default function PersonaPanel({target, language, currentSessionId, busy, onClose, onChoose, onAsk, onLanguage, portrait}: Props) {
  const p = personaTranslator(language)
  const [snapshot, setSnapshot] = useState<ProfileSnapshot | null>(null)
  const [section, setSection] = useState<ProfileSection>('growth')
  const [questions, setQuestions] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [askFailed, setAskFailed] = useState(false)
  const [reload, setReload] = useState(0)
  const dialog = useRef<HTMLElement>(null)
  const back = useRef<HTMLButtonElement>(null)
  const sequence = useRef(0)
  const composing = useRef(false)
  const id = useId()
  const targetKey = target ? `${target.kind}:${target.id}` : ''
  const question = questions[targetKey] || ''
  const canAsk = target?.kind === 'session' && target.id === currentSessionId

  useEffect(() => {
    const requestId = ++sequence.current
    setSnapshot(null); setError(''); setAskFailed(false); setSection('growth')
    if (!target) return
    const context = identityContext()
    setLoading(true)
    const path = target.kind === 'session' ? `/sessions/${encodeURIComponent(target.id)}/profile` : `/characters/${encodeURIComponent(target.id)}/profile`
    const request = target.kind === 'session' ? userApi<ProfileSnapshot>(path) : api<ProfileSnapshot>(path)
    void request.then(result => {
      if (requestId === sequence.current && identityIsCurrent(context)) setSnapshot(result)
    }).catch(issue => {
      if (requestId === sequence.current && identityIsCurrent(context) && !(issue instanceof StaleIdentityError)) setError(issue instanceof ApiError ? issue.sourceMessage : issue instanceof Error ? issue.message : 'Service unavailable. Please try again later.')
    }).finally(() => {if (requestId === sequence.current && identityIsCurrent(context)) setLoading(false)})
    return () => {sequence.current += 1}
  }, [targetKey, reload])

  useEffect(() => {
    if (!target) return
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    back.current?.focus()
    return () => {if (previous?.isConnected) previous.focus()}
  }, [targetKey])

  function keyboard(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') {event.preventDefault(); onClose()}
    if (event.key !== 'Tab') return
    const controls = [...(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),select:not(:disabled),input:not(:disabled),textarea:not(:disabled),[tabindex="0"]') || [])].filter(control => control.tabIndex >= 0)
    if (!controls.length) return
    const first = controls[0], last = controls[controls.length - 1]
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last.focus()}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus()}
  }

  if (!target) return null
  return <div className="persona-backdrop" onClick={event => {if (event.target === event.currentTarget) onClose()}}>
    <section className="persona-drawer" role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} ref={dialog} onKeyDown={keyboard}>
      <header className="persona-heading"><button type="button" className="text-button" ref={back} onClick={onClose} aria-label={p('close')}>← {p('back')}</button><h2 id={`${id}-title`}>{p('profile')}</h2><label className="persona-language"><span className="sr-only">{language === 'en' ? 'Profile language' : '档案语言'}</span><select value={language} onChange={event => onLanguage(event.target.value as Language)}><option value="zh">中文</option><option value="en">EN</option></select></label><span>{p('revision')} {snapshot?.revision ?? '—'}</span></header>
      <div className="persona-identity">{portrait || <span className="persona-sigil" aria-hidden="true">✧</span>}<div><h3>{snapshot?.name || target.name}</h3><small>{p(target.kind === 'session' ? 'snapshot' : 'publicVersion')}{snapshot?.profile && ` · ${p('age')} ${snapshot.profile.age}`}</small></div></div>
      <p className="persona-fiction">{p('fiction')}</p>
      {target.kind === 'session' && <p className="persona-version-note">{p('frozen')}</p>}
      {loading ? <p className="persona-state" role="status">{p('loading')}</p> : error ? <div className="persona-state" role="alert"><p>{localizeApiMessage(error, language)}</p><button className="secondary" type="button" onClick={() => setReload(value => value + 1)}>{p('retry')}</button></div> : snapshot?.profile ? <>
        <div className="persona-tabs" role="tablist" aria-label={p('sections')}>{profileSections.map(key => <button type="button" key={key} role="tab" id={`${id}-tab-${key}`} aria-selected={section === key} aria-controls={`${id}-content`} tabIndex={section === key ? 0 : -1} className={section === key ? 'active' : ''} onClick={() => setSection(key)} onKeyDown={event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
          event.preventDefault()
          const position = profileSections.indexOf(key)
          const next = event.key === 'Home' ? profileSections[0] : event.key === 'End' ? profileSections[5] : profileSections[(position + (event.key === 'ArrowRight' ? 1 : 5)) % 6]
          setSection(next); document.getElementById(`${id}-tab-${next}`)?.focus()
        }}>{sectionNames[language][key]}</button>)}</div>
        <div className="persona-content" role="tabpanel" id={`${id}-content`} aria-labelledby={`${id}-tab-${section}`} tabIndex={0}><h4>{sectionNames[language][section]}</h4><p>{snapshot.profile.sections[section][language]}</p><small>{p('translations')}</small></div>
      </> : <div className="persona-content"><p>{p('legacy')}</p></div>}
      <form className="persona-ask" onSubmit={event => {event.preventDefault(); if (!canAsk || busy || composing.current || !question.trim()) return; setAskFailed(false); const key = targetKey; void onAsk(question).then(sent => {if (sent) setQuestions(previous => ({...previous, [key]: ''})); else setAskFailed(true)})}}>
        <label htmlFor={`${id}-question`}>{p('ask')}</label><textarea id={`${id}-question`} aria-label={p('question')} rows={2} maxLength={2000} value={question} disabled={busy} placeholder={p('placeholder')} onCompositionStart={() => {composing.current = true}} onCompositionEnd={() => {composing.current = false}} onChange={event => setQuestions(previous => ({...previous, [targetKey]: event.target.value}))}/>
        <p>{p(canAsk ? 'currentOnly' : 'startFirst')}</p>
        {askFailed && <p className="persona-ask-error" role="alert">{p('askError')}</p>}
        {canAsk ? <button className="primary" type="submit" disabled={busy || !question.trim() || loading}>{p('send')} ↗</button> : <button className="secondary" type="button" disabled={busy || !snapshot} onClick={() => onChoose(snapshot!.character_id)}>{p('choose')} ↗</button>}
      </form>
    </section>
  </div>
}
