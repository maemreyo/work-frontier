import { useContext, useEffect, useRef } from "react"

import { WorkspaceSessionContext } from "../control-room/shell"
import "./setup-center.css"
import "./setup-center-element.js"

interface SetupCenterElement extends HTMLElement {
  configure(options: {
    readonly basePath: string
    readonly headers: Readonly<Record<string, string>>
  }): Promise<void>
}

export function SetupCenter() {
  const session = useContext(WorkspaceSessionContext)
  const element = useRef<SetupCenterElement | null>(null)

  useEffect(() => {
    if (session === null || element.current === null) return
    void element.current.configure({
      basePath: "/setup",
      headers: {
        Authorization: `Bearer ${session.sessionToken}`,
        "X-Tenant-ID": session.tenantId,
        "X-Workspace-ID": session.workspaceId,
        "X-Actor-ID": session.actorId,
        "X-Actor-Role": session.role,
      },
    })
  }, [session])

  return <work-frontier-setup-center ref={element} mode="manual" />
}
