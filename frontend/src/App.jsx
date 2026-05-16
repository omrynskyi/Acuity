import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage.jsx';
import SessionPage from './pages/SessionPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/session/:id" element={<SessionPage />} />
    </Routes>
  );
}
