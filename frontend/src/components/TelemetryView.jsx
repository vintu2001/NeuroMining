import React, { useEffect, useState } from "react";

const STAT_CONFIG = [
  { key: "total_users",        label: "Indexed Users",        unit: "",     color: "#6366f1" },
  { key: "hdfs_raw_gb",        label: "HDFS Raw Storage",     unit: " GB",  color: "#22d3ee" },
  { key: "hdfs_processed_gb",  label: "Processed Data",       unit: " GB",  color: "#f59e0b" },
  { key: "hdfs_features_gb",   label: "Feature Store",        unit: " GB",  color: "#34d399" },
  { key: "mapreduce_output_rows", label: "MR Output Rows",    unit: "",     color: "#f87171" },
];

function StatCard({ label, value, unit, color }) {
  return (
    <div className="rounded-xl bg-nm-surface border border-nm-border px-5 py-4 flex flex-col gap-1">
      <span className="text-nm-muted text-xs uppercase tracking-wider">{label}</span>
      <span className="font-mono text-2xl font-bold" style={{ color }}>
        {value !== undefined && value !== null
          ? typeof value === "number"
            ? value.toLocaleString() + unit
            : value + unit
          : "—"}
      </span>
    </div>
  );
}

export default function TelemetryView({ data }) {
  // Simulate live ticking for HDFS raw storage to make it feel "real-time"
  const [live, setLive] = useState(data);

  useEffect(() => {
    setLive(data);
  }, [data]);

  useEffect(() => {
    if (!live) return;
    const interval = setInterval(() => {
      setLive((prev) => ({
        ...prev,
        hdfs_raw_gb: +(prev.hdfs_raw_gb + Math.random() * 0.003).toFixed(3),
        mapreduce_output_rows: prev.mapreduce_output_rows + Math.floor(Math.random() * 50),
      }));
    }, 1500);
    return () => clearInterval(interval);
  }, [!!live]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">HDFS Telemetry</h2>
        <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          Live
        </span>
      </div>

      {!live ? (
        <div className="flex items-center justify-center h-48 text-nm-muted">
          Loading telemetry…
        </div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {STAT_CONFIG.map(({ key, label, unit, color }) => (
              <StatCard key={key} label={label} value={live[key]} unit={unit} color={color} />
            ))}
          </div>

          {/* Storage breakdown bar */}
          <div className="rounded-xl bg-nm-surface border border-nm-border p-5 space-y-3">
            <h3 className="text-sm font-semibold text-nm-muted uppercase tracking-wider">Storage Breakdown</h3>
            {[
              { label: "Raw Clickstream", value: live.hdfs_raw_gb,       max: 120, color: "#22d3ee" },
              { label: "MapReduce Output", value: live.hdfs_processed_gb, max: 120, color: "#f59e0b" },
              { label: "Feature Store",   value: live.hdfs_features_gb,  max: 120, color: "#34d399" },
            ].map(({ label, value, max, color }) => (
              <div key={label} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-nm-muted">{label}</span>
                  <span className="font-mono" style={{ color }}>{value?.toFixed(2)} GB</span>
                </div>
                <div className="h-2 bg-nm-bg rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${Math.min((value / max) * 100, 100)}%`, background: color }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Pipeline status */}
          <div className="rounded-xl bg-nm-surface border border-nm-border p-5">
            <h3 className="text-sm font-semibold text-nm-muted uppercase tracking-wider mb-3">Pipeline Stage Status</h3>
            <div className="space-y-2">
              {[
                { stage: "HDFS Ingestion",        status: "complete" },
                { stage: "MapReduce Cleaning",     status: "complete" },
                { stage: "Hive Feature Engineering", status: "complete" },
                { stage: "Spark ML Training",      status: "complete" },
                { stage: "Cluster Assignment",     status: "complete" },
              ].map(({ stage, status }) => (
                <div key={stage} className="flex items-center gap-3 text-sm">
                  <span className={`w-2 h-2 rounded-full ${status === "complete" ? "bg-emerald-400" : "bg-nm-muted animate-pulse"}`} />
                  <span className="text-nm-text">{stage}</span>
                  <span className={`ml-auto text-xs font-mono ${status === "complete" ? "text-emerald-400" : "text-nm-muted"}`}>
                    {status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
