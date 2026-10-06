import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "../../design-system";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorState
          title="Something went wrong"
          description="This area could not be displayed. Retry does not send a command."
          retry={() => this.setState({ hasError: false })}
        />
      );
    }
    return this.props.children;
  }
}
