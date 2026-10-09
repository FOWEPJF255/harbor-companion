import type { Language } from '../i18n'
import { reviewDimensions, type ReviewDimension, type ReviewScoreField } from '../persona'

export type SixReviewInput = {
  schema_version: 2; session_id: string; run_id: string; note: string; memory_score: null
  evidence: Record<ReviewDimension, string>
} & Record<ReviewScoreField, number | ''>
export const emptySixReview = (): SixReviewInput => ({
  schema_version: 2, session_id: '', run_id: '', note: '', memory_score: null,
  naturalness_score: '', persona_score: '', continuity_score: '', credibility_score: '', empathy_score: '', boundary_score: '',
  evidence: {naturalness: '', persona: '', continuity: '', credibility: '', empathy: '', boundary: ''},
})
export function SixReviewFields({value, onChange, language, disabled}: {value: SixReviewInput; onChange: (value: SixReviewInput) => void; language: Language; disabled: boolean}) {
  const en = language === 'en'
  return <fieldset className="admin-six-review" disabled={disabled}><legend>{en ? 'Six dimensions · schema v2' : '六维人工评审 · schema v2'}</legend><p className="admin-note">{en ? 'No default scores. Observe each dimension and cite an exact sentence. Pending is not zero; scores are human judgments, not success percentages. Do not paste unnecessary private details.' : '不预填评分。逐项观察并附依据原句；待评分不等于 0 分。评分是人工判断，不是成功率。不要粘贴无关隐私。'}</p><div className="admin-six-grid">{reviewDimensions.map(dimension => <section key={dimension.key}><label htmlFor={`review-${dimension.key}`}>{dimension[language]}<select id={`review-${dimension.key}`} required value={value[dimension.field]} onChange={event => onChange({...value, [dimension.field]: event.target.value ? Number(event.target.value) : ''})}><option value="">{en ? 'Awaiting score' : '待评分'}</option>{[1, 2, 3, 4, 5].map(score => <option key={score} value={score}>{score} / 5</option>)}</select></label><label htmlFor={`evidence-${dimension.key}`}>{en ? 'Evidence · exact sentence' : '依据原句'}<textarea id={`evidence-${dimension.key}`} required minLength={1} maxLength={1000} rows={3} value={value.evidence[dimension.key]} onChange={event => onChange({...value, evidence: {...value.evidence, [dimension.key]: event.target.value}})}/></label></section>)}</div></fieldset>
}
