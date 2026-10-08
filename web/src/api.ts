import { isNativeApp } from './AppInstall'

type Connection = {baseUrl: string; accessToken: string}
const STORAGE_KEY = 'harbor-connection-v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {super(message); this.name = 'ApiError'; this.status = status}
}

function validateBase(value: string): string {
  const raw = value.trim().replace(/\/+$/, '')
  if (!raw) return ''
  let url: URL
  try {url = new URL(raw)} catch {throw new ApiError(0, '请输入完整的后端 HTTPS 地址。')}
  const loopback = url.hostname === 'localhost' || url.hostname.endsWith('.localhost')
    || /^127\./.test(url.hostname) || url.hostname === '[::1]'
  if ((url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback && !isNativeApp()))
    || url.username || url.password || url.search || url.hash) {
    throw new ApiError(0, '后端地址应使用 HTTPS，不能包含密钥、账号或查询参数。')
  }
  if (isNativeApp() && loopback) throw new ApiError(0, '手机 APP 需要手机可访问的后端地址；localhost 指向手机自身。')
  return url.toString().replace(/\/+$/, '')
}

export function getConnection(): Connection {
  let stored: Partial<Connection> = {}
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}')
    stored = value && typeof value === 'object' ? value : {}
  } catch { /* Storage may be unavailable. */ }
  return {baseUrl: typeof stored.baseUrl === 'string' ? stored.baseUrl : (import.meta.env.VITE_API_BASE_URL || ''),
    accessToken: typeof stored.accessToken === 'string' ? stored.accessToken : ''}
}

export function setConnection(connection: Connection) {
  const baseUrl = validateBase(connection.baseUrl)
  if (connection.accessToken.length > 256) throw new ApiError(0, '演示访问码过长，请检查输入。')
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({baseUrl, accessToken: connection.accessToken.trim()}))
}

export function clearConnection() {sessionStorage.removeItem(STORAGE_KEY)}

/** Capability handles must stay partitioned when the user changes backend services. */
export function getSessionKey(baseKey: string): string {
  const base = getConnection().baseUrl.trim().replace(/\/+$/, '')
  return base ? `${baseKey}@${encodeURIComponent(base)}` : baseKey
}

const errors: Record<string, string> = {
  'Administrator login required.': '管理员登录已失效，请重新登录。',
  'Invalid administrator credentials.': '管理员账号或密码不正确。',
  'Initialize the administrator on the server\'s localhost browser.': '请在后端服务器本机浏览器初始化管理员。',
  'Administrator is already initialized; use login.': '管理员已经创建，请使用登录。',
  'Too many login attempts; try again in one minute.': '登录尝试较多，请一分钟后再试。',
  'Demo access code is required.': '此后端需要演示访问码，请在“我的”连接设置中填写。',
  'Origin not allowed for this demo.': '当前 APP / 网页来源未加入后端允许列表，请检查部署配置。',
  'This prototype is restricted to configured hosts.': '当前域名未加入后端允许列表。',
  'Session not found': '会话不存在，可能已在另一端删除。',
  'Character not found': '角色不存在。',
  'Character is not available': '这个角色已归档，请选择其他角色开启新会话。',
  'Memory not found': '这条记忆已不存在，请刷新后重试。',
  'Model could not complete the turn. No mock fallback or half-turn was saved.': '模型未完成这一轮。请检查 API 配置或稍后重试；系统没有用模拟回复替代。',
  'Adult confirmation is required for this prototype.': '请确认已满 18 岁后再开始。',
  'Memory limit reached; remove older memories first.': '这个会话已达到记忆上限，请先整理旧记忆。',
  'Turn does not belong to this session': '请选择当前会话中的回复记录。',
}

export async function api<T>(path: string, method = 'GET', body?: unknown, token?: string): Promise<T> {
  const connection = getConnection()
  const base = validateBase(connection.baseUrl)
  if (isNativeApp() && !base) throw new ApiError(0, '请先在“我的”配置手机可访问的 HTTPS 后端地址。')
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  if (connection.accessToken) headers['X-Harbor-Access'] = connection.accessToken
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 60_000)
  try {
    const response = await fetch(`${base}/api${path}`, {method, headers, signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body), credentials: 'omit', cache: 'no-store'})
    if (!response.ok) {
      const detail = await response.json().catch(() => ({detail: ''}))
      const message = typeof detail.detail === 'string'
        ? (errors[detail.detail] || (response.status === 401 ? '管理员登录已失效，请重新登录。' : detail.detail))
        : '输入不符合要求，请检查各字段；管理员密码至少 12 位。'
      throw new ApiError(response.status, message || '服务暂时不可用，请稍后重试。')
    }
    return await response.json() as T
  } catch (issue) {
    if (issue instanceof ApiError) throw issue
    if (controller.signal.aborted) throw new ApiError(408, '连接等待超时，请重试。聊天重试会沿用原请求编号，避免重复保存。')
    throw new ApiError(0, navigator.onLine ? '无法连接后端，请检查地址、网络和后端是否启动。' : '当前离线，请恢复网络后重试。消息没有在离线时排队发送。')
  } finally {
    window.clearTimeout(timer)
  }
}
