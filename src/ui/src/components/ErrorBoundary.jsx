import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Pythia render error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
          padding: 40,
          background: '#0D0D0B',
          color: '#6A6762',
        }}>
          <div style={{
            fontFamily: 'Playfair Display, serif',
            fontStyle: 'italic',
            fontSize: 22,
            color: '#C08878',
          }}>The Oracle encountered an error</div>
          <div style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10,
            color: '#3D3D38',
            maxWidth: 500,
            textAlign: 'center',
            lineHeight: 1.8,
          }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              background: 'transparent',
              border: '1px solid #A88C52',
              color: '#A88C52',
              borderRadius: 4,
              padding: '8px 20px',
              fontFamily: 'Syne, sans-serif',
              fontSize: 12,
              cursor: 'pointer',
              marginTop: 8,
            }}
          >
            Try Again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
