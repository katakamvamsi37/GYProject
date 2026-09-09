import { Component } from 'react';
export default class ErrorBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error) {
    console.error('Application error', error);
  }
  render() {
    if (this.state.failed)
      return (
        <main className="fatal-error">
          <h1>Something interrupted the workspace</h1>
          <p>Reload the page to try again. Your saved records are kept on the server.</p>
          <button className="button primary" onClick={() => window.location.reload()}>
            Reload workspace
          </button>
        </main>
      );
    return this.props.children;
  }
}
