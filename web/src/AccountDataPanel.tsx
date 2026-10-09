import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, localizeApiMessage } from './api'
import { translator, type Language, type TextKey } from './i18n'
import { completeAccountDeletion, identityContext, identityIsCurrent, StaleIdentityError, userApi } from './user-auth'

/** Account data stays in the request/download lifetime, never application storage. */
export function AccountDataPanel({language, disabled = false, onDeleted}: {language: Language; disabled?: boolean; onDeleted: () => void}) {
  const t = translator(language)
  const exportPassword = useRef<HTMLInputElement>(null)
  const deletePassword = useRef<HTMLInputElement>(null)
  const mounted = useRef(false)
  const [action, setAction] = useState<'export' | 'delete' | null>(null)
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState<TextKey | null>(null)

  function clearPasswords() {
    if (exportPassword.current) exportPassword.current.value = ''
    if (deletePassword.current) deletePassword.current.value = ''
  }

  useEffect(() => {
    mounted.current = true
    return () => {mounted.current = false; clearPasswords()}
  }, [])

  async function exportAccount(event: FormEvent) {
    event.preventDefault()
    if (action || disabled || !exportPassword.current?.value) return
    const context = identityContext()
    const current = () => mounted.current && identityIsCurrent(context)
    setAction('export'); setError(''); setNotice(null)
    try {
      const data = await userApi<unknown>('/account/export', 'POST', {password: exportPassword.current.value})
      if (!current()) return
      const file = new Blob([JSON.stringify(data)], {type: 'application/json;charset=utf-8'})
      if (file.size > 16 * 1024 * 1024) throw new ApiError(413, 'Account export exceeds the 16 MiB limit; no partial file was returned.')
      const url = URL.createObjectURL(file)
      const link = document.createElement('a')
      try {
        link.href = url; link.download = 'harbor-account-export.json'; link.hidden = true
        document.body.appendChild(link); link.click()
      } finally {link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)}
      setNotice('accountExportStarted')
    } catch (issue) {
      if (current() && !(issue instanceof StaleIdentityError)) setError(issue instanceof ApiError ? issue.sourceMessage : issue instanceof Error ? issue.message : t('disconnected'))
    } finally {
      clearPasswords()
      if (current()) setAction(null)
    }
  }

  async function deleteAccount(event: FormEvent) {
    event.preventDefault()
    if (action || disabled || confirmation !== 'DELETE' || !deletePassword.current?.value) return
    const context = identityContext()
    const current = () => mounted.current && identityIsCurrent(context)
    setAction('delete'); setError(''); setNotice(null)
    try {
      const result = await userApi<{ok: boolean}>('/account/me', 'DELETE', {password: deletePassword.current.value, confirmation: 'DELETE'})
      if (!current()) return
      if (result.ok !== true) throw new ApiError(0, 'Account deletion was not confirmed.')
      clearPasswords(); setConfirmation('')
      completeAccountDeletion()
      onDeleted()
    } catch (issue) {
      if (current() && !(issue instanceof StaleIdentityError)) setError(issue instanceof ApiError ? issue.sourceMessage : issue instanceof Error ? issue.message : t('disconnected'))
    } finally {
      clearPasswords()
      if (current()) setAction(null)
    }
  }

  const blocked = disabled || action !== null
  return <details className="account-data-panel">
    <summary>{t('accountDataTitle')}<span aria-hidden="true">⌄</span></summary>
    <p className="micro">{t('accountDataScope')}</p>
    {error && <p className="auth-error" role="alert">{localizeApiMessage(error, language)}</p>}
    {notice && <p className="connection-notice" role="status">{t(notice)}</p>}
    <section aria-labelledby="account-export-title"><h3 id="account-export-title">{t('accountExportTitle')}</h3><p>{t('accountExportHint')}</p>
      <form className="account-data-form" onSubmit={exportAccount} aria-busy={action === 'export'}>
        <label htmlFor="export-current-password">{t('accountCurrentPassword')}</label><input ref={exportPassword} id="export-current-password" type="password" autoComplete="current-password" minLength={12} maxLength={128} required disabled={blocked}/>
        <button className="secondary" type="submit" disabled={blocked}>{t(action === 'export' ? 'accountExporting' : 'accountExport')}</button>
      </form><p className="micro">{t('accountExportPrivate')}</p><p className="micro">{t('accountDownloadBoundary')}</p>
    </section>
    <section className="account-delete-section" aria-labelledby="account-delete-title"><h3 id="account-delete-title">{t('accountDeleteTitle')}</h3><p>{t('accountDeleteConsequences')}</p><p className="micro">{t('accountDeleteBoundary')}</p>
      <form className="account-data-form" onSubmit={deleteAccount} aria-busy={action === 'delete'}>
        <label htmlFor="delete-current-password">{t('accountCurrentPassword')}</label><input ref={deletePassword} id="delete-current-password" type="password" autoComplete="current-password" minLength={12} maxLength={128} required disabled={blocked}/>
        <label htmlFor="account-delete-confirmation">{t('accountDeleteConfirmation')}</label><input id="account-delete-confirmation" value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" autoCapitalize="off" spellCheck={false} maxLength={6} required disabled={blocked} aria-describedby="account-delete-warning"/>
        <p className="micro" id="account-delete-warning">{t('accountDeleteWarning')}</p><button className="danger account-delete-button" type="submit" disabled={blocked || confirmation !== 'DELETE'}>{t(action === 'delete' ? 'accountDeleting' : 'accountDelete')}</button>
      </form>
    </section>
  </details>
}
