import { Suspense } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { CopilotClient } from './copilot-client';

export default function CopilotPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40 w-full max-w-3xl" />}>
      <CopilotClient />
    </Suspense>
  );
}
