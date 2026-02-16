import { useState, useEffect } from 'react';
import { getCompanies } from '../api';

export default function Companies() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadCompanies();
  }, []);

  const loadCompanies = async () => {
    setLoading(true);
    try {
      const data = await getCompanies();
      setCompanies(data.companies);
    } catch (err) {
      console.error('Failed to load companies:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="table-container">
        <div className="table-header">
          <h2>🏢 Компании ({companies.length})</h2>
        </div>

        {loading ? (
          <div>Загрузка...</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Кол-во зарегистрированных</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((company) => (
                <tr key={company.id}>
                  <td>{company.id}</td>
                  <td>{company.name}</td>
                  <td>{company.user_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
