import { Component } from "react";

/**
 * Catches render errors in the subtree and shows a styled error panel
 * instead of a blank white screen.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error, info);
  }

  reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-6 max-w-lg">
            <h3 className="text-sm font-bold text-red-400 uppercase tracking-widest mb-2">
              Runtime Error Caught
           </h3>
            <pre className="text-xs font-mono text-red-300 whitespace-pre-wrap break-words text-left">
              {this.state.error?.message || String(this.state.error)}
              {"\n\n"}
              {this.state.error?.stack || ""}
           </pre>
            <button
              onClick={this.reset}
              className="mt-4 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider
                         bg-surface-sunken border border-border-subtle text-slate-300
                         hover:border-slate-500 transition-colors"
            >
              Retry
           </button>
         </div>
       </div>
      );
    }
    return this.props.children;
  }
}
