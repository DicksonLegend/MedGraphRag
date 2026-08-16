import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { GuestBanner } from './GuestBanner';

interface AppShellProps {
  title?: string;
  subtitle?: string;
}

export const AppShell: React.FC<AppShellProps> = ({ title, subtitle }) => {
  return (
    <div className="flex h-screen overflow-hidden bg-canvas text-ink transition-colors duration-200">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Topbar title={title} subtitle={subtitle} />
        <GuestBanner />
        
        <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-7xl w-full mx-auto animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
