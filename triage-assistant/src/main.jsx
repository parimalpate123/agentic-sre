import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import KBPage from './pages/KBPage.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<App />} />
        <Route path="/chat/:sessionId" element={<App />} />
        <Route path="/knowledge-base" element={<KBPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
