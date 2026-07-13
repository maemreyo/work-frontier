export interface CopilotPanelProps {
  readonly enabled: boolean
  readonly explanation: string | null
  readonly citations: readonly string[]
  readonly onExplain: () => void
}

export function CopilotPanel({
  enabled,
  explanation,
  citations,
  onExplain,
}: CopilotPanelProps) {
  return (
    <aside aria-labelledby="copilot-heading">
      <h2 id="copilot-heading">Optional Copilot</h2>
      {!enabled ? (
        <p role="status">
          Copilot is off. All readiness, ranking, gates, evidence and approvals remain
          fully available without AI.
        </p>
      ) : (
        <>
          <button onClick={onExplain} type="button">
            Explain with grounded citations
          </button>
          {explanation === null ? null : (
            <div>
              <p>{explanation}</p>
              <h3>Citations</h3>
              <ul>
                {citations.map((citation) => (
                  <li key={citation}>{citation}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </aside>
  )
}
