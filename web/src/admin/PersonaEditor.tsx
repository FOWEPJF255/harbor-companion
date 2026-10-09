import type { Language } from '../i18n'
import { emptyProfile, profileSections, sectionNames, type PersonaProfile } from '../persona'

export default function PersonaEditor({profile, language, disabled, onChange}: {profile?: PersonaProfile | null; language: Language; disabled: boolean; onChange: (value: PersonaProfile) => void}) {
  const en = language === 'en'
  return <fieldset className="admin-persona-editor" disabled={disabled}>
    <legend>{en ? 'Structured fictional profile' : '结构化虚构档案'}</legend>
    <p className="admin-note">{en ? 'Authored fictional settings only. Each save creates a new revision; existing sessions keep their own snapshot. Fill both languages rather than translating on the client.' : '只填写创作的虚构设定。每次保存创建新版本，已有会话保留原快照。中文和英文分别编写，前端不自动翻译。'}</p>
    {!profile ? <><p className="admin-note">{en ? 'This legacy character has no structured profile. Saving other fields keeps that state.' : '这个旧角色没有结构化档案；保存其他字段会保留这一状态。'}</p><button type="button" className="admin-button" onClick={() => onChange(emptyProfile())}>{en ? 'Add a structured profile' : '添加结构化档案'}</button></> : <>
      <label>{en ? 'Fictional adult age' : '虚构成年年龄'}<input type="number" min={18} max={120} step={1} required value={profile.age} onChange={event => onChange({...profile, age: Number(event.target.value)})}/></label>
      <p className="admin-persona-fiction">{en ? 'AI fiction disclosure is always shown with the profile. The character must not claim these are real-life experiences.' : '档案会持续显示 AI 虚构身份说明，角色不能把这些经历声称为真人经历。'}</p>
      {profileSections.map(section => <details className="admin-persona-section" key={section} open>
        <summary>{sectionNames[language][section]}</summary>
        <div className="admin-persona-language-grid">{(['zh', 'en'] as const).map(locale => <label key={locale} htmlFor={`profile-${section}-${locale}`}>{locale === 'zh' ? '中文 · Chinese' : 'English · 英文'}<textarea id={`profile-${section}-${locale}`} lang={locale} rows={4} minLength={1} maxLength={2000} required value={profile.sections[section][locale]} onChange={event => onChange({...profile, sections: {...profile.sections, [section]: {...profile.sections[section], [locale]: event.target.value}}})}/><small>{profile.sections[section][locale].length} / 2000</small></label>)}</div>
      </details>)}
    </>}
  </fieldset>
}
