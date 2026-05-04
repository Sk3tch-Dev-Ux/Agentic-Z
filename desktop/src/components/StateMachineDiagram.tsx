// SVG-based state machine for the dayz-director. Custom layout (no React Flow
// dep) — the state list is fixed at design time so a hardcoded position grid
// is simpler and ~200 KB lighter than a graph layout library.

import { DirectorTransition } from "../api/director";

const NODES: { id: string; label: string; x: number; y: number; }[] = [
  { id: "IDLE",       label: "IDLE",       x:  90, y:  40 },
  { id: "PREFLIGHT",  label: "PREFLIGHT",  x:  90, y: 110 },
  { id: "AUDIT",      label: "AUDIT",      x:  90, y: 180 },
  { id: "PLAN",       label: "PLAN",       x:  90, y: 250 },
  { id: "FIX",        label: "FIX",        x:  90, y: 320 },
  { id: "REAUDIT",    label: "REAUDIT",    x:  90, y: 390 },
  { id: "BUILD",      label: "BUILD",      x:  90, y: 460 },
  { id: "LAUNCH",     label: "LAUNCH",     x:  90, y: 530 },
  { id: "TAIL",       label: "TAIL",       x:  90, y: 600 },
  { id: "REPORT",     label: "REPORT",     x:  90, y: 670 },
  { id: "DONE",       label: "DONE",       x:  90, y: 740 },
  // Off-path
  { id: "DEBUG",      label: "DEBUG",      x: 240, y: 320 },
  { id: "HALTED",     label: "HALTED",     x: 240, y: 670 },
];

const NODE_W = 130;
const NODE_H = 36;

const FLOW_EDGES: [string, string, string?][] = [
  ["IDLE", "PREFLIGHT"],
  ["PREFLIGHT", "AUDIT"],
  ["AUDIT", "PLAN"],
  ["PLAN", "FIX"],
  ["FIX", "REAUDIT"],
  ["REAUDIT", "FIX",   "still critical"],
  ["REAUDIT", "BUILD"],
  ["BUILD", "LAUNCH"],
  ["LAUNCH", "TAIL"],
  ["TAIL", "REPORT"],
  ["TAIL", "DEBUG",   "errors"],
  ["DEBUG", "FIX",    "fix"],
  ["REPORT", "DONE"],
  ["FIX", "HALTED",   "cap tripped"],
  ["BUILD", "HALTED", "3× failure"],
];

const W = 380;
const H = 800;

interface Props {
  currentState?: string;
  transitions?: DirectorTransition[];
}

export function StateMachineDiagram({ currentState, transitions = [] }: Props) {
  const visited = new Set<string>(transitions.map((t) => t.to));
  if (currentState) visited.add(currentState);

  const nodeById = new Map(NODES.map((n) => [n.id, n]));

  function nodeFill(id: string): string {
    if (id === currentState) return "#3a8c5a";   // accent (current)
    if (visited.has(id))      return "#1f4d2e";   // accent-dim (visited)
    return "#1f2322";                              // bg-elevated
  }

  function nodeStroke(id: string): string {
    if (id === currentState) return "#52b073";
    if (visited.has(id))      return "#3a8c5a";
    return "#2a2f2d";
  }

  function nodeTextColor(id: string): string {
    if (id === currentState || visited.has(id)) return "#ffffff";
    return "#7a807d";
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMin meet">
      <defs>
        <marker id="arrow-active" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#3a8c5a" />
        </marker>
        <marker id="arrow-dim" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#444" />
        </marker>
      </defs>

      {/* Edges */}
      {FLOW_EDGES.map(([fromId, toId, label], i) => {
        const a = nodeById.get(fromId);
        const b = nodeById.get(toId);
        if (!a || !b) return null;
        const ax = a.x + NODE_W / 2;
        const ay = a.y + NODE_H / 2;
        const bx = b.x + NODE_W / 2;
        const by = b.y + NODE_H / 2;
        const isActive = visited.has(fromId) && visited.has(toId);
        const stroke = isActive ? "#3a8c5a" : "#2f3432";
        const marker = isActive ? "url(#arrow-active)" : "url(#arrow-dim)";

        // Edge: straight if vertical, curved if horizontal jump
        let path: string;
        if (Math.abs(a.x - b.x) < 1) {
          // Vertical: from bottom of A to top of B
          const startY = a.y + NODE_H + 1;
          const endY = b.y - 8;
          path = `M ${ax} ${startY} L ${bx} ${endY}`;
        } else {
          // Curved: side jump
          const startX = a.x + NODE_W;
          const startY = ay;
          const endX = b.x;
          const endY = by;
          const cx = (startX + endX) / 2 + 30;
          path = `M ${startX} ${startY} Q ${cx} ${(startY + endY) / 2} ${endX} ${endY}`;
        }
        const labelX = (ax + bx) / 2 + (Math.abs(a.x - b.x) < 1 ? 12 : 18);
        const labelY = (ay + by) / 2;

        return (
          <g key={i}>
            <path d={path} fill="none" stroke={stroke} strokeWidth={isActive ? 2 : 1}
                  markerEnd={marker} />
            {label && (
              <text x={labelX} y={labelY} fill={isActive ? "#7a9a82" : "#555"}
                    fontSize="10" fontFamily="monospace">{label}</text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {NODES.map((n) => {
        const isCurrent = n.id === currentState;
        return (
          <g key={n.id}>
            <rect
              x={n.x} y={n.y} width={NODE_W} height={NODE_H} rx={4}
              fill={nodeFill(n.id)} stroke={nodeStroke(n.id)} strokeWidth={isCurrent ? 2 : 1}
            />
            <text
              x={n.x + NODE_W / 2} y={n.y + NODE_H / 2 + 4}
              textAnchor="middle"
              fontSize="12"
              fontWeight={isCurrent ? "bold" : "normal"}
              fontFamily="ui-sans-serif, system-ui"
              fill={nodeTextColor(n.id)}
            >
              {n.label}
            </text>
            {isCurrent && (
              <circle cx={n.x + 10} cy={n.y + 10} r={4} fill="#52b073">
                <animate attributeName="opacity" values="1;0.3;1" dur="1.4s" repeatCount="indefinite" />
              </circle>
            )}
          </g>
        );
      })}
    </svg>
  );
}
