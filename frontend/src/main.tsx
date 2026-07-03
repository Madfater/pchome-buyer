import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'
import { AppStateProvider } from './state'
import { ToastProvider } from './toast'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <AppStateProvider>
        <App />
      </AppStateProvider>
    </ToastProvider>
  </StrictMode>,
)
