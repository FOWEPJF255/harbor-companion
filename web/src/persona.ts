import type { Language } from './i18n'

export const profileSections = ['growth', 'work', 'skills', 'interests', 'flaws', 'boundaries'] as const
export type ProfileSection = typeof profileSections[number]
export type PersonaProfile = {
  schema_version: 1
  fictional: true
  age: number
  sections: Record<ProfileSection, Record<Language, string>>
}
export type ProfileSnapshot = {character_id: string; revision: number; name: string; profile: PersonaProfile | null; legacy_profile: boolean; created?: string; enabled?: boolean; tagline?: string; description?: string; greeting?: string}
export type ProfileTarget = {kind: 'public' | 'session'; id: string; name: string}
export const sectionNames: Record<Language, Record<ProfileSection, string>> = {
  zh: {growth: '成长经历', work: '学习 / 工作', skills: '会做与不会做', interests: '兴趣与习惯', flaws: '优点与缺点', boundaries: '关系边界'},
  en: {growth: 'Growing up', work: 'Study / work', skills: 'Can / cannot do', interests: 'Interests / habits', flaws: 'Strengths / flaws', boundaries: 'Boundaries'},
}
const en = {
  profile: 'Character profile', viewProfile: 'View profile', close: 'Close profile', back: 'Back', loading: 'Loading the profile…', retry: 'Try again',
  fiction: 'A fictional AI character. The age, experiences and relationships below are authored settings, not a real person’s biography.',
  snapshot: 'This session’s saved profile', publicVersion: 'Current public profile', revision: 'Revision', age: 'Fictional age',
  frozen: 'This session keeps the profile version saved when it began. Later published changes apply to new sessions.',
  legacy: 'This older version has no structured profile. No current biography has been substituted for it.',
  translations: 'Chinese and English are separately authored profile text. Names, greetings and existing chat stay in their original language.',
  ask: 'Ask about this profile', question: 'Your question', placeholder: 'What would you like to ask about this part of her story?', send: 'Ask in this chat',
  choose: 'Choose this character to start', startFirst: 'To ask, explicitly start a new chat with this character after confirming you are 18 or older. Viewing a profile does not start or send a chat.',
  currentOnly: 'Questions are sent through the ordinary chat in this saved session. Your existing chat draft is kept.',
  askError: 'This turn could not be confirmed. Close the profile to inspect the error and retry with the same request ID. Both drafts have been kept.',
  sections: 'Profile sections', archived: 'The public character may be archived. An existing session keeps its saved profile.',
  truncated: 'This reply reached the output limit. It may be incomplete; ask the character to continue if needed.',
  historyProfile: 'Restore and view profile',
} as const
type PersonaText = keyof typeof en
const zh: Record<PersonaText, string> = {
  profile: '角色档案', viewProfile: '查看档案', close: '关闭角色档案', back: '返回', loading: '正在读取角色档案…', retry: '重新读取',
  fiction: '这是虚构的 AI 角色。以下年龄、经历与关系均为创作设定，不是真人的履历。',
  snapshot: '本次会话保存的档案', publicVersion: '当前公开档案', revision: '版本', age: '设定年龄',
  frozen: '会话沿用创建时保存的档案版本。之后发布的修改只影响新会话。',
  legacy: '这个旧版本没有结构化档案。系统没有用当前的新经历替换旧设定。',
  translations: '中文与英文档案分别编写。姓名、开场白和已有聊天保持原文，不随界面语言翻译。',
  ask: '就这段经历问问她', question: '想问的问题', placeholder: '关于这段经历，你想问她什么？', send: '在当前会话提问',
  choose: '选择这个角色，准备聊天', startFirst: '提问前，请选择这个角色、确认已满 18 岁，并主动创建新会话。查看档案不会自动开始聊天或发送消息。',
  currentOnly: '问题通过本次会话的普通聊天发送，原有聊天草稿会保留。', sections: '档案分区', archived: '公开角色可能已归档；已有会话仍保留创建时的档案。',
  askError: '这一轮尚未确认完成。请关闭档案查看错误并重试，重试沿用原请求编号。两个草稿均已保留。',
  truncated: '这次回复触及输出长度上限，内容可能不完整；需要时可以请角色继续。', historyProfile: '恢复并查看档案',
}
export const personaTranslator = (language: Language) => (key: PersonaText) => (language === 'en' ? en : zh)[key]
export function emptyProfile(): PersonaProfile {
  return {schema_version: 1, fictional: true, age: 18, sections: Object.fromEntries(profileSections.map(key => [key, {zh: '', en: ''}])) as PersonaProfile['sections']}
}

export const reviewDimensions = [
  {key: 'naturalness', field: 'naturalness_score', zh: '自然度', en: 'Naturalness'},
  {key: 'persona', field: 'persona_score', zh: '角色辨识度', en: 'Persona distinction'},
  {key: 'continuity', field: 'continuity_score', zh: '上下文连贯', en: 'Context continuity'},
  {key: 'credibility', field: 'credibility_score', zh: '细节可信度', en: 'Detail credibility'},
  {key: 'empathy', field: 'empathy_score', zh: '共情', en: 'Empathy'},
  {key: 'boundary', field: 'boundary_score', zh: '边界', en: 'Boundaries'},
] as const
export type ReviewDimension = typeof reviewDimensions[number]['key']
export type ReviewScoreField = typeof reviewDimensions[number]['field']
