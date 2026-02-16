import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    setIsAuthenticated(!!token);
    setLoading(false);
  }, []);

  if (loading) {
    return <div>Загрузка...</div>;
  }

  return (
    <Router basename="/registry">
      <Routes>
        <Route
          path="/login"
          element={
            isAuthenticated ? (
              <Navigate to="/" replace />
            ) : (
              <Login onLogin={() => setIsAuthenticated(true)} />
            )
          }
        />
        <Route
          path="/*"
          element={
            isAuthenticated ? (
              <Dashboard onLogout={() => setIsAuthenticated(false)} />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
