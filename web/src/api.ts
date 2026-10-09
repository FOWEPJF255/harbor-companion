import { isNativeApp } from './AppInstall'
import { readLanguage, type Language } from './i18n'

type Connection = {baseUrl: string; accessToken: string}
const STORAGE_KEY = 'harbor-connection-v1'

export class ApiError extends Error {
  status: number
  sourceMessage: string
  trace: Array<Record<string, unknown>> = []
  failureReason = ''
  constructor(status: number, message: string) {super(localizeApiMessage(message)); this.name = 'ApiError'; this.status = status; this.sourceMessage = message}
}

const englishMessages: Record<string, string> = {
  '请输入完整的后端 HTTPS 地址。': 'Enter the full HTTPS backend address.',
  '后端地址应使用 HTTPS，不能包含密钥、账号或查询参数。': 'Use HTTPS without credentials or query parameters.',
  '手机 APP 需要手机可访问的后端地址；localhost 指向手机自身。': 'The phone needs a reachable backend; localhost refers to the phone itself.',
  '演示访问码过长，请检查输入。': 'The demo access code is too long.',
  '请先在“我的”配置手机可访问的 HTTPS 后端地址。': 'Configure a reachable HTTPS backend in Me first.',
  '输入不符合要求，请检查各字段；管理员密码至少 12 位。': 'Check the input fields. Administrator passwords need at least 12 characters.',
  '输入不符合要求，请检查各字段。': 'Check the input fields and try again.',
  '服务暂时不可用，请稍后重试。': 'Service unavailable. Please try again later.',
  '连接等待超时，请重试。聊天重试会沿用原请求编号，避免重复保存。': 'Connection timed out. Retrying chat keeps the same request ID to prevent duplicate turns.',
  '无法连接后端，请检查地址、网络和后端是否启动。': 'Cannot reach the backend. Check the address, network, and running service.',
  '当前离线，请恢复网络后重试。消息没有在离线时排队发送。': 'You are offline. Reconnect and retry; messages have not been queued.',
  '用户登录已失效，请重新登录。': 'Your user login has expired. Sign in again.',
}

export function localizeApiMessage(message: string, language: Language = readLanguage()): string {
  const original = Object.entries(englishMessages).find(([, english]) => english === message)?.[0] || message
  const chinese = errors[original] || original
  if (language === 'zh') return chinese
  return englishMessages[chinese] || Object.entries(errors).find(([, translated]) => translated === chinese)?.[0] || chinese
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
  'User login required.': '用户登录已失效，请重新登录。',
  'Invalid user credentials.': '用户名或密码不正确。',
  'Public registration is disabled.': '自助注册已关闭，请联系运营方开通账号。',
  'Invalid authentication input.': '登录字段不符合要求：用户名需为 3–40 位字母、数字、下划线、点或连字符；密码需为 12–128 位。',
  'Adult confirmation is required.': '请先确认已满 18 岁。',
  'Unable to register using these details.': '无法使用这些资料注册，请检查输入或联系运营方。',
  'Too many authentication attempts; try again later.': '登录尝试较多，请稍后再试。',
  'Authentication is temporarily unavailable.': '账户服务暂时不可用，请稍后重试。',
  'Backend does not expose a supported account mode.': '后端未返回受支持的账户模式，请更新后端服务。',
  'Invalid user authentication response.': '后端登录响应不完整，请联系运营方检查账户服务。',
  'Account authentication is unavailable in local demo mode.': '本机演示模式不提供普通用户账户登录。',
  'Current password is incorrect.': '当前密码不正确，请重新输入；登录仍然保留。',
  'Invalid account data input.': '账户数据操作字段不符合要求：密码需为 12–128 位，注销还需准确输入 DELETE。',
  'Account deletion requires the exact confirmation DELETE.': '请准确输入 DELETE 后再确认永久注销。',
  'Account data controls require account mode.': '账户导出和注销仅适用于账户模式。',
  'Account data management requires account mode.': '账户导出和注销仅适用于账户模式。',
  'Account export exceeds the 16 MiB limit; no partial file was returned.': '导出资料超过 16 MiB 上限，没有返回不完整文件。请联系运营方处理。',
  'Account export is busy; try again later.': '资料导出任务已满，请稍后重试。',
  'Account export could not be completed; no partial file was returned.': '账户导出未完成，没有返回不完整文件，请稍后重试。',
  'Account deletion could not be completed; no data was deleted.': '账户注销未完成，没有删除数据，请稍后重试。',
  'Account deletion was not confirmed.': '尚未收到账户注销成功确认，请检查连接后再确认账户状态。',
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
  'Memory source session not found': '共享记忆来源会话已不存在，请重新选择。',
  'Request ID was already used for a different message': '这个请求编号已用于另一条消息，请重新发送。',
  'Unsupported or unsafe analysis question; use synthetic demo topics only.': '暂不支持这个分析问题；请查询合成样本的情绪、工具结果、延迟或失败归因。',
  'Synthetic analysis timed out; no private data was accessed.': '合成数据分析超时，没有访问私人会话数据。',
  'Model could not complete the turn. No mock fallback or half-turn was saved.': '模型未完成这一轮。请检查 API 配置或稍后重试；系统没有用模拟回复替代。',
  'Adult confirmation is required for this prototype.': '请确认已满 18 岁后再开始。',
  'Memory limit reached; remove older memories first.': '这个会话已达到记忆上限，请先整理旧记忆。',
  'Turn does not belong to this session': '请选择当前会话中的回复记录。',
  'Invalid session cursor': '会话分页入口已失效，请刷新列表。',
  'Too many session handles': '会话入口数量过多，请整理本设备记录。',
  'Session limit reached; remove older sessions first.': '已达到当前账户的会话上限，请先删除不再需要的会话。',
  'Message must not be blank': '请填写非空消息后再发送。',
  'Memory must not be blank': '请填写非空记忆后再保存。',
  'This session is busy; try again later.': '当前会话正在处理其他请求，请稍后重试。',
  'Request budget unavailable; try again later.': '当前请求额度暂不可用，请稍后重试。',
  'Chat request limit reached; try again in one minute.': '本分钟请求较多，请一分钟后再试。',
  'All model run slots are busy; try again later.': '模型处理位置暂时已满，请稍后重试。',
}

export async function api<T>(path: string, method = 'GET', body?: unknown, token?: string, options: {signal?: AbortSignal} = {}): Promise<T> {
  const connection = getConnection()
  const base = validateBase(connection.baseUrl)
  if (isNativeApp() && !base) throw new ApiError(0, '请先在“我的”配置手机可访问的 HTTPS 后端地址。')
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  if (connection.accessToken) headers['X-Harbor-Access'] = connection.accessToken
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  else options.signal?.addEventListener('abort', abort, {once: true})
  const timer = window.setTimeout(() => controller.abort(), 60_000)
  try {
    const response = await fetch(`${base}/api${path}`, {method, headers, signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body), credentials: 'omit', cache: 'no-store'})
    if (!response.ok) {
      const detail = await response.json().catch(() => ({detail: ''}))
      const message = typeof detail.detail === 'string'
        ? (errors[detail.detail] || (response.status === 401 ? path.startsWith('/admin') ? '管理员登录已失效，请重新登录。' : '用户登录已失效，请重新登录。' : detail.detail))
        : path.startsWith('/admin') ? '输入不符合要求，请检查各字段；管理员密码至少 12 位。' : '输入不符合要求，请检查各字段。'
      const error = new ApiError(response.status, message || '服务暂时不可用，请稍后重试。')
      if (Array.isArray(detail.trace)) error.trace = detail.trace
      if (typeof detail.failure_reason === 'string') error.failureReason = detail.failure_reason
      throw error
    }
    return await response.json() as T
  } catch (issue) {
    if (issue instanceof ApiError) throw issue
    if (controller.signal.aborted) throw new ApiError(408, '连接等待超时，请重试。聊天重试会沿用原请求编号，避免重复保存。')
    throw new ApiError(0, navigator.onLine ? '无法连接后端，请检查地址、网络和后端是否启动。' : '当前离线，请恢复网络后重试。消息没有在离线时排队发送。')
  } finally {
    window.clearTimeout(timer)
    options.signal?.removeEventListener('abort', abort)
  }
}
