import { useState } from 'react';
import { login } from '../api';

interface LoginProps {
  onLogin: () => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await login(password);
      localStorage.setItem('token', data.access_token);
      onLogin();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Неверный пароль');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Registry Dashboard</h1>
        {error && <div className="error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="Пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  );
}
