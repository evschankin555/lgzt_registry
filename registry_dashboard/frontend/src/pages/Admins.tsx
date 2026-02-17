import { useState, useEffect } from 'react';
import { getAdmins } from '../api';

interface Admin {
  tg_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  telegram_link: string | null;
}

export default function Admins() {
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAdmins();
  }, []);

  const loadAdmins = async () => {
    try {
      setLoading(true);
      const data = await getAdmins();
      setAdmins(data.admins);
      setError(null);
    } catch (err) {
      console.error('Failed to load admins:', err);
      setError('Не удалось загрузить список администраторов');
    } finally {
      setLoading(false);
    }
  };

  const getDisplayName = (admin: Admin) => {
    if (admin.first_name || admin.last_name) {
      return `${admin.first_name || ''} ${admin.last_name || ''}`.trim();
    }
    if (admin.username) {
      return `@${admin.username}`;
    }
    return `ID: ${admin.tg_id}`;
  };

  if (loading) {
    return <div>Загрузка...</div>;
  }

  if (error) {
    return (
      <div>
        <div style={{ color: 'red', marginBottom: '20px' }}>{error}</div>
        <button onClick={loadAdmins}>Повторить</button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>👑 Администраторы бота</h2>
        <button onClick={loadAdmins}>🔄 Обновить</button>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Telegram ID</th>
              <th>Имя</th>
              <th>Username</th>
              <th>Ссылка</th>
            </tr>
          </thead>
          <tbody>
            {admins.map((admin) => (
              <tr key={admin.tg_id}>
                <td>{admin.tg_id}</td>
                <td>{getDisplayName(admin)}</td>
                <td>
                  {admin.username ? (
                    <code>@{admin.username}</code>
                  ) : (
                    <span style={{ color: '#999' }}>—</span>
                  )}
                </td>
                <td>
                  {admin.telegram_link ? (
                    <a
                      href={admin.telegram_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-sm"
                    >
                      Открыть в Telegram
                    </a>
                  ) : (
                    <span style={{ color: '#999' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {admins.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
          Нет администраторов
        </div>
      )}
    </div>
  );
}
