'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  FileText,
  LayoutDashboard,
  MessageSquare,
  Search,
  Settings,
  Upload,
} from 'lucide-react';
import type { ComponentType } from 'react';
import { cn } from '@/lib/cn';

type LucideIcon = ComponentType<{ className?: string }>;
type NavItem = {
  href: string;
  label: string;
  icon?: LucideIcon;
  imageSrc?: string;
};

const NAV: readonly NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/upload', label: 'Upload', icon: Upload },
  { href: '/search', label: 'Search', icon: Search },
  { href: '/copilot', label: 'Copilot', icon: MessageSquare },
  { href: '/insights', label: 'Insights', imageSrc: '/insight.png' },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:w-56 flex-col border-r border-ink-faint bg-surface-800">
      <div className="px-2 py-3">
        <Link
          href="/dashboard"
          className="block rounded-md px-1 transition-colors hover:bg-surface-700/40"
        >
          <Image
            src="/logo.png"
            alt="KnowledgeOps AI"
            width={500}
            height={320}
            priority
            className="h-24 w-full object-contain"
          />
        </Link>
      </div>
      <nav className="flex-1 px-2 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon, imageSrc }) => {
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
              {imageSrc ? (
                <Image
                  src={imageSrc}
                  alt=""
                  width={16}
                  height={16}
                  className={cn(
                    'h-4 w-4 object-contain',
                    // The PNG is dark linework; invert it so it reads on the
                    // dark surface tokens, brighten on hover/active.
                    'invert opacity-70',
                    active && 'opacity-100',
                  )}
                />
              ) : Icon ? (
                <Icon className="h-4 w-4" />
              ) : null}
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
