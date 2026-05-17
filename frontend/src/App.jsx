import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'framer-motion';
import { Routes, Route, useLocation } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import AuthPage from './pages/AuthPage.jsx';
import HomePage from './pages/HomePage.jsx';
import SessionPage from './pages/SessionPage.jsx';
import OnboardingPage from './pages/OnboardingPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import ReportsPage from './pages/ReportsPage.jsx';

export default function App() {
  const location = useLocation();
  const reducedMotion = useReducedMotion();
  const hasSharedGradient =
    location.pathname === '/' ||
    location.pathname === '/reports' ||
    location.pathname === '/settings';
  const routePresence = {
    initial: {
      opacity: 0,
      y: reducedMotion ? 0 : 14,
    },
    animate: {
      opacity: 1,
      y: 0,
      transition: reducedMotion
        ? {
            duration: 0.08,
            ease: [0.22, 1, 0.36, 1],
          }
        : {
            opacity: {
              duration: 0.56,
              ease: [0.22, 1, 0.36, 1],
            },
            y: {
              duration: 0.4,
              ease: [0.22, 1, 0.36, 1],
            },
          },
    },
    exit: {
      opacity: 0,
      y: reducedMotion ? 0 : 10,
      transition: {
        duration: reducedMotion ? 0.08 : 0.24,
        ease: [0.32, 0.72, 0, 1],
      },
    },
  };

  return (
    <MotionConfig reducedMotion="user">
      <div className="app-shell">
        {hasSharedGradient && <div className="page-gradient-layer" />}
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            className="app-route-layer"
            initial={routePresence.initial}
            animate={routePresence.animate}
            exit={routePresence.exit}
          >
            <Routes location={location}>
              <Route path="/auth" element={<AuthPage />} />
              <Route element={<ProtectedRoute />}>
                <Route path="/" element={<HomePage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/session/:id" element={<SessionPage />} />
                <Route path="/onboarding" element={<OnboardingPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
            </Routes>
          </motion.div>
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
