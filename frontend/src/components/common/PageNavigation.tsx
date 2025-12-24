/**
 * Page Navigation Component
 *
 * Breadcrumb-style navigation slider that appears on all internal pages.
 * Shows navigation links to all main sections.
 */

import React from 'react';
import {
  Home,
  Package,
  FileText,
  ChevronRight,
  Layers,
} from 'lucide-react';

export type PageId = 'home' | 'products' | 'research' | 'demo';

interface PageNavItem {
  id: PageId;
  label: string;
  icon: React.ReactNode;
}

const navItems: PageNavItem[] = [
  { id: 'home', label: 'Home', icon: <Home className="w-3.5 h-3.5" /> },
  { id: 'products', label: 'Products', icon: <Package className="w-3.5 h-3.5" /> },
  { id: 'research', label: 'Research', icon: <FileText className="w-3.5 h-3.5" /> },
  { id: 'demo', label: 'Demo', icon: <Layers className="w-3.5 h-3.5" /> },
];

interface PageNavigationProps {
  currentPage: PageId;
  breadcrumbs?: { label: string; onClick?: () => void }[];
  onNavigate: (page: PageId) => void;
}

export function PageNavigation({ currentPage, breadcrumbs, onNavigate }: PageNavigationProps) {
  return (
    <div className="flex items-center justify-between">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm">
        {breadcrumbs?.map((crumb, index) => (
          <React.Fragment key={index}>
            {index > 0 && <ChevronRight className="w-3.5 h-3.5 text-gray-500" />}
            {crumb.onClick ? (
              <button
                onClick={crumb.onClick}
                className="text-gray-400 hover:text-white transition-colors"
              >
                {crumb.label}
              </button>
            ) : (
              <span className="text-white font-medium">{crumb.label}</span>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Navigation Slider */}
      <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              currentPage === item.id
                ? 'bg-white/10 text-white'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Internal Page Header
 *
 * Consistent header for all internal pages with Symbol-μ branding
 * and navigation.
 */
interface InternalPageHeaderProps {
  currentPage: PageId;
  breadcrumbs?: { label: string; onClick?: () => void }[];
  onNavigate: (page: PageId) => void;
}

export function InternalPageHeader({ currentPage, breadcrumbs, onNavigate }: InternalPageHeaderProps) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-slate-950/90 backdrop-blur-md border-b border-white/5">
      <div className="max-w-7xl mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          {/* Logo - Symbol-μ in Helvetica Bold */}
          <button
            onClick={() => onNavigate('home')}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
          >
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <span
                className="text-white text-lg"
                style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
              >
                μ
              </span>
            </div>
            <span
              className="text-xl text-white"
              style={{ fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700 }}
            >
              Symbol-μ
            </span>
          </button>

          {/* Navigation */}
          <PageNavigation
            currentPage={currentPage}
            breadcrumbs={breadcrumbs}
            onNavigate={onNavigate}
          />
        </div>
      </div>
    </header>
  );
}
