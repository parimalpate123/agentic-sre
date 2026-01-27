import { useState, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import UtilityPanel from './components/UtilityPanel'

function App() {
  const [isFullScreen, setIsFullScreen] = useState(false)
  const [showUtilityPanel, setShowUtilityPanel] = useState(false)
  const chatWindowRef = useRef(null)

  const handleCloseUtilityPanel = () => {
    setShowUtilityPanel(false)
    // Note: CloudWatch incidents are now loaded on-demand via "CW Incidents" button
    // No need to auto-reload when closing the utility panel
  }

  return (
    <div className={`bg-gradient-to-br from-slate-900 to-slate-800 transition-all ${isFullScreen ? 'fixed inset-0' : 'min-h-screen p-4 md:p-8'}`}>
      {showUtilityPanel ? (
        <div className="mx-auto max-w-6xl py-8">
          <UtilityPanel onClose={handleCloseUtilityPanel} />
        </div>
      ) : (
        <div className={`mx-auto ${isFullScreen ? 'h-screen' : 'h-[calc(100vh-4rem)]'}`}>
          <ChatWindow 
            ref={chatWindowRef}
            isFullScreen={isFullScreen} 
            onToggleFullScreen={() => setIsFullScreen(!isFullScreen)}
            onShowUtilityPanel={() => setShowUtilityPanel(true)}
          />
        </div>
      )}
    </div>
  )
}

export default App
