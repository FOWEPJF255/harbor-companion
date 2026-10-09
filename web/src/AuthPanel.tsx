import { useEffect, useState, type FormEvent } from 'react'
import { authenticateUser, StaleIdentityError } from './user-auth'
import { localizeApiMessage } from './api'
import { translator, type Language } from './i18n'

export function AuthPanel({language, registrationEnabled}: {language: Language; registrationEnabled: boolean}) {
  const t = translator(language)
  const [kind, setKind] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [adult, setAdult] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!registrationEnabled && kind === 'register') {
      setKind('login'); setError(''); setPassword(''); setConfirmation('')
    }
  }, [registrationEnabled, kind])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!adult || busy || (kind === 'register' && !registrationEnabled)) return
    if (kind === 'register' && password !== confirmation) {setError(t('passwordMismatch')); return}
    setBusy(true); setError('')
    try {await authenticateUser(kind, username, password)} catch (issue) {
      if (!(issue instanceof StaleIdentityError)) setError(issue instanceof Error ? issue.message : t('disconnected'))
    } finally {setPassword(''); setConfirmation(''); setBusy(false)}
  }

  return <section className="user-auth-panel" aria-label={t('accountTitle')}>
    <div className="section-title"><h3>{t(kind === 'login' ? 'signIn' : 'register')}</h3><span>{t('accountMode')}</span></div>
    <p className="micro">{t('accountSigninHint')}</p>
    {error && <p className="auth-error" role="alert">{localizeApiMessage(error, language)}</p>}
    <p className="micro">{t('accountCredentialHint')}</p>
    <form onSubmit={submit} className="user-auth-form"><label htmlFor="user-username">{t('username')}</label><input id="user-username" autoComplete="username" minLength={3} maxLength={40} pattern="[A-Za-z0-9_.-]+" value={username} disabled={busy} required onChange={event => setUsername(event.target.value)}/><label htmlFor="user-password">{t('password')}</label><input id="user-password" type="password" autoComplete={kind === 'register' ? 'new-password' : 'current-password'} minLength={12} maxLength={128} value={password} disabled={busy} required onChange={event => setPassword(event.target.value)}/>{kind === 'register' && <><label htmlFor="user-confirmation">{t('confirmPassword')}</label><input id="user-confirmation" type="password" autoComplete="new-password" maxLength={128} value={confirmation} disabled={busy} required onChange={event => setConfirmation(event.target.value)}/></>}<label className="adult-check"><input type="checkbox" checked={adult} disabled={busy} onChange={event => setAdult(event.target.checked)}/><span>{t('accountAdult')}</span></label><button className="primary" disabled={busy || !adult} type="submit">{t(busy ? 'processing' : kind === 'login' ? 'signIn' : 'register')}<span>↗</span></button></form>
    {registrationEnabled ? <button className="text-button" type="button" disabled={busy} onClick={() => {setKind(kind === 'login' ? 'register' : 'login'); setError(''); setPassword(''); setConfirmation('')}}>{t(kind === 'login' ? 'register' : 'signIn')}</button> : <p className="micro">{t('registrationClosed')}</p>}
    <p className="micro">{t('credentialsCleared')}</p>
  </section>
}
