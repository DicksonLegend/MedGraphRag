import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { CitationMeta } from '../../api/types';
import {
  Maximize2,
  Minimize2,
  X,
  RotateCcw,
  Play,
  Pause,
  Eye,
  EyeOff,
  GitCommit,
  Share2,
} from 'lucide-react';

interface GraphNode {
  id: string;
  name: string;
  type: 'LabTest' | 'Disease' | 'Drug' | 'Document' | 'Chunk' | 'Entity';
  snippet?: string;
  score?: number;
  source?: string;
  citationsCount: number;
  isProvenance: boolean;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  mesh?: THREE.Mesh;
  sprite?: THREE.Sprite;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
  isProvenance: boolean;
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
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  const [is2DMode, setIs2DMode] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);

  // Parse nodes & links from graph_paths and citations
  const parseGraphData = () => {
    const nodesMap: Map<string, GraphNode> = new Map();
    const links: GraphLink[] = [];

    const getOrCreateNode = (
      id: string,
      name: string,
      type: GraphNode['type'],
      extra?: Partial<GraphNode>
    ) => {
      if (!nodesMap.has(id)) {
        const u = Math.random();
        const v = Math.random();
        const theta = u * 2.0 * Math.PI;
        const phi = Math.acos(2.0 * v - 1.0);
        const r = 160 + Math.random() * 90;
        const sinPhi = Math.sin(phi);

        nodesMap.set(id, {
          id,
          name,
          type,
          citationsCount: 1,
          isProvenance: false,
          x: r * sinPhi * Math.cos(theta),
          y: r * sinPhi * Math.sin(theta),
          z: is2DMode ? 0 : r * Math.cos(phi),
          vx: 0,
          vy: 0,
          vz: 0,
          ...extra,
        });
      } else {
        const existing = nodesMap.get(id)!;
        existing.citationsCount += 1;
        if (extra) {
          Object.assign(existing, extra);
        }
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
        isProvenance: false,
      });
    });

    // 2. Parse graph_paths (provenance paths)
    graphPaths.slice(0, 3).forEach((pathStr) => {
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

          const n1 = getOrCreateNode(srcId, srcEnt.name, srcEnt.type, { isProvenance: true });
          const n2 = getOrCreateNode(tgtId, tgtEnt.name, tgtEnt.type, { isProvenance: true });
          n1.isProvenance = true;
          n2.isProvenance = true;

          links.push({ source: srcId, target: tgtId, label: edge, isProvenance: true });
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

    // --- Scene Setup ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a); // Explicit #0F172A

    // Subtle dark grid
    const gridHelper = new THREE.GridHelper(600, 30, 0x1e293b, 0x1e293b);
    gridHelper.position.y = -150;
    scene.add(gridHelper);

    // Camera
    const camera = new THREE.PerspectiveCamera(50, width / height, 1, 3000);
    camera.position.set(0, 70, 420);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
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
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 0.8;
    controlsRef.current = controls;

    if (is2DMode) {
      controls.enableRotate = false;
      camera.position.set(0, 0, 420);
    }

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x14b8a6, 2.8, 1000);
    pointLight.position.set(120, 200, 160);
    scene.add(pointLight);

    // Node Colors
    const getNodeColor = (type: GraphNode['type']) => {
      switch (type) {
        case 'LabTest':
          return 0x0f766e;
        case 'Disease':
          return 0xdc2626;
        case 'Drug':
          return 0x2563eb;
        case 'Document':
          return 0x64748b;
        case 'Chunk':
          return 0x475569;
        default:
          return 0x14b8a6;
      }
    };

    const nodeMeshes: THREE.Mesh[] = [];
    const nodeMapById = new Map<string, GraphNode>();

    // Create Node Meshes (Size proportional to citation count / score)
    nodes.forEach((node) => {
      nodeMapById.set(node.id, node);
      const color = getNodeColor(node.type);

      const baseRadius = node.type === 'Disease' ? 14 : node.type === 'LabTest' ? 12 : node.type === 'Document' ? 10 : 8;
      const radius = Math.min(22, baseRadius + (node.citationsCount > 1 ? node.citationsCount * 1.5 : 0));

      const geometry = new THREE.SphereGeometry(radius, 24, 24);
      const material = new THREE.MeshStandardMaterial({
        color: node.isProvenance ? 0x14b8a6 : color,
        roughness: 0.2,
        metalness: 0.5,
        emissive: node.isProvenance ? 0x14b8a6 : color,
        emissiveIntensity: node.isProvenance ? 0.45 : 0.15,
        opacity: node.isProvenance ? 1.0 : 0.7,
        transparent: true,
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(node.x, node.y, node.z);
      (mesh as any).userData = { node };
      scene.add(mesh);
      node.mesh = mesh;
      nodeMeshes.push(mesh);

      // Label Sprite with Dark Halo
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (ctx) {
        canvas.width = 384;
        canvas.height = 96;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        ctx.font = 'bold 24px "IBM Plex Mono", monospace';
        ctx.strokeStyle = '#0b1220';
        ctx.lineWidth = 6;
        const displayName = node.name.length > 20 ? `${node.name.slice(0, 18)}…` : node.name;
        ctx.strokeText(displayName, 192, 48);

        ctx.fillStyle = node.isProvenance ? '#2dd4bf' : '#f8fafc';
        ctx.fillText(displayName, 192, 48);

        const texture = new THREE.CanvasTexture(canvas);
        const spriteMaterial = new THREE.SpriteMaterial({
          map: texture,
          transparent: true,
          opacity: showLabels ? 0.95 : 0,
        });
        const sprite = new THREE.Sprite(spriteMaterial);
        sprite.position.set(0, radius + 12, 0);
        sprite.scale.set(70, 18, 1);
        mesh.add(sprite);
        node.sprite = sprite;
      }
    });

    // Link Lines
    const linkLines: { line: THREE.Line; source: GraphNode; target: GraphNode; link: GraphLink }[] = [];

    links.forEach((link) => {
      const srcNode = nodeMapById.get(link.source);
      const tgtNode = nodeMapById.get(link.target);
      if (srcNode && tgtNode) {
        const lineGeo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(srcNode.x, srcNode.y, srcNode.z),
          new THREE.Vector3(tgtNode.x, tgtNode.y, tgtNode.z),
        ]);

        const lineMaterial = new THREE.LineBasicMaterial({
          color: link.isProvenance ? 0x14b8a6 : 0x334155,
          transparent: true,
          opacity: link.isProvenance ? 0.9 : 0.35,
          linewidth: link.isProvenance ? 2 : 1,
        });

        const line = new THREE.Line(lineGeo, lineMaterial);
        scene.add(line);
        linkLines.push({ line, source: srcNode, target: tgtNode, link });
      }
    });

    // Raycaster for Hover and Click
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handlePointerMove = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(nodeMeshes);

      if (intersects.length > 0) {
        const hit = intersects[0].object as THREE.Mesh;
        const node = (hit as any).userData?.node as GraphNode;
        if (node) {
          setHoveredNode(node);
          setTooltipPos({ x: event.clientX - rect.left, y: event.clientY - rect.top });
        }
      } else {
        setHoveredNode(null);
        setTooltipPos(null);
      }
    };

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

    renderer.domElement.addEventListener('mousemove', handlePointerMove);
    renderer.domElement.addEventListener('pointerdown', handlePointerDown);

    // Force-Directed Relaxation Simulation
    let animationFrameId: number;
    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Repulsion between nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const n1 = nodes[i];
          const n2 = nodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const dz = is2DMode ? 0 : n2.z - n1.z;
          const distSq = dx * dx + dy * dy + dz * dz + 1.0;
          const dist = Math.sqrt(distSq);

          if (dist < 340) {
            const force = 750 / distSq;
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
        const force = (dist - 110) * 0.012;

        s.vx += (dx / dist) * force;
        s.vy += (dy / dist) * force;
        s.vz += is2DMode ? 0 : (dz / dist) * force;
        t.vx -= (dx / dist) * force;
        t.vy -= (dy / dist) * force;
        t.vz -= is2DMode ? 0 : (dz / dist) * force;
      });

      // Update positions
      nodes.forEach((n) => {
        n.x += n.vx * 0.35;
        n.y += n.vy * 0.35;
        if (!is2DMode) n.z += n.vz * 0.35;
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
      renderer.domElement.removeEventListener('mousemove', handlePointerMove);
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      renderer.dispose();
    };
  }, [isOpen, is2DMode, autoRotate, showLabels, graphPaths, citations]);

  const handleResetView = () => {
    if (cameraRef.current && controlsRef.current) {
      cameraRef.current.position.set(0, 70, 420);
      controlsRef.current.target.set(0, 0, 0);
      controlsRef.current.update();
    }
  };

  if (!isOpen) return null;

  const hasPaths = graphPaths.length > 0 || citations.length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-sm animate-fade-in font-sans"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-graph-title"
    >
      <div
        className={`relative w-full rounded-lg border border-slate-800 bg-[#0F172A] shadow-2xl flex flex-col overflow-hidden transition-all duration-200 ${
          isFullscreen ? 'h-full max-h-[96vh]' : 'max-w-6xl h-[680px]'
        }`}
      >
        {/* Modal Header: Deleted "Canvas #0F172A" */}
        <div className="p-3.5 sm:p-4 border-b border-slate-800 bg-[#0F172A] flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <div className="p-1.5 rounded-lg bg-teal-950/80 border border-teal-800 text-[#14B8A6]">
              <GitCommit className="w-4 h-4 stroke-[1.75]" />
            </div>
            <div>
              <h3 id="modal-graph-title" className="font-semibold text-sm text-slate-100 tracking-tight">
                3D Evidence Knowledge Graph Explorer
              </h3>
              <p className="text-[11px] font-mono text-slate-400">
                {graphPaths.length} multi-hop provenance path(s) • {citations.length} evidence citation(s)
              </p>
            </div>
          </div>

          {/* Explorer Controls: 28px height chips */}
          <div className="flex items-center space-x-2">
            {/* Auto-Rotate Toggle */}
            <button
              type="button"
              onClick={() => setAutoRotate(!autoRotate)}
              className={`flex items-center space-x-1 h-7 px-2.5 rounded-lg text-xs font-mono border transition-all cursor-pointer ${
                autoRotate
                  ? 'bg-slate-100 text-slate-900 border-slate-100 font-semibold'
                  : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
              title="Toggle Auto-Rotation"
              aria-label="Toggle auto rotation"
            >
              {autoRotate ? <Pause className="w-3 h-3 stroke-[1.75]" /> : <Play className="w-3 h-3 stroke-[1.75]" />}
              <span>{autoRotate ? 'Rotating' : 'Paused'}</span>
            </button>

            {/* Labels Toggle */}
            <button
              type="button"
              onClick={() => setShowLabels(!showLabels)}
              className={`flex items-center space-x-1 h-7 px-2.5 rounded-lg text-xs font-mono border transition-all cursor-pointer ${
                showLabels
                  ? 'bg-slate-100 text-slate-900 border-slate-100 font-semibold'
                  : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
              title="Toggle Node Labels"
              aria-label="Toggle node labels"
            >
              {showLabels ? <Eye className="w-3 h-3 stroke-[1.75]" /> : <EyeOff className="w-3 h-3 stroke-[1.75]" />}
              <span>Labels</span>
            </button>

            {/* Reset View */}
            <button
              type="button"
              onClick={handleResetView}
              className="h-7 px-2 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 transition-colors cursor-pointer"
              title="Reset View Position"
              aria-label="Reset 3D camera view"
            >
              <RotateCcw className="w-3.5 h-3.5 stroke-[1.75]" />
            </button>

            {/* Fullscreen Toggle */}
            <button
              type="button"
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="h-7 px-2 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 transition-colors cursor-pointer"
              title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
              aria-label="Toggle fullscreen"
            >
              {isFullscreen ? <Minimize2 className="w-3.5 h-3.5 stroke-[1.75]" /> : <Maximize2 className="w-3.5 h-3.5 stroke-[1.75]" />}
            </button>

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="h-7 px-2 flex items-center justify-center rounded-lg text-slate-400 hover:text-red-400 bg-slate-900 border border-slate-800 transition-colors cursor-pointer"
              aria-label="Close 3D explorer modal"
            >
              <X className="w-3.5 h-3.5 stroke-[1.75]" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="relative flex-1 grid grid-cols-1 lg:grid-cols-12 min-h-0 bg-[#0F172A]">
          {/* Main 3D Canvas Viewport */}
          <div className={`${selectedNode ? 'lg:col-span-8' : 'lg:col-span-12'} relative h-full w-full`}>
            {!hasPaths ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center text-slate-500">
                <GitCommit className="w-10 h-10 mb-2 text-slate-600 stroke-[1.75]" />
                <p className="font-semibold text-xs text-slate-300">No Graph Paths Found</p>
                <p className="text-[11px] font-mono text-slate-500 mt-1 max-w-sm">
                  Direct FAISS similarity without multi-hop traversal.
                </p>
              </div>
            ) : (
              <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
            )}

            {/* Interactive Hover Tooltip */}
            {hoveredNode && tooltipPos && (
              <div
                className="absolute z-30 pointer-events-none p-2 rounded bg-slate-900/95 border border-slate-700 text-[11px] font-mono text-slate-200 shadow-xl space-y-0.5"
                style={{
                  left: Math.min(tooltipPos.x + 12, (mountRef.current?.clientWidth || 800) - 220),
                  top: tooltipPos.y + 12,
                }}
              >
                <div className="flex items-center space-x-1 font-semibold text-[#14B8A6]">
                  <span>{hoveredNode.type}:</span>
                  <span className="text-slate-100">{hoveredNode.name}</span>
                </div>
                <div className="text-[10px] text-slate-400">ID: {hoveredNode.id}</div>
                {hoveredNode.score !== undefined && (
                  <div className="text-[10px] text-[#16A34A] font-semibold">
                    RRF Score: {hoveredNode.score.toFixed(4)}
                  </div>
                )}
                {hoveredNode.isProvenance && (
                  <div className="text-[9px] text-[#14B8A6] uppercase font-semibold">★ Provenance Path Node</div>
                )}
              </div>
            )}

            {/* Entity Legend */}
            <div className="absolute bottom-3 left-3 p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-[11px] font-mono space-y-1 shadow-md">
              <span className="uppercase font-medium text-slate-400 block mb-1 text-[10px] tracking-wide">
                Entity Legend
              </span>
              <div className="flex flex-wrap items-center gap-2.5">
                <div className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-[#14b8a6]" />
                  <span className="text-slate-200 font-semibold">Provenance</span>
                </div>
                <div className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-[#0f766e]" />
                  <span className="text-slate-300">LabTest</span>
                </div>
                <div className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-[#dc2626]" />
                  <span className="text-slate-300">Disease</span>
                </div>
                <div className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-[#2563eb]" />
                  <span className="text-slate-300">Drug</span>
                </div>
                <div className="flex items-center space-x-1">
                  <span className="w-2 h-2 rounded-full bg-[#64748b]" />
                  <span className="text-slate-400">Document/Chunk</span>
                </div>
              </div>
            </div>
          </div>

          {/* Side Inspector for Selected Node */}
          {selectedNode && (
            <div className="lg:col-span-4 p-4 bg-[#0F172A] border-t lg:border-t-0 lg:border-l border-slate-800 overflow-y-auto space-y-3 animate-fade-in text-left">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div className="flex items-center space-x-2">
                  <span className="h-6 px-2 flex items-center text-[10px] font-mono font-semibold rounded bg-teal-950 text-teal-300 border border-teal-800">
                    {selectedNode.type}
                  </span>
                  <h4 className="font-semibold text-xs text-slate-100 truncate">
                    {selectedNode.name}
                  </h4>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                >
                  <X className="w-3.5 h-3.5 stroke-[1.75]" />
                </button>
              </div>

              {selectedNode.score !== undefined && (
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 font-mono text-xs space-y-0.5">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">RRF Fused Score</span>
                  <span className="text-sm font-semibold text-[#14B8A6] tabular-nums">
                    {selectedNode.score.toFixed(4)}
                  </span>
                </div>
              )}

              {selectedNode.source && (
                <div className="space-y-1 text-xs font-mono">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Source Dataset</span>
                  <p className="text-slate-300 truncate p-2 rounded bg-slate-900 border border-slate-800 text-[11px]">
                    {selectedNode.source}
                  </p>
                </div>
              )}

              {selectedNode.snippet && (
                <div className="space-y-1 text-xs">
                  <span className="text-[10px] font-mono uppercase text-slate-400 block font-medium">Evidence Snippet</span>
                  <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-slate-300 leading-relaxed font-sans max-h-40 overflow-y-auto text-[12px]">
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
