/**
 * 全局 Error Boundary. React 19 推荐用 class (尚未稳定 hook 版).
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
  info: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, info: null };

  static getDerivedStateFromError(error: Error): State {
    return { error, info: null };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ info });
    console.error('[ErrorBoundary]', error, info);
  }

  reset = (): void => {
    this.setState({ error: null, info: null });
  };

  goHome = (): void => {
    window.location.hash = '/chat';
    this.reset();
  };

  render(): ReactNode {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex h-full items-center justify-center p-6">
          <div className="max-w-md space-y-4 rounded-lg border border-destructive/50 bg-destructive/5 p-6 text-center">
            <AlertTriangle className="mx-auto h-10 w-10 text-destructive" />
            <div>
              <h2 className="text-lg font-semibold">出错了</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                应用遇到了意外错误. 你可以重试或返回首页.
              </p>
            </div>
            <div className="rounded bg-muted px-3 py-2 text-left text-xs font-mono">
              {this.state.error.message}
            </div>
            <div className="flex justify-center gap-2">
              <Button variant="outline" size="sm" onClick={this.reset}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                重试
              </Button>
              <Button size="sm" onClick={this.goHome}>
                <Home className="mr-1.5 h-3.5 w-3.5" />
                返回首页
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
