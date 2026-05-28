import { BrowserRouter, Route, Routes } from 'react-router-dom'
import SalonDetailPage from './pages/SalonDetailPage'
import SalonListPage from './pages/SalonListPage'

export default function App() {
  return (
    <BrowserRouter>
      <main className="app">
        <Routes>
          <Route path="/" element={<SalonListPage />} />
          <Route path="/salons/:id" element={<SalonDetailPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
