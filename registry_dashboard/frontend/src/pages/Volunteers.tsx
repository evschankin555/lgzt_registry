import { useState, useEffect } from 'react';
import { getVolunteers, updateVolunteer, deleteVolunteer } from '../api';

export default function Volunteers() {
  const [volunteers, setVolunteers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingVolunteer, setEditingVolunteer] = useState<any>(null);

  useEffect(() => {
    loadVolunteers();
  }, []);

  const loadVolunteers = async () => {
    setLoading(true);
    try {
      const data = await getVolunteers();
      setVolunteers(data.volunteers);
    } catch (err) {
      console.error('Failed to load volunteers:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (volunteer: any) => {
    setEditingVolunteer({ ...volunteer });
  };

  const handleSaveEdit = async () => {
    if (!editingVolunteer || !editingVolunteer.name.trim()) {
      alert('Введите имя волонтера');
      return;
    }

    try {
      await updateVolunteer(editingVolunteer.id, editingVolunteer.name);
      setEditingVolunteer(null);
      loadVolunteers();
    } catch (err) {
      console.error('Failed to update volunteer:', err);
      alert('Ошибка при обновлении волонтера');
    }
  };

  const handleDelete = async (volunteerId: number) => {
    if (!confirm('Удалить волонтера?')) {
      return;
    }

    try {
      await deleteVolunteer(volunteerId);
      loadVolunteers();
    } catch (err) {
      console.error('Failed to delete volunteer:', err);
      alert('Ошибка при удалении волонтера');
    }
  };

  return (
    <div>
      <div className="table-container">
        <div className="table-header">
          <h2>🙋 Волонтеры ({volunteers.length})</h2>
        </div>

        {loading ? (
          <div>Загрузка...</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Telegram ID</th>
                <th>Имя</th>
                <th>Дата добавления</th>
                <th>Добавил (TG ID)</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {volunteers.map((volunteer) => (
                <tr key={volunteer.id}>
                  <td>{volunteer.id}</td>
                  <td>{volunteer.tg_id}</td>
                  <td>{volunteer.name || '—'}</td>
                  <td>
                    {volunteer.added_at
                      ? new Date(volunteer.added_at).toLocaleString('ru-RU')
                      : '—'}
                  </td>
                  <td>{volunteer.added_by || '—'}</td>
                  <td>
                    <button
                      className="btn-action"
                      onClick={() => handleEdit(volunteer)}
                    >
                      ✏️ Изменить имя
                    </button>
                    <button
                      className="btn-action btn-danger"
                      onClick={() => handleDelete(volunteer.id)}
                    >
                      🗑️ Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editingVolunteer && (
        <div className="modal-overlay" onClick={() => setEditingVolunteer(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Редактировать имя волонтера</h2>
            <p><strong>Telegram ID:</strong> {editingVolunteer.tg_id}</p>

            <label>Имя</label>
            <input
              type="text"
              value={editingVolunteer.name || ''}
              onChange={(e) =>
                setEditingVolunteer({ ...editingVolunteer, name: e.target.value })
              }
              placeholder="Введите имя волонтера"
            />

            <div className="modal-buttons">
              <button className="btn-primary" onClick={handleSaveEdit}>
                Сохранить
              </button>
              <button className="btn-secondary" onClick={() => setEditingVolunteer(null)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
