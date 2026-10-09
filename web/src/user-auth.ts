import { api, ApiError, getSessionKey } from './api'

export type AuthMode = 'local_demo' | 'accounts'
export type User = {id: string; username: string}
export type UserAuth = {mode: AuthMode; phase: 'checking' | 'demo' | 'signed_out' | 'authenticated'; user: User | null; expiresAt: number | null; epoch: number; backendKey: string}
type AuthResponse = {access_token: string; expires_in: number; user: User}
export type IdentityContext = {epoch: number; backendKey: string}

let auth: UserAuth = {mode: 'local_demo', phase: 'checking', user: null, expiresAt: null, epoch: 0, backendKey: getSessionKey('harbor-user-auth')}
let token = ''
const listeners = new Set<(value: UserAuth) => void>()
const requests = new Set<AbortController>()

export class StaleIdentityError extends Error {
  constructor() {super('Request belongs to an inactive user identity.'); this.name = 'StaleIdentityError'}
}
export function getUserAuth(): UserAuth {return {...auth}}
export function subscribeUserAuth(listener: (value: UserAuth) => void) {listeners.add(listener); return () => {listeners.delete(listener)}}
function publish(value: Partial<UserAuth>) {auth = {...auth, ...value}; listeners.forEach(listener => listener(getUserAuth()))}
export function identityContext(): IdentityContext {return {epoch: auth.epoch, backendKey: auth.backendKey}}
export function identityIsCurrent(context: IdentityContext) {return context.epoch === auth.epoch && context.backendKey === auth.backendKey && context.backendKey === getSessionKey('harbor-user-auth')}

function invalidate(value: Partial<UserAuth>) {
  for (const controller of requests) controller.abort()
  requests.clear(); token = ''
  publish({epoch: auth.epoch + 1, user: null, expiresAt: null, ...value})
}
export function resetUserIdentity() {invalidate({backendKey: getSessionKey('harbor-user-auth'), phase: 'checking'})}

function readToken(): {token: string; expiresAt: number} | null {
  try {
    const stored = JSON.parse(sessionStorage.getItem(auth.backendKey) || 'null')
    return stored && typeof stored.token === 'string' && typeof stored.expiresAt === 'number' && stored.expiresAt > Date.now() ? stored : null
  } catch {return null}
}
function removeToken() {try {sessionStorage.removeItem(auth.backendKey)} catch { /* In-memory logout still completes. */ }}
function validUser(user: User): boolean {return Boolean(user && typeof user.id === 'string' && typeof user.username === 'string')}

async function scopedRequest<T>(path: string, method = 'GET', body?: unknown, bearer?: string): Promise<T> {
  const context = identityContext()
  const controller = new AbortController()
  requests.add(controller)
  try {
    const result = await api<T>(path, method, body, bearer, {signal: controller.signal})
    if (!identityIsCurrent(context)) throw new StaleIdentityError()
    return result
  } catch (error) {
    if (!identityIsCurrent(context)) throw new StaleIdentityError()
    throw error
  } finally {requests.delete(controller)}
}

export async function configureUserMode(mode: AuthMode): Promise<UserAuth> {
  if (mode !== 'local_demo' && mode !== 'accounts') throw new ApiError(0, 'Backend does not expose a supported account mode.')
  const backendKey = getSessionKey('harbor-user-auth')
  if (auth.mode === mode && auth.backendKey === backendKey && (auth.phase === 'authenticated' || auth.phase === 'demo')) return getUserAuth()
  invalidate({mode, backendKey, phase: mode === 'local_demo' ? 'demo' : 'checking'})
  if (mode === 'local_demo') return getUserAuth()
  const stored = readToken()
  if (!stored) {removeToken(); publish({phase: 'signed_out'}); return getUserAuth()}
  try {
    const result = await scopedRequest<{user: User; expires_in: number}>('/auth/me', 'GET', undefined, stored.token)
    if (!validUser(result.user) || !(result.expires_in > 0)) throw new Error('Invalid user authentication response.')
    token = stored.token
    publish({phase: 'authenticated', user: result.user, expiresAt: Date.now() + result.expires_in * 1000})
    return getUserAuth()
  } catch (error) {
    if (error instanceof StaleIdentityError) throw error
    if (error instanceof ApiError && error.status === 401) removeToken()
    publish({phase: 'signed_out'})
    if (!(error instanceof ApiError && error.status === 401)) throw error
    return getUserAuth()
  }
}

export async function authenticateUser(kind: 'login' | 'register', username: string, password: string): Promise<UserAuth> {
  if (auth.mode !== 'accounts') throw new Error('Account authentication is unavailable in local demo mode.')
  const body = kind === 'register' ? {username: username.trim(), password, adult_confirmed: true} : {username: username.trim(), password}
  const result = await scopedRequest<AuthResponse>(`/auth/${kind}`, 'POST', body)
  if (!validUser(result.user) || !result.access_token || !(result.expires_in > 0)) throw new Error('Invalid user authentication response.')
  invalidate({phase: 'checking'})
  token = result.access_token
  const expiresAt = Date.now() + result.expires_in * 1000
  try {sessionStorage.setItem(auth.backendKey, JSON.stringify({token, expiresAt}))} catch { /* The verified user can continue for this page lifetime. */ }
  publish({phase: 'authenticated', user: result.user, expiresAt})
  return getUserAuth()
}

export async function signOutUser(): Promise<boolean> {
  const previousToken = token
  removeToken(); invalidate({phase: 'signed_out'})
  if (!previousToken) return true
  try {await api('/auth/logout', 'POST', undefined, previousToken); return true} catch {return false}
}
export function expireUser() {removeToken(); invalidate({phase: 'signed_out'})}

/** Called only after the authenticated server confirms account erasure. */
export function completeAccountDeletion() {
  for (const key of ['harbor-session', 'harbor-sessions']) {
    try {localStorage.removeItem(getUserSessionKey(key))} catch { /* Identity still clears if device storage is unavailable. */ }
  }
  removeToken(); invalidate({phase: 'signed_out'})
}

/** User bearer tokens are explicit and never substituted into the administrator plane. */
export async function userApi<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  if (path.startsWith('/admin')) throw new Error('Use the separate administrator authentication plane.')
  if (auth.phase === 'checking') throw new StaleIdentityError()
  if (auth.mode === 'accounts' && (auth.phase !== 'authenticated' || !token)) throw new ApiError(401, '用户登录已失效，请重新登录。')
  const context = identityContext()
  try {return await scopedRequest<T>(path, method, body, auth.mode === 'accounts' ? token : undefined)} catch (error) {
    if (identityIsCurrent(context) && error instanceof ApiError && error.status === 401 && auth.mode === 'accounts') expireUser()
    throw error
  }
}

export function getUserSessionKey(baseKey: string) {
  const base = getSessionKey(baseKey)
  return auth.mode === 'accounts' ? `${base}@user:${encodeURIComponent(auth.user?.id || 'signed-out')}` : base
}
