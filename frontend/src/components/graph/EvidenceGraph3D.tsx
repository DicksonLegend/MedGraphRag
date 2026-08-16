import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { CitationMeta } from '../../api/types';
import {
  Maximize2,
  Minimize2,
  X,
  Layers,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  Info,
  ExternalLink,
  Sparkles,
  GitCommit,
} from 'lucide-react';

interface GraphNode {
  id: string;
  name: string;
  type: 'LabTest' | 'Disease' | 'Drug' | 'Document' | 'Chunk' | 'Entity';
  snippet?: string;
  score?: number;
  source?: string;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  mesh?: THREE.Mesh;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
}

interface EvidenceGraph3DProps {
  graphPaths: string[];
  citations: CitationMeta[];
  isOpen: boolean;
  onClose: () => void;
}

export const EvidenceGraph3D: React.FC<EvidenceGraph3DProps> = ({
  graphPaths,
  citations,
  isOpen,
  onClose,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [is2DMode, setIs2DMode] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Parse nodes & links from graph_paths and citations
  const parseGraphData = () => {
    const nodesMap: Map<string, GraphNode> = new Map();
    const links: GraphLink[] = [];

    // Helper to get or create node
    const getOrCreateNode = (
      id: string,
      name: string,
      type: GraphNode['type'],
      extra?: Partial<GraphNode>
    ) => {
      if (!nodesMap.has(id)) {
        // Random initial 3D position on sphere
        const u = Math.random();
        const v = Math.random();
        const theta = u * 2.0 * Math.PI;
        const phi = Math.acos(2.0 * v - 1.0);
        const r = 180 + Math.random() * 80;
        const sinPhi = Math.sin(phi);

        nodesMap.set(id, {
          id,
          name,
          type,
          x: r * sinPhi * Math.cos(theta),
          y: r * sinPhi * Math.sin(theta),
          z: is2DMode ? 0 : r * Math.cos(phi),
          vx: 0,
          vy: 0,
          vz: 0,
          ...extra,
        });
      }
      return nodesMap.get(id)!;
    };

    // 1. Add nodes from citations
    citations.forEach((c) => {
      const docId = c.document_id;
      const chunkId = c.chunk_id;

      getOrCreateNode(`doc_${docId}`, docId.split('/').pop() || docId, 'Document', {
        source: c.source,
      });

      getOrCreateNode(`chunk_${chunkId}`, c.label, 'Chunk', {
        snippet: c.snippet,
        score: c.fused_score,
        source: c.source,
      });

      links.push({
        source: `doc_${docId}`,
        target: `chunk_${chunkId}`,
        label: 'HAS_CHUNK',
      });
    });

    // 2. Parse graph_paths (e.g. "Disease(Hyperkalemia) -[HAS_CHUNK]-> Document(...)")
    graphPaths.forEach((pathStr) => {
      const segments = pathStr.split(/\s*-\[(.*?)\]->\s*/);
      if (segments.length >= 3) {
        for (let i = 0; i < segments.length - 2; i += 2) {
          const rawSrc = segments[i];
          const edge = segments[i + 1] || 'RELATED';
          const rawTgt = segments[i + 2];

          const parseEntity = (raw: string): { type: GraphNode['type']; name: string } => {
            const m = raw.match(/^([A-Za-z0-9_]+)\((.*?)\)$/);
            if (m) {
              const t = m[1] as GraphNode['type'];
              return { type: t, name: m[2] };
            }
            return { type: 'Entity', name: raw };
          };

          const srcEnt = parseEntity(rawSrc);
          const tgtEnt = parseEntity(rawTgt);

          const srcId = `${srcEnt.type}_${srcEnt.name}`;
          const tgtId = `${tgtEnt.type}_${tgtEnt.name}`;

          getOrCreateNode(srcId, srcEnt.name, srcEnt.type);
          getOrCreateNode(tgtId, tgtEnt.name, tgtEnt.type);

          links.push({ source: srcId, target: tgtId, label: edge });
        }
      }
    });

    return {
      nodes: Array.from(nodesMap.values()),
      links,
    };
  };

  useEffect(() => {
    if (!isOpen || !mountRef.current) return;

    const container = mountRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    const { nodes, links } = parseGraphData();
    if (nodes.length === 0) return;

    // --- Three.js Scene Setup ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a1120);

    // Subtle grid/stars
    const gridHelper = new THREE.GridHelper(600, 30, 0x1e293b, 0x0f172a);
    gridHelper.position.y = -150;
    scene.add(gridHelper);

    // Camera
    const camera = new THREE.PerspectiveCamera(50, width / height, 1, 3000);
    camera.position.set(0, 80, 420);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxDistance = 1200;
    controls.minDistance = 60;
    if (is2DMode) {
      controls.enableRotate = false;
      camera.position.set(0, 0, 420);
    }

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x2dd4bf, 2.5, 1000);
    pointLight.position.set(100, 200, 150);
    scene.add(pointLight);

    // Colors by node type
    const getNodeColor = (type: GraphNode['type']) => {
      switch (type) {
        case 'LabTest':
          return 0x0f766e; // Teal
        case 'Disease':
          return 0xef4444; // Red
        case 'Drug':
          return 0x8b5cf6; // Purple
        case 'Document':
          return 0x3b82f6; // Blue
        case 'Chunk':
          return 0x64748b; // Slate
        default:
          return 0x14b8a6;
      }
    };

    // Node Meshes
    const nodeMeshes: THREE.Mesh[] = [];
    const nodeMapById = new Map<string, GraphNode>();

    nodes.forEach((node) => {
      nodeMapById.set(node.id, node);
      const color = getNodeColor(node.type);
      const radius = node.type === 'Disease' ? 14 : node.type === 'LabTest' ? 12 : node.type === 'Document' ? 10 : 8;

      const geometry = new THREE.SphereGeometry(radius, 24, 24);
      const material = new THREE.MeshStandardMaterial({
        color,
        roughness: 0.25,
        metalness: 0.4,
        emissive: color,
        emissiveIntensity: 0.2,
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(node.x, node.y, node.z);
      (mesh as any).userData = { node };
      scene.add(mesh);
      node.mesh = mesh;
      nodeMeshes.push(mesh);

      // Label sprite
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (ctx) {
        canvas.width = 256;
        canvas.height = 64;
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 20px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.shadowColor = '#000000';
        ctx.shadowBlur = 4;
        const displayName = node.name.length > 18 ? `${node.name.slice(0, 16)}…` : node.name;
        ctx.fillText(displayName, 128, 36);

        const texture = new THREE.CanvasTexture(canvas);
        const spriteMaterial = new THREE.SpriteMaterial({
          map: texture,
          transparent: true,
          opacity: 0.85,
        });
        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.position.set(0, radius + 10, 0);
        sprite.scale.set(60, 15, 1);
        mesh.add(sprite);
      }
    });

    // Links / Edges
    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x475569,
      transparent: true,
      opacity: 0.5,
    });

    const linkLines: { line: THREE.Line; source: GraphNode; target: GraphNode }[] = [];

    links.forEach((link) => {
      const srcNode = nodeMapById.get(link.source);
      const tgtNode = nodeMapById.get(link.target);
      if (srcNode && tgtNode) {
        const lineGeo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(srcNode.x, srcNode.y, srcNode.z),
          new THREE.Vector3(tgtNode.x, tgtNode.y, tgtNode.z),
        ]);
        const line = new THREE.Line(lineGeo, lineMaterial);
        scene.add(line);
        linkLines.push({ line, source: srcNode, target: tgtNode });
      }
    });

    // Raycaster for node clicks
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handlePointerDown = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(nodeMeshes);

      if (intersects.length > 0) {
        const hit = intersects[0].object as THREE.Mesh;
        const node = (hit as any).userData?.node as GraphNode;
        if (node) {
          setSelectedNode(node);
        }
      }
    };

    renderer.domElement.addEventListener('pointerdown', handlePointerDown);

    // Simple Force-Directed Relaxation Simulation
    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const n1 = nodes[i];
          const n2 = nodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const dz = is2DMode ? 0 : n2.z - n1.z;
          const distSq = dx * dx + dy * dy + dz * dz + 1.0;
          const dist = Math.sqrt(distSq);

          if (dist < 320) {
            const force = (800 / distSq);
            n1.vx -= (dx / dist) * force;
            n1.vy -= (dy / dist) * force;
            n1.vz -= is2DMode ? 0 : (dz / dist) * force;
            n2.vx += (dx / dist) * force;
            n2.vy += (dy / dist) * force;
            n2.vz += is2DMode ? 0 : (dz / dist) * force;
          }
        }
      }

      // Spring attraction along links
      linkLines.forEach(({ source: s, target: t }) => {
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dz = is2DMode ? 0 : t.z - s.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.1;
        const force = (dist - 100) * 0.015;

        s.vx += (dx / dist) * force;
        s.vy += (dy / dist) * force;
        s.vz += is2DMode ? 0 : (dz / dist) * force;
        t.vx -= (dx / dist) * force;
        t.vy -= (dy / dist) * force;
        t.vz -= is2DMode ? 0 : (dz / dist) * force;
      });

      // Update positions & line geometry
      nodes.forEach((n) => {
        n.x += n.vx * 0.4;
        n.y += n.vy * 0.4;
        if (!is2DMode) n.z += n.vz * 0.4;
        n.vx *= 0.88;
        n.vy *= 0.88;
        n.vz *= 0.88;

        if (n.mesh) {
          n.mesh.position.set(n.x, n.y, is2DMode ? 0 : n.z);
        }
      });

      linkLines.forEach(({ line, source: s, target: t }) => {
        const posAttr = line.geometry.attributes.position;
        if (posAttr) {
          posAttr.setXYZ(0, s.x, s.y, is2DMode ? 0 : s.z);
          posAttr.setXYZ(1, t.x, t.y, is2DMode ? 0 : t.z);
          posAttr.needsUpdate = true;
        }
      });

      controls.update();
      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      renderer.dispose();
    };
  }, [isOpen, is2DMode, graphPaths, citations]);

  if (!isOpen) return null;

  const hasPaths = graphPaths.length > 0 || citations.length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-md animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-graph-title"
    >
      <div
        className={`relative w-full rounded-2xl border border-card-border bg-card shadow-2xl flex flex-col overflow-hidden transition-all duration-300 ${
          isFullscreen ? 'h-full max-h-[96vh]' : 'max-w-6xl h-[680px]'
        }`}
      >
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-card-border bg-canvas/60 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-brand text-white shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 id="modal-graph-title" className="font-heading font-extrabold text-base text-ink tracking-tight">
                3D Evidence Graph Explorer
              </h3>
              <p className="text-[11px] font-mono text-ink-muted">
                Spatial traversal: {graphPaths.length} multi-hop graph path(s) • {citations.length} evidence citation(s)
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {/* 2D / 3D Toggle */}
            <button
              type="button"
              onClick={() => setIs2DMode(!is2DMode)}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-all cursor-pointer ${
                is2DMode
                  ? 'bg-brand text-white border-brand'
                  : 'bg-card text-ink border-card-border hover:bg-canvas'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>{is2DMode ? '2D Projection' : '3D Spatial'}</span>
            </button>

            {/* Fullscreen Toggle */}
            <button
              type="button"
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="p-2 rounded-lg text-ink-muted hover:text-ink hover:bg-canvas border border-card-border transition-colors cursor-pointer"
              title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg text-ink-muted hover:text-status-danger hover:bg-status-danger-bg border border-card-border transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body: 3D Viewport + Side Inspector */}
        <div className="relative flex-1 grid grid-cols-1 lg:grid-cols-12 min-h-0 bg-[#0a1120]">
          {/* Main 3D Canvas Viewport */}
          <div className={`${selectedNode ? 'lg:col-span-8' : 'lg:col-span-12'} relative h-full w-full`}>
            {!hasPaths ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center text-ink-subtle">
                <GitCommit className="w-12 h-12 mb-3 text-ink-subtle opacity-50" />
                <p className="font-heading font-semibold text-sm text-ink">No Graph Paths Found</p>
                <p className="text-xs font-mono text-ink-subtle mt-1 max-w-sm">
                  This query resolved via direct FAISS vector similarity without multi-hop biomedical graph traversal.
                </p>
              </div>
            ) : (
              <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
            )}

            {/* Legend Overlay */}
            <div className="absolute bottom-4 left-4 p-3 rounded-xl bg-card/85 backdrop-blur-md border border-card-border text-[11px] font-mono space-y-1.5 shadow-lg">
              <span className="text-[10px] uppercase font-bold text-ink-subtle block mb-1">Entity Legend</span>
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#0f766e]" />
                  <span className="text-ink">LabTest</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444]" />
                  <span className="text-ink">Disease</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#3b82f6]" />
                  <span className="text-ink">Document</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#64748b]" />
                  <span className="text-ink">Chunk</span>
                </div>
              </div>
            </div>
          </div>

          {/* Side Inspector Panel for Selected Node */}
          {selectedNode && (
            <div className="lg:col-span-4 p-5 bg-card border-t lg:border-t-0 lg:border-l border-card-border overflow-y-auto space-y-4 animate-fade-in text-left">
              <div className="flex items-center justify-between pb-3 border-b border-card-border">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-brand-surface text-brand border border-brand-border">
                    {selectedNode.type}
                  </span>
                  <h4 className="font-heading font-bold text-sm text-ink truncate">
                    {selectedNode.name}
                  </h4>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded-md text-ink-subtle hover:text-ink hover:bg-canvas"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              {selectedNode.score !== undefined && (
                <div className="p-3 rounded-xl bg-canvas border border-card-border font-mono text-xs space-y-1">
                  <span className="text-[10px] uppercase text-ink-subtle block">RRF Fused Score</span>
                  <span className="text-base font-bold text-brand tabular-nums">
                    {selectedNode.score.toFixed(4)}
                  </span>
                </div>
              )}

              {selectedNode.source && (
                <div className="space-y-1 text-xs font-mono">
                  <span className="text-[10px] uppercase text-ink-subtle block">Source Dataset</span>
                  <p className="text-ink truncate p-2 rounded bg-canvas border border-card-border">
                    {selectedNode.source}
                  </p>
                </div>
              )}

              {selectedNode.snippet && (
                <div className="space-y-1 text-xs">
                  <span className="text-[10px] font-mono uppercase text-ink-subtle block">Evidence Snippet</span>
                  <div className="p-3 rounded-xl bg-canvas border border-card-border text-ink leading-relaxed font-sans max-h-48 overflow-y-auto">
                    "{selectedNode.snippet}"
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
