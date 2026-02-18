import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";

const METRIC_COLORS = {
  accuracy:          "#6366f1",
  f1:                "#22d3ee",
  weightedPrecision: "#f59e0b",
  weightedRecall:    "#34d399",
};

const DISPLAY_NAMES = {
  accuracy:          "Accuracy",
  f1:                "F1 Score",
  weightedPrecision: "Precision",
  weightedRecall:    "Recall",
};

const MODEL_COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#34d399"];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-nm-surface border border-nm-border rounded-lg p-3 text-xs shadow-xl">
      <p className="font-semibold text-nm-text mb-1">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4">
          <span style={{ color: p.fill }}>{p.name}</span>
          <span className="font-mono text-nm-text">{(p.value * 100).toFixed(2)}%</span>
        </div>
      ))}
    </div>
  );
};

export default function ModelComparison({ data }) {
  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 text-nm-muted">
        Loading model metrics…
      </div>
    );
  }

  // Reshape for grouped bar chart: one entry per model
  const chartData = data.map((m) => ({
    model:             m.model,
    Accuracy:          m.accuracy,
    "F1 Score":        m.f1,
    Precision:         m.weightedPrecision,
    Recall:            m.weightedRecall,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">Model Performance Comparison</h2>
        <span className="text-nm-muted text-sm">(Naïve Bayes · SVM · MLP Neural Network · Ensemble)</span>
      </div>

      {/* Grouped Bar Chart */}
      <div className="rounded-xl bg-nm-surface border border-nm-border p-6">
        <ResponsiveContainer width="100%" height={360}>
          <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
            <XAxis
              dataKey="model"
              tick={{ fill: "#64748b", fontSize: 12 }}
              axisLine={{ stroke: "#2a2d3a" }}
              tickLine={false}
            />
            <YAxis
              domain={[0.6, 1.0]}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
              tick={{ fill: "#64748b", fontSize: 12 }}
              axisLine={{ stroke: "#2a2d3a" }}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
            <Legend
              wrapperStyle={{ color: "#64748b", fontSize: 12, paddingTop: 16 }}
            />
            <Bar dataKey="Accuracy"  fill="#6366f1" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="F1 Score"  fill="#22d3ee" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="Precision" fill="#f59e0b" radius={[4, 4, 0, 0]} maxBarSize={28} />
            <Bar dataKey="Recall"    fill="#34d399" radius={[4, 4, 0, 0]} maxBarSize={28} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Numeric table */}
      <div className="overflow-x-auto rounded-xl border border-nm-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-nm-surface text-nm-muted text-left">
              <th className="px-5 py-3 font-medium">Model</th>
              <th className="px-5 py-3 font-medium">Accuracy</th>
              <th className="px-5 py-3 font-medium">Precision</th>
              <th className="px-5 py-3 font-medium">Recall</th>
              <th className="px-5 py-3 font-medium">F1 Score</th>
            </tr>
          </thead>
          <tbody>
            {data.map((m, i) => (
              <tr
                key={m.model}
                className={`border-t border-nm-border ${i % 2 === 0 ? "bg-nm-bg" : "bg-nm-surface"}`}
              >
                <td className="px-5 py-3 font-semibold" style={{ color: MODEL_COLORS[i] }}>
                  {m.model}
                </td>
                <td className="px-5 py-3 font-mono">{(m.accuracy * 100).toFixed(2)}%</td>
                <td className="px-5 py-3 font-mono">{(m.weightedPrecision * 100).toFixed(2)}%</td>
                <td className="px-5 py-3 font-mono">{(m.weightedRecall * 100).toFixed(2)}%</td>
                <td className="px-5 py-3 font-mono">{(m.f1 * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
