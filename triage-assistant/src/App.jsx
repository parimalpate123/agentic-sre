import { useState } from 'react'
import ChatWindow from './components/ChatWindow'

function App() {
  const [isFullScreen, setIsFullScreen] = useState(false)

  return (
    <div className={`bg-gradient-to-br from-slate-900 to-slate-800 transition-all ${isFullScreen ? 'fixed inset-0' : 'min-h-screen p-4 md:p-8'}`}>
      <div className={`mx-auto ${isFullScreen ? 'h-screen' : 'h-[calc(100vh-4rem)]'}`}>
        <ChatWindow isFullScreen={isFullScreen} onToggleFullScreen={() => setIsFullScreen(!isFullScreen)} />
      </div>
    </div>
  )
}

export default App
