import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createContext, useMemo, type ReactNode } from "react"

export type ControlRoomView = "builder" | "coordinator" | "executive" | "operator" | "setup"

export interface WorkspaceSession {
  readonly tenantId: string
  readonly workspaceId: string
  readonly actorId: string
  readonly role: string
  readonly sessionToken: string
}

export const WorkspaceSessionContext = createContext<WorkspaceSession | null>(null)

export interface ControlRoomShellProps {
  readonly session: WorkspaceSession
  readonly activeView: ControlRoomView
  readonly onNavigate: (view: ControlRoomView) => void
  readonly children: ReactNode
}

const views: readonly { readonly id: ControlRoomView; readonly label: string }[] = [
  { id: "builder", label: "Builder" },
  { id: "coordinator", label: "Coordinator" },
  { id: "executive", label: "Executive" },
  { id: "operator", label: "Operator" },
  { id: "setup", label: "Setup" },
]

export function ControlRoomShell(props: ControlRoomShellProps) {
  const queryClient = useMemo(() => new QueryClient(), [])
  return (
    <WorkspaceSessionContext.Provider value={props.session}>
      <QueryClientProvider client={queryClient}>
        <a className="wf-skip-link" href="#wf-main">Skip to main content</a>
        <header className="wf-shell-header">
          <strong>Work Frontier</strong>
          <span><strong>Workspace:</strong> {props.session.workspaceId}</span>
        </header>
        <nav aria-label="Control Room views" className="wf-shell-nav">
          {views.map((view) => (
            <button
              aria-current={props.activeView === view.id ? "page" : undefined}
              key={view.id}
              onClick={() => props.onNavigate(view.id)}
              type="button"
            >
              {view.label}
            </button>
          ))}
        </nav>
        <main id="wf-main" tabIndex={-1}>{props.children}</main>
      </QueryClientProvider>
    </WorkspaceSessionContext.Provider>
  )
}
