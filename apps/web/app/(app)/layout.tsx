import Link from 'next/link';
import { LogoutButton } from './logout-button';

const NAV = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/documents', label: 'Documents' },
  { href: '/copilot', label: 'Copilot' },
  { href: '/insights', label: 'Insights' },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex bg-surface-900 text-ink">
      <aside className="hidden md:flex md:w-56 flex-col border-r border-ink-faint bg-surface-800">
        <div className="px-4 py-5">
          <Link href="/dashboard" className="block text-base font-semibold tracking-tight">
            KnowledgeOps AI
          </Link>
        </div>
        <nav className="flex-1 px-2 space-y-1">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm text-ink-muted hover:bg-surface-700 hover:text-ink"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="px-2 py-4 border-t border-ink-faint">
          <LogoutButton />
        </div>
      </aside>
      <main className="flex-1 px-6 py-6">{children}</main>
    </div>
  );
}
