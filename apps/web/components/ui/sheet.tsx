'use client';

import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  children: ReactNode;
  side?: 'right' | 'left';
  widthClassName?: string;
};

export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  side = 'right',
  widthClassName = 'w-full sm:max-w-md',
}: SheetProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            'fixed top-0 z-50 h-full bg-surface-800 border-ink-faint shadow-card focus:outline-none flex flex-col',
            side === 'right' ? 'right-0 border-l' : 'left-0 border-r',
            widthClassName,
          )}
        >
          <header className="flex items-start justify-between gap-4 border-b border-ink-faint px-5 py-4">
            <div>
              {title && <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>}
              {description && (
                <Dialog.Description className="mt-1 text-sm text-ink-muted">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close
              className="rounded-md p-1 text-ink-muted hover:bg-surface-700 hover:text-ink"
              aria-label="Close panel"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
