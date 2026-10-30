import { t } from '@/i18n';
import { Button } from '@/components/ui/button';
import { post } from '@/lib/api';
import { Component, type ErrorInfo, type ReactNode } from 'react';

/**
 * A crash in a part of the page stays in that part: a human message and a way to try again,
 * instead of a blank page. The details go to Narcisse's log (where stack traces belong).
 */
export class ErrorBoundary extends Component<
  { children: ReactNode; label: string },
  { failed: boolean }
> {
  override state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    void post('/client-errors', {
      message: String(error.message || error).slice(0, 2000),
      stack: `${error.stack ?? ''}\n${info.componentStack ?? ''}`.slice(0, 20_000),
      where: window.location.pathname.slice(0, 500),
    }).catch(() => undefined); // offline: nothing more to do
  }

  override render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="grid justify-items-start gap-3 rounded-lg border p-6">
        <p className="font-medium">{t().errorBoundary.failed(this.props.label)}</p>
        <p className="text-sm text-muted-foreground">{t().errorBoundary.details}</p>
        <Button variant="outline" onClick={() => this.setState({ failed: false })}>
          {t().common.retry}
        </Button>
      </div>
    );
  }
}
