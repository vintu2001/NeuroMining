import React, { useRef, useEffect, useState } from "react";
import * as d3 from "d3";

const CLUSTER_COLORS = [
  "#6366f1", // indigo  — Power Networkers
  "#22d3ee", // cyan    — Passive Browsers
  "#f59e0b", // amber   — Content Creators
  "#34d399", // emerald — Job Seekers
  "#f87171", // red     — Casual Observers
];

export default function ClusterMap({ data }) {
  const svgRef  = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  useEffect(() => {
    if (!data || !data.points || !svgRef.current) return;

    const container = svgRef.current.parentElement;
    const W = container.clientWidth  || 800;
    const H = 520;
    const MARGIN = { top: 20, right: 30, bottom: 40, left: 40 };

    const points = data.points;

    // Clear previous render
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3
      .select(svgRef.current)
      .attr("width", W)
      .attr("height", H);

    // Scales
    const xExtent = d3.extent(points, (d) => d.pca_x);
    const yExtent = d3.extent(points, (d) => d.pca_y);
    const xPad = (xExtent[1] - xExtent[0]) * 0.05;
    const yPad = (yExtent[1] - yExtent[0]) * 0.05;

    const xScale = d3
      .scaleLinear()
      .domain([xExtent[0] - xPad, xExtent[1] + xPad])
      .range([MARGIN.left, W - MARGIN.right]);

    const yScale = d3
      .scaleLinear()
      .domain([yExtent[0] - yPad, yExtent[1] + yPad])
      .range([H - MARGIN.bottom, MARGIN.top]);

    // Grid lines
    const grid = svg.append("g").attr("class", "grid");
    grid
      .append("g")
      .attr("transform", `translate(0,${H - MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).ticks(8).tickSize(-(H - MARGIN.top - MARGIN.bottom)).tickFormat(""))
      .selectAll("line")
      .attr("stroke", "#2a2d3a")
      .attr("stroke-dasharray", "3,3");

    grid
      .append("g")
      .attr("transform", `translate(${MARGIN.left},0)`)
      .call(d3.axisLeft(yScale).ticks(6).tickSize(-(W - MARGIN.left - MARGIN.right)).tickFormat(""))
      .selectAll("line")
      .attr("stroke", "#2a2d3a")
      .attr("stroke-dasharray", "3,3");

    // Axes
    svg
      .append("g")
      .attr("transform", `translate(0,${H - MARGIN.bottom})`)
      .call(d3.axisBottom(xScale).ticks(8))
      .selectAll("text, line, path")
      .attr("stroke", "#64748b")
      .attr("fill", "#64748b");

    svg
      .append("g")
      .attr("transform", `translate(${MARGIN.left},0)`)
      .call(d3.axisLeft(yScale).ticks(6))
      .selectAll("text, line, path")
      .attr("stroke", "#64748b")
      .attr("fill", "#64748b");

    // Axis labels
    svg.append("text")
      .attr("x", W / 2).attr("y", H - 4)
      .attr("text-anchor", "middle").attr("fill", "#64748b").attr("font-size", 11)
      .text("PCA Component 1");

    svg.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -H / 2).attr("y", 14)
      .attr("text-anchor", "middle").attr("fill", "#64748b").attr("font-size", 11)
      .text("PCA Component 2");

    // Scatter points
    svg
      .append("g")
      .selectAll("circle")
      .data(points)
      .join("circle")
      .attr("cx", (d) => xScale(d.pca_x))
      .attr("cy", (d) => yScale(d.pca_y))
      .attr("r", 3.5)
      .attr("fill", (d) => CLUSTER_COLORS[d.cluster] ?? "#94a3b8")
      .attr("fill-opacity", 0.7)
      .attr("stroke", (d) => CLUSTER_COLORS[d.cluster] ?? "#94a3b8")
      .attr("stroke-width", 0.3)
      .on("mouseover", (event, d) => {
        setTooltip({
          x: event.clientX,
          y: event.clientY,
          user_id: d.user_id,
          archetype: d.archetype,
          cluster: d.cluster,
          pca_x: d.pca_x.toFixed(3),
          pca_y: d.pca_y.toFixed(3),
        });
      })
      .on("mouseout", () => setTooltip(null));

  }, [data]);

  const meta = data?.metadata ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">User Behavioral Clusters</h2>
        <span className="text-nm-muted text-sm">(Bisecting K-Means, k=5 · PCA 2-D projection)</span>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3">
        {CLUSTER_COLORS.map((color, i) => {
          const m = meta.find((x) => x.cluster_id === i);
          return (
            <div key={i} className="flex items-center gap-1.5 text-sm">
              <span className="w-3 h-3 rounded-full inline-block" style={{ background: color }} />
              <span className="text-nm-text">{m?.archetype ?? `Cluster ${i}`}</span>
              {m && (
                <span className="text-nm-muted">({m.user_count.toLocaleString()})</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Chart */}
      <div className="rounded-xl bg-nm-surface border border-nm-border p-4 overflow-hidden">
        {!data ? (
          <div className="flex items-center justify-center h-64 text-nm-muted">Loading cluster data…</div>
        ) : (
          <svg ref={svgRef} className="w-full" />
        )}
      </div>

      {/* Silhouette score */}
      {meta.length > 0 && (
        <p className="text-nm-muted text-xs">
          Silhouette score: <span className="text-nm-text font-mono">{meta[0]?.silhouette}</span>
        </p>
      )}

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-nm-surface border border-nm-border rounded-lg px-3 py-2 text-xs shadow-xl pointer-events-none"
          style={{ top: tooltip.y + 12, left: tooltip.x + 12 }}
        >
          <div className="font-semibold text-nm-text mb-1">{tooltip.archetype}</div>
          <div className="text-nm-muted font-mono">{tooltip.user_id}</div>
          <div className="text-nm-muted">x={tooltip.pca_x} y={tooltip.pca_y}</div>
        </div>
      )}
    </div>
  );
}
