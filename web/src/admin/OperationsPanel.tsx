import type { Language } from '../i18n'
import { adminTranslator } from './i18n'
import type { Operations } from './types'

type OperationsPanelProps = { data: Operations | null; loading: boolean; language: Language }

const actions: Record<string, string> = {
  session_created: '建立会话', session_deleted: '删除会话', history_deleted: '清空会话历史',
  run_completed: '完成一次运行', run_failed: '运行失败', synthetic_analysis: '分析合成样本',
  memory_added: '添加已确认记忆', memory_corrected: '纠正已确认记忆', memory_approve: '确认记忆提议',
  memory_delete: '删除记忆', review_access_changed: '修改审阅授权', reviewer_read: '查看已授权原文',
  review_added: '记录人工评审', user_provisioned: '开通用户账户',
}
const reasons: Record<string, string> = {
  provider_or_timeout: '提供方错误或超时', provider_error: '提供方调用失败',
  provider_or_step_failure: '提供方或步骤执行失败',
  run_timeout: '运行等待超时', provider_timeout: '提供方等待超时',
  invalid_model_output: '模型输出格式不符', step_budget_exhausted: '步骤预算已用尽',
}

export default function OperationsPanel({ data, loading, language }: OperationsPanelProps) {
  const t = adminTranslator(language)
  const time = (value: string) => {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? t('时间未记载') : date.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN', { hour12: false })
  }
  const count = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value.toLocaleString(language === 'en' ? 'en-US' : 'zh-CN') : t('未提供')
  const identifier = (value: string | null) => {
    if (!value || !/^[A-Za-z0-9:_-]{1,128}$/.test(value)) return '—'
    return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value
  }
  const actor = (value: string | null) => {
    if (!value) return t('未记录主体')
    if (value.startsWith('admin:')) return t('管理员')
    if (value.startsWith('user:')) return `${t('用户')} · ${identifier(value.slice(5))}`
    if (/^[a-f0-9]{32}$/.test(value)) return `${t('用户')} · ${identifier(value)}`
    return t('本机演示主体')
  }
  const metadata = (entry: Record<string, unknown>) => {
    const values: string[] = []
    // Render known scalar metadata only; never stringify arbitrary event payloads.
    if (typeof entry.provider === 'string' && /^[a-z0-9_-]{1,40}$/i.test(entry.provider)) values.push(`${t('提供方')} ${entry.provider}`)
    for (const [key, label, suffix] of [['duration_ms', '执行耗时', ' ms'], ['total_tokens', '估算或返回 token', ''], ['count', '记录数量', '']] as const) {
      if (typeof entry[key] === 'number' && Number.isFinite(entry[key]) && (entry[key] as number) >= 0) values.push(`${t(label)} ${count(entry[key])}${suffix}`)
    }
    if (typeof entry.allowed === 'boolean') values.push(entry.allowed ? t('已授予审阅权限') : t('已撤回审阅权限'))
    if (typeof entry.run_id === 'string') values.push(`${t('运行')} ${identifier(entry.run_id)}`)
    if (typeof entry.reason === 'string') values.push(reasons[entry.reason] ? t(reasons[entry.reason]) : t('失败类型已记录'))
    return values.length ? values.join(' · ') : '—'
  }

  return <>
    <div className="admin-callout"><span aria-hidden="true">⌘</span><div><strong>{t('观察当前进程，保留动作证据。')}</strong><p>{t('运行数、限额和拒绝计数只覆盖当前单个后端进程。重启后预算计数重置，不能据此推断生产吞吐或服务可用率。')}</p></div></div>
    {data ? <>
      <div className="admin-metric-grid">{[
        [t('正在执行'), count(data.budgets.active_runs), t('当前占用的模型运行位置')],
        [t('最大并行运行'), count(data.budgets.max_concurrent_runs), t('此进程允许的并行上限')],
        [t('每主体每分钟限额'), count(data.budgets.requests_per_actor_per_minute), t('账户或本机演示主体的聊天请求上限')],
        [t('启动以来拒绝'), count(data.budgets.rejected_since_start), t('预算或并行位置不足导致的拒绝')],
      ].map(([label, value, hint]) => <article className="admin-metric-card" key={label}><span>{label}</span><strong>{value}</strong><small>{hint}</small></article>)}</div>
      <section className="admin-panel"><h2>{t('统计与保留范围')}</h2><dl className="admin-definition-list"><div><dt>{t('预算范围')}</dt><dd>{t('单进程内存计数；服务重启后重新开始')}</dd></div><div><dt>{t('审计保留配置')}</dt><dd>{count(data.audit_retention_days)} {t('天')}<p className="admin-note">{t('动作审计保存在后端数据库，预算计数与动作审计采用不同的保存方式。')}</p></dd></div><div><dt>{t('内容边界')}</dt><dd>{t('仅展示动作、时间、缩略标识和允许的标量元数据；不展示聊天原文、提示词、工具输入输出或密钥。')}</dd></div></dl></section>
      <div className="admin-section-heading"><h2>{t('脱敏动作审计')}</h2><span>{Math.min(data.audit.length, 100)} {t('条已读取记录')} · {t('最多 100 条')}</span></div>
      <div className="admin-panel admin-table-panel"><div className="admin-table-scroll"><table className="admin-table"><thead><tr><th>{t('动作与时间')}</th><th>{t('操作主体')}</th><th>{t('目标标识')}</th><th>{t('允许的运行元数据')}</th></tr></thead><tbody>{data.audit.slice(0, 100).map(event => <tr key={event.id}><td><strong>{t(actions[event.action] ?? '其他已记录动作')}</strong><small>{time(event.created)}</small></td><td>{actor(event.actor_id)}</td><td><code>{identifier(event.target_id)}</code></td><td className="admin-break" style={{whiteSpace: 'normal', minWidth: 220, maxWidth: 420}}>{metadata(event.metadata ?? {})}</td></tr>)}</tbody></table></div>{!data.audit.length && <div className="admin-empty">{t('暂无动作审计。后续账户和运行操作会在这里留下记录。')}</div>}</div>
    </> : !loading && <div className="admin-empty">{t('暂无运行控制数据。可刷新重试。')}</div>}
  </>
}
