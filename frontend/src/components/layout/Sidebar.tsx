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
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { user_id, role, ephemeral, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/chat', label: 'Clinical Query', icon: MessageSquare },
    { to: '/reports', label: 'Diagnostic Reports', icon: FileText },
    { to: '/trends', label: 'MedTrend Analytics', icon: TrendingUp },
    { to: '/caregap', label: 'CareGap Reconcile', icon: ShieldAlert },
    { to: '/coverage', label: 'Evidence Coverage', icon: MapPin },
  ];

  if (role === 'admin') {
    navItems.push({ to: '/admin', label: 'System Admin', icon: Shield });
  }

  return (
    <aside className="w-64 shrink-0 bg-card border-r border-card-border flex flex-col justify-between h-screen sticky top-0 transition-colors duration-200">
      {/* Brand Header */}
      <div>
        <div className="p-5 border-b border-card-border flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-brand text-white shadow-sm">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-heading font-extrabold text-base text-ink tracking-tight">
              MedGraph<span className="text-brand">RAG</span>
            </h1>
            <p className="text-[11px] font-mono text-ink-muted">Clinical RAG v1.0.0</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="p-3 space-y-1" aria-label="Main Navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-heading font-medium transition-all ${
                    isActive
                      ? 'bg-brand text-white shadow-xs font-semibold'
                      : 'text-ink-muted hover:text-ink hover:bg-canvas'
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* User Info & Session Controls */}
      <div className="p-4 border-t border-card-border bg-canvas/60 space-y-3">
        <div className="flex items-center space-x-3 px-2">
          <div className="p-2 rounded-full bg-card border border-card-border text-brand">
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
          className="w-full flex items-center justify-center space-x-2 px-3 py-2 rounded-xl text-xs font-heading font-semibold text-ink-muted hover:text-status-danger hover:bg-status-danger-bg border border-card-border hover:border-status-danger/30 transition-colors shadow-2xs"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
