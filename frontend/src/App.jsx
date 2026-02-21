import React, { useState, useEffect } from "react";
import axios from "axios";
import ClusterMap from "./components/ClusterMap";
import ModelComparison from "./components/ModelComparison";
import TelemetryView from "./components/TelemetryView";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TABS = ["Cluster Map", "Model Comparison", "Telemetry"];

export default function App() {
  const [activeTab, setActiveTab] = useState("Cluster Map");
  const [clusters, setClusters]   = useState(null);
  const [metrics, setMetrics]     = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [error, setError]         = useState(null);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/clusters?limit=3000`),
      axios.get(`${API}/metrics`),
      axios.get(`${API}/telemetry`),
    ])
      .then(([c, m, t]) => {
        setClusters(c.data);
        setMetrics(m.data);
        setTelemetry(t.data);
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="min-h-screen bg-nm-bg text-nm-text">
      <header className="border-b border-nm-border px-8 py-4 flex items-center gap-4">
        <span className="text-nm-accent font-bold text-xl tracking-tight">
          ⬡ NeuroMining
        </span>
        <span className="text-nm-muted text-sm">
          Distributed ML Analytics Dashboard
        </span>
      </header>

      <nav className="border-b border-nm-border px-8 flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "text-nm-accent border-b-2 border-nm-accent"
                : "text-nm-muted hover:text-nm-text"
            }`}
          >
            {tab}
          </button>
        ))}
      </nav>

      <main className="px-8 py-6">
        {error && (
          <div className="mb-4 rounded-lg bg-red-900/30 border border-red-700 px-4 py-3 text-red-300 text-sm">
            API Error: {error}. Using stub data.
          </div>
        )}

        {activeTab === "Cluster Map" && (
          <ClusterMap data={clusters} />
        )}
        {activeTab === "Model Comparison" && (
          <ModelComparison data={metrics} />
        )}
        {activeTab === "Telemetry" && (
          <TelemetryView data={telemetry} />
        )}
      </main>
    </div>
  );
}
