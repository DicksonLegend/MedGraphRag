import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import {
  MessageSquare,
  FileText,
  TrendingUp,
  ShieldAlert,
  MapPin,
  Shield,
  LogOut,
  Activity,
  User,
  HeartPulse,
  ChevronLeft,
  ChevronRight,
  Database,
  Sparkles,
  Zap,
  Network,
  Cpu,
  Layers,
  CheckCircle2,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';

interface NavItemConfig {
  to: string;
  label: string;
  shortLabel: string;
  icon: React.ElementType;
  shortcut?: string;
  description?: string;
}

export const Sidebar: React.FC = () => {
  const { user_id, role, ephemeral, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const clinicalItems: NavItemConfig[] = [
    {
      to: '/chat',
      label: 'Clinical Query Console',
      shortLabel: 'Console',
      icon: MessageSquare,
      shortcut: '⌘1',
      description: 'Multi-hop GraphRAG clinical evidence query',
    },
    {
      to: '/reports',
      label: 'Diagnostic Reports',
      shortLabel: 'Reports',
      icon: FileText,
      shortcut: '⌘2',
      description: 'EHR lab & imaging ingest vault',
    },
  ];

  const intelligenceItems: NavItemConfig[] = [
    {
      to: '/trends',
      label: 'MedTrend Analytics',
      shortLabel: 'Trends',
      icon: TrendingUp,
      shortcut: '⌘3',
      description: 'Longitudinal biomarker trajectory',
    },
    {
      to: '/caregap',
      label: 'CareGap Reconcile',
      shortLabel: 'CareGap',
      icon: ShieldAlert,
      shortcut: '⌘4',
      description: 'Evidence guideline disparity audit',
    },
    {
      to: '/coverage',
      label: 'Evidence Coverage Map',
      shortLabel: 'Coverage',
      icon: MapPin,
      shortcut: '⌘5',
      description: 'Density decomposition matrix',
    },
  ];

  // Global Keyboard Navigation (⌘1...⌘5 or Ctrl+1...Ctrl+5, plus ⌘B or Ctrl+B for toggle)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey) {
        if (e.key === '1') {
          e.preventDefault();
          navigate('/chat');
        } else if (e.key === '2') {
          e.preventDefault();
          navigate('/reports');
        } else if (e.key === '3') {
          e.preventDefault();
          navigate('/trends');
        } else if (e.key === '4') {
          e.preventDefault();
          navigate('/caregap');
        } else if (e.key === '5') {
          e.preventDefault();
          navigate('/coverage');
        } else if (e.key.toLowerCase() === 'b') {
          e.preventDefault();
          setIsCollapsed((prev) => !prev);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [navigate]);

  const renderNavItem = (item: NavItemConfig) => {
    const Icon = item.icon;
    const isActive = location.pathname === item.to || (item.to === '/chat' && location.pathname === '/');
    const isHovered = hoveredItem === item.to;

    return (
      <div
        key={item.to}
        className="relative"
        onMouseEnter={() => setHoveredItem(item.to)}
        onMouseLeave={() => setHoveredItem(null)}
      >
        {/* Regular Nav Item inside sidebar flow */}
        <NavLink
          to={item.to}
          className={`group/link flex items-center justify-between rounded-xl text-xs font-sans font-medium transition-all duration-200 relative select-none cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-teal-600 active:scale-[0.98] ${
            isCollapsed ? 'px-2 py-2.5 justify-center' : 'px-3 py-2.5'
          } ${
            isActive
              ? 'bg-gradient-to-r from-teal-500/10 via-teal-500/5 to-transparent dark:from-teal-400/15 dark:via-teal-400/5 dark:to-transparent text-[#0F766E] dark:text-[#14B8A6] font-semibold shadow-xs ring-1 ring-teal-500/20 dark:ring-teal-400/20'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100/70 dark:hover:bg-slate-800/60'
          }`}
        >
          {/* Active Accent Bar with Glowing Tip */}
          {isActive && (
            <div className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-[#0F766E] dark:bg-[#14B8A6] shadow-[0_0_8px_rgba(20,184,166,0.6)] animate-fade-in" />
          )}

          <div className="flex items-center space-x-3 min-w-0 flex-1">
            {/* 3D Icon Container with Micro-Tilt */}
            <div
              className={`p-2 rounded-lg transition-all duration-200 shrink-0 transform-gpu ${
                isActive
                  ? 'bg-white dark:bg-slate-900 text-[#0F766E] dark:text-[#14B8A6] shadow-xs ring-1 ring-teal-500/30'
                  : 'bg-slate-100/80 dark:bg-slate-800/70 text-slate-500 dark:text-slate-400 group-hover/link:text-slate-800 dark:group-hover/link:text-slate-200 group-hover/link:scale-110 group-hover/link:-rotate-3 group-hover/link:bg-white dark:group-hover/link:bg-slate-700'
              }`}
            >
              <Icon className="w-4 h-4 stroke-[1.75]" />
            </div>

            {/* Label (Expanded Mode) — Fully visible without truncation */}
            {!isCollapsed && (
              <span className="whitespace-nowrap font-medium tracking-tight text-xs text-slate-800 dark:text-slate-200">
                {item.label}
              </span>
            )}
          </div>

          {/* Keyboard Shortcut (Expanded Mode, subtle on hover) */}
          {!isCollapsed && item.shortcut && (
            <span className="opacity-0 group-hover/link:opacity-100 transition-opacity duration-200 text-[10px] font-mono text-slate-400 dark:text-slate-500 px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shrink-0 ml-1.5">
              {item.shortcut}
            </span>
          )}
        </NavLink>

        {/* ── EXPANDING FLOATING CAPSULE IN SHRINK / COLLAPSED MODE ── */}
        {isCollapsed && isHovered && (
          <div
            className="absolute left-[calc(100%+8px)] top-0 z-50 min-w-[250px] p-3 rounded-2xl bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-xl border border-teal-500/30 dark:border-teal-400/30 shadow-2xl shadow-teal-950/20 text-slate-800 dark:text-slate-100 animate-fade-in pointer-events-auto"
            onClick={() => navigate(item.to)}
          >
            <div className="flex items-center justify-between pb-1.5 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2.5">
                <div
                  className={`p-1.5 rounded-lg ${
                    isActive
                      ? 'bg-teal-50 dark:bg-teal-950/80 text-[#0F766E] dark:text-[#14B8A6]'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                  }`}
                >
                  <Icon className="w-4 h-4 stroke-[1.75]" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold font-sans text-slate-900 dark:text-slate-100 leading-none whitespace-nowrap">
                    {item.label}
                  </h4>
                  {item.description && (
                    <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                      {item.description}
                    </p>
                  )}
                </div>
              </div>

              {item.shortcut && (
                <span className="text-[10px] font-mono text-teal-800 dark:text-teal-300 px-1.5 py-0.5 rounded bg-teal-50 dark:bg-teal-950/80 border border-teal-200 dark:border-teal-800">
                  {item.shortcut}
                </span>
              )}
            </div>

            <div className="pt-1.5 text-[11px] font-mono text-slate-500">
              Status: {isActive ? <strong className="text-[#16A34A]">Active Route</strong> : 'Ready'}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <aside
      className={`shrink-0 bg-white dark:bg-[#0F172A] border-r border-slate-200 dark:border-slate-800 flex flex-col justify-between h-screen sticky top-0 transition-all duration-300 z-40 select-none shadow-sm ${
        isCollapsed ? 'w-[72px]' : 'w-64'
      }`}
    >
      {/* ── TOP SECTION: BRAND HEADER & NAVIGATION ── */}
      <div className="flex flex-col min-h-0 flex-1">
        {/* Brand Header */}
        <div
          className={`border-b border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/50 transition-all duration-200 ${
            isCollapsed ? 'p-3 flex flex-col items-center gap-2' : 'p-4 flex items-center justify-between'
          }`}
        >
          {/* Logo & Brand Name */}
          <div
            onClick={() => {
              if (isCollapsed) setIsCollapsed(false);
            }}
            className={`flex items-center min-w-0 cursor-pointer ${
              isCollapsed ? 'justify-center' : 'space-x-3'
            }`}
            title={isCollapsed ? 'Click to expand sidebar' : 'MedGraphRAG Clinical Workspace'}
          >
            {/* Interactive 3D Emblem */}
            <div className="relative group/logo">
              <div className="absolute -inset-1 bg-gradient-to-r from-teal-500 to-emerald-500 rounded-xl blur-xs opacity-30 group-hover/logo:opacity-80 transition duration-300" />
              <div className="relative p-2 rounded-xl bg-gradient-to-br from-[#0F766E] to-[#115E59] text-white shadow-md transform-gpu group-hover/logo:scale-105 group-hover/logo:rotate-3 transition-transform duration-300 ring-2 ring-teal-500/20">
                <HeartPulse className="w-5 h-5 animate-pulse" />
              </div>
            </div>

            {!isCollapsed && (
              <div className="min-w-0 animate-fade-in">
                <div className="flex items-center space-x-1.5">
                  <h1 className="font-sans font-bold text-sm text-slate-900 dark:text-slate-100 tracking-tight">
                    MedGraph<span className="text-[#0F766E] dark:text-[#14B8A6]">RAG</span>
                  </h1>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                    v1.0.0
                  </span>
                </div>
                <div className="flex items-center space-x-1 text-[10px] font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] animate-pulse" />
                  <span className="uppercase tracking-wider">Clinical AI</span>
                </div>
              </div>
            )}
          </div>

          {/* Explicit Expand/Collapse Button */}
          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={`rounded-lg text-slate-400 hover:text-teal-700 dark:hover:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-950/40 border border-transparent hover:border-teal-200 dark:hover:border-teal-800 transition-all cursor-pointer focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden ${
              isCollapsed ? 'p-1.5 w-full flex items-center justify-center' : 'p-1.5'
            }`}
            title={isCollapsed ? 'Expand Sidebar (⌘B)' : 'Collapse to Rail (⌘B)'}
            aria-label={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          >
            {isCollapsed ? (
              <PanelLeftOpen className="w-4 h-4 stroke-[1.75]" />
            ) : (
              <PanelLeftClose className="w-4 h-4 stroke-[1.75]" />
            )}
          </button>
        </div>

        {/* Navigation Sections */}
        <div className="p-2 space-y-4 overflow-y-auto flex-1">
          {/* Section 1: Core Clinical Workspace */}
          <div className="space-y-1">
            {!isCollapsed ? (
              <div className="flex items-center justify-between px-2.5 mb-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Clinical Workspace
                </span>
                <span className="text-[10px] font-mono text-slate-400">Core</span>
              </div>
            ) : (
              <div className="w-4 h-0.5 bg-slate-200 dark:bg-slate-700 mx-auto my-1.5 rounded" />
            )}

            {clinicalItems.map(renderNavItem)}
          </div>

          {/* Section 2: Longitudinal Intelligence & Discovery */}
          <div className="space-y-1">
            {!isCollapsed ? (
              <div className="flex items-center justify-between px-2.5 mb-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                  Intelligence & Proof
                </span>
                <span className="text-[10px] font-mono text-slate-400">Graph</span>
              </div>
            ) : (
              <div className="w-4 h-0.5 bg-slate-200 dark:bg-slate-700 mx-auto my-1.5 rounded" />
            )}

            {intelligenceItems.map(renderNavItem)}
          </div>

          {/* Section 3: Admin (Conditional) */}
          {role === 'admin' && (
            <div className="space-y-1 pt-1">
              {!isCollapsed && (
                <div className="flex items-center justify-between px-2.5 mb-1">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                    Administration
                  </span>
                </div>
              )}
              {renderNavItem({
                to: '/admin',
                label: 'System Admin',
                shortLabel: 'Admin',
                icon: Shield,
                shortcut: '⌘6',
                description: 'System diagnostics & security controls',
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── BOTTOM SECTION: SYSTEM KNOWLEDGE GAUGE & IDENTITY CARD ── */}
      <div className="border-t border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/60 p-2.5 space-y-2.5">
        {/* Knowledge Graph Micro-Telemetry Widget (Shown when expanded) */}
        {!isCollapsed && (
          <div className="p-2.5 rounded-xl bg-white dark:bg-[#0F172A] border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-1.5 font-mono text-[11px] group/telemetry hover:border-teal-300 dark:hover:border-teal-700 transition-colors">
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400">
              <span className="flex items-center space-x-1 text-[10px] uppercase tracking-wide font-sans font-semibold">
                <Network className="w-3 h-3 text-[#0F766E] dark:text-[#14B8A6] stroke-[1.75]" />
                <span>Knowledge Graph</span>
              </span>
              <span className="h-4 px-1 inline-flex items-center rounded text-[9px] bg-green-50 dark:bg-green-950/60 text-[#16A34A] border border-green-200 dark:border-green-800 font-bold">
                ACTIVE
              </span>
            </div>
            <div className="flex justify-between items-center text-slate-700 dark:text-slate-300">
              <span className="text-slate-500 text-[10px]">Graph Index</span>
              <span className="font-semibold tabular-nums">2.50M nodes · 9 types</span>
            </div>
            <div className="flex justify-between items-center text-slate-700 dark:text-slate-300">
              <span className="text-slate-500 text-[10px]">Vector Density</span>
              <span className="font-semibold tabular-nums">2.20M vectors</span>
            </div>
          </div>
        )}

        {/* User Identity Doppelrand Card */}
        <div
          className={`relative group/user rounded-xl bg-white dark:bg-[#0F172A] border border-slate-200 dark:border-slate-800 p-2 shadow-2xs space-y-2 ${
            isCollapsed ? 'flex flex-col items-center' : ''
          }`}
        >
          <div className="flex items-center space-x-2.5 min-w-0 w-full">
            {/* Avatar Pill with Online Beacon */}
            <div className="relative shrink-0 mx-auto">
              <div className="w-8 h-8 rounded-lg bg-teal-50 dark:bg-teal-950/60 border border-teal-200 dark:border-teal-800 text-[#0F766E] dark:text-[#14B8A6] flex items-center justify-center font-mono font-bold text-xs shadow-2xs">
                {user_id ? user_id.substring(0, 2).toUpperCase() : 'MD'}
              </div>
              <span
                className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white dark:border-[#0F172A] ${
                  ephemeral ? 'bg-amber-500' : 'bg-[#16A34A]'
                }`}
                title={ephemeral ? 'Ephemeral Guest Session' : 'Verified Clinical Practitioner'}
              />
            </div>

            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-xs font-sans font-semibold text-slate-900 dark:text-slate-100 truncate">
                  {user_id || 'Physician User'}
                </p>
                <div className="flex items-center space-x-1 text-[10px] font-mono text-slate-500 dark:text-slate-400">
                  <span className="uppercase">{role || (ephemeral ? 'Guest' : 'Clinician')}</span>
                  <span>·</span>
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Active</span>
                </div>
              </div>
            )}
          </div>

          {/* Sign Out Button */}
          <button
            type="button"
            onClick={handleLogout}
            className={`w-full flex items-center justify-center space-x-1.5 py-1.5 rounded-lg text-xs font-sans font-medium text-slate-600 dark:text-slate-400 hover:text-[#DC2626] hover:bg-red-50/80 dark:hover:bg-red-950/40 border border-slate-200 dark:border-slate-800 hover:border-red-200 dark:hover:border-red-800 transition-all duration-200 cursor-pointer shadow-2xs group/logout focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-hidden`}
            title="Sign out of current clinical session"
            aria-label="Sign out of current clinical session"
          >
            <LogOut className="w-3.5 h-3.5 group-hover/logout:translate-x-0.5 transition-transform duration-200 stroke-[1.75]" />
            {!isCollapsed && <span>Sign Out</span>}
          </button>

          {/* User Popout Card in Collapsed Mode */}
          {isCollapsed && (
            <div className="absolute left-[calc(100%+8px)] bottom-0 z-50 hidden group-hover/user:block p-3 rounded-2xl bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-xl border border-slate-200 dark:border-slate-800 shadow-2xl min-w-[200px] animate-fade-in text-xs font-sans">
              <div className="flex items-center space-x-2 pb-2 border-b border-slate-100 dark:border-slate-800">
                <div className="w-7 h-7 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-[#0F766E] dark:text-[#14B8A6] flex items-center justify-center font-mono font-bold text-xs">
                  {user_id ? user_id.substring(0, 2).toUpperCase() : 'MD'}
                </div>
                <div>
                  <p className="font-semibold text-slate-900 dark:text-slate-100 truncate">
                    {user_id || 'Physician User'}
                  </p>
                  <span className="text-[10px] font-mono text-slate-500 uppercase">
                    {role || (ephemeral ? 'Guest' : 'Clinician')}
                  </span>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 pt-2 font-mono">
                Session: <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Authenticated</span>
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
