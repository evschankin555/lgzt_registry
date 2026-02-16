import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { getStats } from '../api';
import Users from './Users';
import Volunteers from './Volunteers';
import Companies from './Companies';

interface DashboardProps {
  onLogout: () => void;
}

export default function Dashboard({ onLogout }: DashboardProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    onLogout();
  };

  const isActive = (path: string) => {
    if (path === '/' && location.pathname === '/') return true;
    if (path !== '/' && location.pathname.startsWith(path)) return true;
    return false;
  };

  return (
    <div className="dashboard">
      <nav className="navbar">
        <div className="navbar-content">
          <h1>📋 Registry Dashboard</h1>
          <nav>
            <button
              onClick={() => navigate('/')}
              className={isActive('/') ? 'active' : ''}
            >
              Главная
            </button>
            <button
              onClick={() => navigate('/users')}
              className={isActive('/users') ? 'active' : ''}
            >
              Пользователи
            </button>
            <button
              onClick={() => navigate('/volunteers')}
              className={isActive('/volunteers') ? 'active' : ''}
            >
              Волонтеры
            </button>
            <button
              onClick={() => navigate('/companies')}
              className={isActive('/companies') ? 'active' : ''}
            >
              Компании
            </button>
          </nav>
          <button onClick={handleLogout} className="logout-btn">
            Выйти
          </button>
        </div>
      </nav>

      <div className="container">
        <Routes>
          <Route path="/" element={<Home stats={stats} />} />
          <Route path="/users" element={<Users />} />
          <Route path="/volunteers" element={<Volunteers />} />
          <Route path="/companies" element={<Companies />} />
        </Routes>
      </div>
    </div>
  );
}

function Home({ stats }: { stats: any }) {
  if (!stats) {
    return <div>Загрузка статистики...</div>;
  }

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>📊 Статистика</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Всего в базе</h3>
          <div className="value">{stats.total?.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <h3>Зарегистрировано</h3>
          <div className="value">{stats.registered?.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <h3>Компаний</h3>
          <div className="value">{stats.companies}</div>
        </div>
        <div className="stat-card">
          <h3>Волонтеров</h3>
          <div className="value">{stats.volunteers}</div>
        </div>
        <div className="stat-card">
          <h3>За сегодня</h3>
          <div className="value">{stats.today}</div>
        </div>
        <div className="stat-card">
          <h3>За неделю</h3>
          <div className="value">{stats.week}</div>
        </div>
        <div className="stat-card">
          <h3>За месяц</h3>
          <div className="value">{stats.month}</div>
        </div>
      </div>
    </div>
  );
}
