import { Timeline } from "antd";

export interface TraceStep {
  step: string;
  summary: string;
  duration_ms?: number;
}

export default function TracePanel({ trace }: { trace: TraceStep[] }) {
  return (
    <Timeline
      items={trace.map((t) => ({
        children: (
          <span>
            <b>{t.step}</b>: {t.summary}
            {t.duration_ms != null && <span style={{ color: "#999" }}> ({t.duration_ms}ms)</span>}
          </span>
        ),
      }))}
    />
  );
}
