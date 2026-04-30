import { Loader2 } from 'lucide-react';
import { Badge } from './badge';

type Status = 'pending' | 'processing' | 'ready' | 'failed';

const TONE = {
  pending: 'muted',
  processing: 'info',
  ready: 'success',
  failed: 'danger',
} as const;

export function StatusPill({ status }: { status: Status }) {
  return (
    <Badge tone={TONE[status]}>
      {(status === 'processing' || status === 'pending') && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      <span>{status}</span>
    </Badge>
  );
}
