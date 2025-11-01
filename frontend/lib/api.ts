const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || ''
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || ''

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  console.log('[API] Making request to:', url)
  console.log('[API] Method:', options.method || 'GET')
  console.log('[API] Body:', options.body)
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }

  if (API_KEY) {
    headers['X-API-KEY'] = API_KEY
  }

  console.log('[API] Headers:', headers)

  const response = await fetch(url, {
    ...options,
    headers,
  })
  
  console.log('[API] Response status:', response.status)

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `HTTP error! status: ${response.status}`)
  }

  return response.json()
}

export interface PopulateListRequest {
  search_url: string
  profile_limit?: number
  collect_only?: boolean
  send_note?: boolean
  note_text?: string
}

export interface SendCampaignRequest {
  limit?: number
  default_dm?: string
}

export interface VerifyConnectionsRequest {
  limit?: number
}

export interface List {
  id: string
  name: string
  search_url?: string
  profile_count?: number
  count?: number
  created_at: string
}

export interface Prospect {
  id?: string
  profile_url: string
  first_name?: string
  status?: string
  list_id?: string
}

export interface Sender {
  id: string
  name?: string
  enabled: boolean
  updated_at?: string
  storage_state?: string
}

export const api = {
  health: () => apiRequest<{ ok: boolean }>('/health', { method: 'GET' }),

  getLists: () => apiRequest<List[]>('/lists', { method: 'GET' }),

  getList: (listId: string) => apiRequest<List>(`/lists/${listId}`, { method: 'GET' }),

  getListProspects: (listId: string) =>
    apiRequest<Prospect[]>(`/lists/${listId}/prospects`, { method: 'GET' }),

  updateList: (listId: string, data: { name: string }) =>
    apiRequest<List>(`/lists/${listId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteList: (listId: string) =>
    apiRequest<{ ok: boolean; message?: string }>(`/lists/${listId}`, {
      method: 'DELETE',
    }),

  populateList: (data: PopulateListRequest) => {
    console.log("[API] populateList() called with data:", data)
    return apiRequest<{ ok: boolean; message?: string }>('/lists/populate', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  sendCampaign: (data: SendCampaignRequest) =>
    apiRequest<{ ok: boolean; attempted: number; sent: number; errors: number }>('/campaigns/send', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  verifyConnections: (data: VerifyConnectionsRequest) =>
    apiRequest<{ ok: boolean; checked: number; connected: number }>('/connections/verify', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getSenders: () => apiRequest<Sender[]>('/senders', { method: 'GET' }),

  toggleSender: (senderId: string) =>
    apiRequest<{ id: string; enabled: boolean }>(`/senders/${senderId}/toggle`, {
      method: 'PATCH',
    }),

  updateSender: (senderId: string, data: { name: string; storage_state?: string }) =>
    apiRequest<{ id: string; ok: boolean }>(`/senders/${senderId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  createSender: (data: { name: string; storage_state?: string }) =>
    apiRequest<{ id: string; ok: boolean }>('/senders', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

