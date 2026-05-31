import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import IncidentDetail from './pages/IncidentDetail'
import Analytics from './pages/Analytics'

function App() {
  return (
    <div className="min-h-screen flex flex-col bg-devops-dark text-slate-200 font-sans">
      <Navbar />
      <main className="flex-1 overflow-x-hidden overflow-y-auto bg-devops-dark p-6">
        <div className="max-w-7xl mx-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incidents/:id" element={<IncidentDetail />} />
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

export default App
