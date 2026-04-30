import { Sidebar } from '@/components/app/sidebar';
import { Topbar } from '@/components/app/topbar';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex bg-surface-900 text-ink">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar />
        <main className="flex-1 px-4 md:px-6 py-6 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
}
