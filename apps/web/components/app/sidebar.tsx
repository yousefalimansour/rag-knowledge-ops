'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Bell,
  FileText,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  Sparkles,
  Upload,
} from 'lucide-react';
import { cn } from '@/lib/cn';

const NAV = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/upload', label: 'Upload', icon: Upload },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/copilot', label: 'Copilot', icon: MessageSquare },
  { href: '/insights', label: 'Insights', icon: Sparkles },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:w-56 flex-col border-r border-ink-faint bg-surface-800">
      <div className="px-4 py-5">
        <Link href="/dashboard" className="flex items-center gap-2 text-base font-semibold tracking-tight">
          <Bell className="h-4 w-4 text-accent" />
          <span>KnowledgeOps AI</span>
        </Link>
      </div>
      <nav className="flex-1 px-2 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-surface-700 text-ink'
                  : 'text-ink-muted hover:bg-surface-700/60 hover:text-ink',
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="px-2 py-4 border-t border-ink-faint">
        <Link
          href="/settings"
          className={cn(
            'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ink-muted hover:bg-surface-700 hover:text-ink',
            pathname.startsWith('/settings') && 'bg-surface-700 text-ink',
          )}
        >
          <Settings className="h-4 w-4" />
          <span>Settings</span>
        </Link>
      </div>
    </aside>
  );
}
