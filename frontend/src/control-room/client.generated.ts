/** Generated-shape API client for the Work Frontier OpenAPI surface. */

export interface FrontierItem {
  readonly item_id: string
  readonly decision_id: string
  readonly decision_type: string
  readonly title: string
  readonly ready: boolean
  readonly ranking_position: number | null
  readonly authority: string
  readonly freshness: string
  readonly why: readonly string[]
  readonly blocked_by: readonly string[]
}

export interface FrontierPage {
  readonly items: readonly FrontierItem[]
  readonly next_cursor: string | null
}

export interface LeaseResponse {
  readonly lease_id: string
  readonly item_id: string
  readonly owner: string
  readonly decision_id: string
  readonly version: number
}

export interface ControlPlaneClient {
  frontier(cursor?: string): Promise<FrontierPage>
  item(itemId: string): Promise<FrontierItem>
  claim(itemId: string, decisionId: string, divergenceReason?: string): Promise<LeaseResponse>
}

export interface ClientOptions {
  readonly baseUrl: string
  readonly token: string
  readonly tenantId: string
  readonly workspaceId: string
  readonly fetchImpl?: typeof fetch
}

export function createControlPlaneClient(options: ClientOptions): ControlPlaneClient {
  const fetchImpl = options.fetchImpl ?? fetch
  const headers = {
    Authorization: `Bearer ${options.token}`,
    "Content-Type": "application/json",
    "X-Tenant-ID": options.tenantId,
    "X-Workspace-ID": options.workspaceId,
  }

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetchImpl(`${options.baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: { ...headers, ...init?.headers },
    })
    const payload: unknown = await response.json()
    if (!response.ok) {
      const message = readErrorMessage(payload)
      throw new Error(message)
    }
    return payload as T
  }

  return {
    frontier: (cursor?: string) =>
      request<FrontierPage>(`/frontier${cursor === undefined ? "" : `?cursor=${encodeURIComponent(cursor)}`}`),
    item: (itemId: string) => request<FrontierItem>(`/frontier/${encodeURIComponent(itemId)}`),
    claim: (itemId: string, decisionId: string, divergenceReason?: string) =>
      request<LeaseResponse>(`/leases/${encodeURIComponent(itemId)}/claim`, {
        method: "POST",
        body: JSON.stringify({
          decision_id: decisionId,
          ...(divergenceReason === undefined ? {} : { divergence_reason: divergenceReason }),
        }),
      }),
  }
}

function readErrorMessage(payload: unknown): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "error" in payload &&
    typeof payload.error === "object" &&
    payload.error !== null &&
    "message" in payload.error &&
    typeof payload.error.message === "string"
  ) {
    return payload.error.message
  }
  return "Work Frontier request failed"
}
