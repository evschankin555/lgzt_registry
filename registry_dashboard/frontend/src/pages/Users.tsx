import { useState, useEffect } from 'react';
import { getUsers, getCompanies, updateUser, deleteUser, exportExcel } from '../api';

export default function Users() {
  const [users, setUsers] = useState<any[]>([]);
  const [companies, setCompanies] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [limit] = useState(20);
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [editingUser, setEditingUser] = useState<any>(null);

  useEffect(() => {
    loadUsers();
    loadCompanies();
  }, [page, status, search]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await getUsers(page, limit, status || undefined, search || undefined);
      setUsers(data.users);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadCompanies = async () => {
    try {
      const data = await getCompanies();
      setCompanies(data.companies);
    } catch (err) {
      console.error('Failed to load companies:', err);
    }
  };

  const handleEdit = (user: any) => {
    setEditingUser(user);
  };

  const handleSaveEdit = async () => {
    if (!editingUser) return;

    try {
      await updateUser(editingUser.id, {
        company_id: editingUser.company_id,
        status: editingUser.status,
      });
      setEditingUser(null);
      loadUsers();
    } catch (err) {
      console.error('Failed to update user:', err);
      alert('Ошибка при обновлении пользователя');
    }
  };

  const handleDelete = async (userId: number) => {
    if (!confirm('Удалить пользователя? (статус будет изменен на "deleted")')) {
      return;
    }

    try {
      await deleteUser(userId);
      loadUsers();
    } catch (err) {
      console.error('Failed to delete user:', err);
      alert('Ошибка при удалении пользователя');
    }
  };

  const handleExport = async () => {
    try {
      await exportExcel();
    } catch (err) {
      console.error('Failed to export:', err);
      alert('Ошибка при экспорте');
    }
  };

  const pages = Math.ceil(total / limit);

  return (
    <div>
      <div className="table-container">
        <div className="table-header">
          <h2>👥 Пользователи ({total.toLocaleString()})</h2>
          <button onClick={handleExport}>📥 Экспорт в Excel</button>
        </div>

        <div className="filters">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
            <option value="">Все статусы</option>
            <option value="registered">Зарегистрированы</option>
            <option value="not registered">Не зарегистрированы</option>
            <option value="blocked">Заблокированы</option>
            <option value="deleted">Удалены</option>
          </select>

          <input
            type="text"
            placeholder="Поиск по ФИО или телефону..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          />
        </div>

        {loading ? (
          <div>Загрузка...</div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>ФИО</th>
                  <th>Телефон</th>
                  <th>Компания</th>
                  <th>Статус</th>
                  <th>Дата регистрации</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td>
                      {user.last_name} {user.first_name} {user.father_name}
                    </td>
                    <td>{user.phone_number || '—'}</td>
                    <td>{user.company_name || '—'}</td>
                    <td>
                      <span className={`status-badge status-${user.status.replace(' ', '-')}`}>
                        {user.status}
                      </span>
                    </td>
                    <td>
                      {user.registered_at
                        ? new Date(user.registered_at).toLocaleString('ru-RU')
                        : '—'}
                    </td>
                    <td>
                      <button className="btn-action" onClick={() => handleEdit(user)}>
                        ✏️ Изменить
                      </button>
                      <button
                        className="btn-action btn-danger"
                        onClick={() => handleDelete(user.id)}
                      >
                        🗑️ Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="pagination">
              <button onClick={() => setPage(0)} disabled={page === 0}>
                ««
              </button>
              <button onClick={() => setPage(page - 1)} disabled={page === 0}>
                «
              </button>
              <span style={{ padding: '8px 12px' }}>
                Страница {page + 1} из {pages}
              </span>
              <button onClick={() => setPage(page + 1)} disabled={page >= pages - 1}>
                »
              </button>
              <button onClick={() => setPage(pages - 1)} disabled={page >= pages - 1}>
                »»
              </button>
            </div>
          </>
        )}
      </div>

      {editingUser && (
        <div className="modal-overlay" onClick={() => setEditingUser(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Редактировать пользователя</h2>
            <p><strong>ФИО:</strong> {editingUser.last_name} {editingUser.first_name} {editingUser.father_name}</p>

            <label>Компания</label>
            <select
              value={editingUser.company_id || ''}
              onChange={(e) =>
                setEditingUser({ ...editingUser, company_id: parseInt(e.target.value) || null })
              }
            >
              <option value="">Не назначена</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            <label>Статус</label>
            <select
              value={editingUser.status}
              onChange={(e) => setEditingUser({ ...editingUser, status: e.target.value })}
            >
              <option value="registered">Зарегистрирован</option>
              <option value="not registered">Не зарегистрирован</option>
              <option value="blocked">Заблокирован</option>
              <option value="deleted">Удален</option>
            </select>

            <div className="modal-buttons">
              <button className="btn-primary" onClick={handleSaveEdit}>
                Сохранить
              </button>
              <button className="btn-secondary" onClick={() => setEditingUser(null)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
