import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
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
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { user_id, role, ephemeral, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const clinicalItems = [
    { to: '/chat', label: 'Clinical Query Console', icon: MessageSquare },
    { to: '/reports', label: 'Diagnostic Reports', icon: FileText },
  ];

  const intelligenceItems = [
    { to: '/trends', label: 'MedTrend Analytics', icon: TrendingUp },
    { to: '/caregap', label: 'CareGap Reconcile', icon: ShieldAlert },
    { to: '/coverage', label: 'Evidence Coverage Map', icon: MapPin },
  ];

  return (
    <aside className="w-64 shrink-0 bg-card border-r border-card-border flex flex-col justify-between h-screen sticky top-0 transition-colors duration-200 z-40">
      {/* Brand Header */}
      <div>
        <div className="p-5 border-b border-card-border flex items-center space-x-3 bg-canvas/30">
          <div className="p-2.5 rounded-xl bg-brand text-white shadow-sm ring-2 ring-brand/20">
            <HeartPulse className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-heading font-extrabold text-base text-ink tracking-tight">
              MedGraph<span className="text-brand">RAG</span>
            </h1>
            <p className="text-[10px] font-mono text-ink-muted uppercase tracking-wider">
              Clinical Intelligence v1.0
            </p>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="p-3 space-y-5 overflow-y-auto">
          {/* Section 1: Core Clinical Workspace */}
          <div className="space-y-1">
            <span className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-ink-subtle block mb-1.5">
              Clinical Workspace
            </span>
            {clinicalItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs font-heading font-semibold transition-all relative ${
                      isActive
                        ? 'bg-brand-surface text-brand border border-brand-border/80 shadow-2xs font-bold'
                        : 'text-ink-muted hover:text-ink hover:bg-canvas'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-brand" />
                      )}
                      <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-brand' : 'text-ink-muted'}`} />
                      <span>{item.label}</span>
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>

          {/* Section 2: Longitudinal Intelligence & Discovery */}
          <div className="space-y-1">
            <span className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-ink-subtle block mb-1.5">
              Intelligence & Proof
            </span>
            {intelligenceItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs font-heading font-semibold transition-all relative ${
                      isActive
                        ? 'bg-brand-surface text-brand border border-brand-border/80 shadow-2xs font-bold'
                        : 'text-ink-muted hover:text-ink hover:bg-canvas'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-brand" />
                      )}
                      <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-brand' : 'text-ink-muted'}`} />
                      <span>{item.label}</span>
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>

          {/* Section 3: Admin (Conditional) */}
          {role === 'admin' && (
            <div className="space-y-1 pt-1">
              <span className="px-3 text-[10px] font-mono font-bold uppercase tracking-wider text-ink-subtle block mb-1.5">
                Administration
              </span>
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs font-heading font-semibold transition-all relative ${
                    isActive
                      ? 'bg-brand-surface text-brand border border-brand-border/80 shadow-2xs font-bold'
                      : 'text-ink-muted hover:text-ink hover:bg-canvas'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-brand" />
                    )}
                    <Shield className={`w-4 h-4 shrink-0 ${isActive ? 'text-brand' : 'text-ink-muted'}`} />
                    <span>System Admin</span>
                  </>
                )}
              </NavLink>
            </div>
          )}
        </div>
      </div>

      {/* User Status Badge & Sign Out */}
      <div className="p-4 border-t border-card-border bg-canvas/60 space-y-3">
        <div className="flex items-center space-x-3 px-1">
          <div className="p-2 rounded-xl bg-card border border-card-border text-brand shadow-2xs">
            <User className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-heading font-bold text-ink truncate">
              {user_id || 'User'}
            </p>
            <div className="flex items-center space-x-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${ephemeral ? 'bg-status-caution' : 'bg-status-success'}`} />
              <span className="text-[10px] font-mono text-ink-subtle uppercase">
                {role || (ephemeral ? 'Guest' : 'User')}
              </span>
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center space-x-2 px-3 py-2 rounded-xl text-xs font-heading font-semibold text-ink-muted hover:text-status-danger hover:bg-status-danger-bg/80 border border-card-border hover:border-status-danger/30 transition-colors shadow-2xs cursor-pointer"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
