import {
  exportExecutiveMetrics,
  type ExecutiveMetric,
} from "./executive-operator"

export function ExecutiveView({
  metrics,
}: {
  readonly metrics: readonly ExecutiveMetric[]
}) {
  const exportValue = exportExecutiveMetrics(metrics)
  return (
    <section aria-labelledby="executive-heading">
      <h1 id="executive-heading">Executive outcomes</h1>
      <p>Every result includes its authority and source revision.</p>
      <dl className="wf-metric-grid">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <dt>{metric.label}</dt>
            <dd>
              {metric.value} {metric.unit}
            </dd>
            <dd>
              {metric.authority}; {metric.sourceRevision}
            </dd>
          </div>
        ))}
      </dl>
      <a
        download="work-frontier-executive.csv"
        href={`data:text/csv;charset=utf-8,${encodeURIComponent(exportValue)}`}
      >
        Export authoritative metrics
      </a>
    </section>
  )
}
