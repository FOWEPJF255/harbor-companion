export type AdminView = 'overview' | 'characters' | 'sessions' | 'reviews' | 'provider'

export interface CharacterInput {
  name: string
  tagline: string
  description: string
  system_prompt: string
  greeting: string
  accent_color: string
  avatar_style: 'nova' | 'sage' | 'ember'
  enabled: boolean
}

export interface Character extends CharacterInput {
  id: string
  revision: number
  created: string
  updated: string
}

export interface Overview {
  session_count: number
  turn_count: number
  memory_count: number
  pending_memory_count: number
  active_character_count: number
  provider_counts: Record<string, number>
  average_latency_ms: number | null
  reviews_count: number
}

export interface SessionSummary {
  id: string
  character_id: string
  character_name: string
  mode: string
  created: string
  turn_count: number
  memory_count: number
  last_active: string | null
}

export interface SessionDetail {
  session: SessionSummary
  messages: Array<{role: string; content: string; created: string}>
  memories: Array<{id: string; content: string; status: string}>
  turns: Array<{
    id: string
    provider: string
    emotion: string
    latency_ms: number
    created: string
    trace: unknown
    usage: unknown
  }>
}

export interface Review {
  id: string
  session_id: string
  run_id: string | null
  persona_score: number
  empathy_score: number
  memory_score: number
  note: string
  created: string
  provider: string
}

export interface ProviderStatus {
  provider: string
  configured: boolean
  model: string | null
  api_base: string
  credentials_set: boolean
  quality_evidence: string
}
