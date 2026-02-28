import { useState, useRef } from 'react'
import ChatLayout from './components/ChatLayout'
import UtilityPanel from './components/UtilityPanel'

function App() {
  const [isFullScreen, setIsFullScreen] = useState(false)
  const [showUtilityPanel, setShowUtilityPanel] = useState(false)
  const chatWindowRef = useRef(null)

  const handleCloseUtilityPanel = () => {
    setShowUtilityPanel(false)
  }

  return (
    <div className={`bg-gray-50 transition-all ${isFullScreen ? 'fixed inset-0' : 'min-h-screen'}`}>
      {showUtilityPanel ? (
        <div className="mx-auto max-w-6xl py-8 px-4">
          <UtilityPanel onClose={handleCloseUtilityPanel} />
        </div>
      ) : (
        <div className={isFullScreen ? 'h-screen' : 'h-screen'}>
          <ChatLayout
            isFullScreen={isFullScreen}
            onToggleFullScreen={() => setIsFullScreen(!isFullScreen)}
            onShowUtilityPanel={() => setShowUtilityPanel(true)}
            chatWindowRef={chatWindowRef}
          />
        </div>
      )}
    </div>
  )
}

export default App
