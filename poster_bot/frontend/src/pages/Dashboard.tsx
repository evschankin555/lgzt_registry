import { useState, useEffect, useCallback } from 'react';
import api from '../api';

interface DashboardProps {
  onLogout: () => void;
}

interface Stats {
  accounts: number;
  groups: number;
  groups_joined: number;
  posts: number;
  successful_sends: number;
}

interface GroupStats {
  pending: number;
  joining: number;
  joined: number;
  failed: number;
  total: number;
}

interface JoiningStatus {
  is_running: boolean;
  stats: {
    pending: number;
    joining: number;
    joined: number;
    failed: number;
    current_group: string | null;
    next_attempt_in: number;
  };
}

interface TelegramAccount {
  id: number;
  phone: string;
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  is_authorized: boolean;
}

interface Group {
  id: number;
  telegram_id: string;
  title: string;
  link: string;
  city: string | null;
  address: string | null;
  status: string;
  is_joined: boolean;
  join_error: string | null;
  join_attempts: number;
  source: string;
}

interface Post {
  id: number;
  caption: string;
  status: string;
  created_at: string;
  success_count: number;
  fail_count: number;
  total_groups: number;
}

interface PostDetail {
  id: number;
  caption: string;
  status: string;
  created_at: string;
  results: Array<{
    group_id: number;
    group_title: string;
    status: string;
    error: string | null;
    message_link: string | null;
  }>;
}

function Dashboard({ onLogout }: DashboardProps) {
  const [activeTab, setActiveTab] = useState('overview');
  const [stats, setStats] = useState<Stats | null>(null);
  const [groupStats, setGroupStats] = useState<GroupStats | null>(null);
  const [accounts, setAccounts] = useState<TelegramAccount[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [joiningStatus, setJoiningStatus] = useState<JoiningStatus | null>(null);

  // Phone auth state
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [password2fa, setPassword2fa] = useState('');
  const [authStep, setAuthStep] = useState<'phone' | 'code' | '2fa' | 'done'>('phone');
  const [authUser, setAuthUser] = useState<any>(null);
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  // Import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const [updateExisting, setUpdateExisting] = useState(false);

  // Send form state
  const [selectedAccount, setSelectedAccount] = useState('');
  const [groupFilter, setGroupFilter] = useState('joined');
  const [selectedGroups, setSelectedGroups] = useState<number[]>([]);
  const [caption, setCaption] = useState('');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [delaySeconds, setDelaySeconds] = useState(5);
  const [sendLoading, setSendLoading] = useState(false);
  const [sendResult, setSendResult] = useState<any>(null);

  // Post detail
  const [selectedPost, setSelectedPost] = useState<PostDetail | null>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState('');

  const loadStats = useCallback(async () => {
    try {
      const res = await api.get('/api/stats');
      setStats(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadGroupStats = useCallback(async () => {
    try {
      const res = await api.get('/api/groups/stats');
      setGroupStats(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadAccounts = useCallback(async () => {
    try {
      const res = await api.get('/api/telegram/accounts');
      setAccounts(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadGroups = useCallback(async (filter?: string) => {
    try {
      const res = await api.get('/api/groups', { params: { filter } });
      setGroups(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadPosts = useCallback(async () => {
    try {
      const res = await api.get('/api/posts');
      setPosts(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadJoiningStatus = useCallback(async () => {
    try {
      const res = await api.get('/api/groups/joining-status');
      setJoiningStatus(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadStats();
    loadGroupStats();
    loadAccounts();
    loadGroups();
    loadPosts();
    loadJoiningStatus();

    // Polling for joining status
    const interval = setInterval(() => {
      loadJoiningStatus();
      loadGroupStats();
    }, 3000);

    return () => clearInterval(interval);
  }, [loadStats, loadGroupStats, loadAccounts, loadGroups, loadPosts, loadJoiningStatus]);

  // Phone auth handlers
  const handleSendCode = async () => {
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await api.post('/api/telegram/send-code', { phone });
      if (res.data.status === 'code_sent') {
        setAuthStep('code');
      } else if (res.data.status === 'already_authorized') {
        setAuthUser(res.data.user);
        setAuthStep('done');
        loadAccounts();
      }
    } catch (e: any) {
      setAuthError(e.response?.data?.detail || 'Ошибка отправки кода');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    setAuthError('');
    setAuthLoading(true);
    try {
      const res = await api.post('/api/telegram/verify-code', {
        phone,
        code,
        password: password2fa || undefined
      });
      if (res.data.status === 'success') {
        setAuthUser(res.data.user);
        setAuthStep('done');
        loadAccounts();
      } else if (res.data.status === '2fa_required') {
        setAuthStep('2fa');
      } else if (res.data.status === 'error') {
        setAuthError(res.data.message);
      }
    } catch (e: any) {
      setAuthError(e.response?.data?.detail || 'Ошибка проверки кода');
    } finally {
      setAuthLoading(false);
    }
  };

  const resetAuth = () => {
    setPhone('');
    setCode('');
    setPassword2fa('');
    setAuthStep('phone');
    setAuthUser(null);
    setAuthError('');
  };

  // Import Excel
  const handleImportExcel = async () => {
    if (!importFile) return;

    setImportLoading(true);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append('file', importFile);

      const res = await api.post(`/api/groups/import?update_existing=${updateExisting}`, formData);
      setImportResult(res.data);
      loadGroups();
      loadGroupStats();
    } catch (e: any) {
      setImportResult({ status: 'error', message: e.response?.data?.detail || 'Ошибка импорта' });
    } finally {
      setImportLoading(false);
    }
  };

  // Start/Stop joining
  const handleStartJoining = async () => {
    const acc = accounts.find(a => a.is_authorized);
    if (!acc) {
      alert('Нет авторизованного аккаунта');
      return;
    }

    try {
      await api.post('/api/groups/start-joining', { phone: acc.phone });
      loadJoiningStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStopJoining = async () => {
    try {
      await api.post('/api/groups/stop-joining');
      loadJoiningStatus();
    } catch (e) {
      console.error(e);
    }
  };

  // Send post handler
  const handleSendPost = async () => {
    if (!selectedAccount || selectedGroups.length === 0 || !photoFile) {
      alert('Выберите аккаунт, группы и фото');
      return;
    }

    setSendLoading(true);
    setSendResult(null);

    try {
      const formData = new FormData();
      formData.append('phone', selectedAccount);
      formData.append('group_ids', selectedGroups.join(','));
      formData.append('caption', caption);
      formData.append('delay_seconds', String(delaySeconds));
      formData.append('photo', photoFile);

      const res = await api.post('/api/posts/send', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSendResult(res.data);
      loadPosts();
      loadStats();
    } catch (e: any) {
      setSendResult({ status: 'error', message: e.response?.data?.detail || 'Ошибка отправки' });
    } finally {
      setSendLoading(false);
    }
  };

  // Load post detail
  const handleViewPost = async (postId: number) => {
    try {
      const res = await api.get(`/api/posts/${postId}`);
      setSelectedPost(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    onLogout();
  };

  // Filter groups for display
  const filteredGroups = groups.filter(g => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return g.title?.toLowerCase().includes(q) ||
             g.link.toLowerCase().includes(q) ||
             g.city?.toLowerCase().includes(q) ||
             g.address?.toLowerCase().includes(q);
    }
    return true;
  });

  // Select all/none
  const handleSelectAll = () => {
    setSelectedGroups(filteredGroups.filter(g => g.status === 'joined').map(g => g.id));
  };

  const handleSelectNone = () => {
    setSelectedGroups([]);
  };

  return (
    <div className="dashboard">
      <header className="header">
        <h1>Poster Bot</h1>
        <div className="header-actions">
          <button className="btn btn-secondary" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </header>

      <nav className="nav-tabs">
        <button className={`nav-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
          Обзор
        </button>
        <button className={`nav-tab ${activeTab === 'telegram' ? 'active' : ''}`} onClick={() => setActiveTab('telegram')}>
          Telegram
        </button>
        <button className={`nav-tab ${activeTab === 'groups' ? 'active' : ''}`} onClick={() => { setActiveTab('groups'); loadGroups(); }}>
          Группы
        </button>
        <button className={`nav-tab ${activeTab === 'send' ? 'active' : ''}`} onClick={() => { setActiveTab('send'); loadGroups('joined'); }}>
          Рассылка
        </button>
        <button className={`nav-tab ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
          История
        </button>
      </nav>

      <div className="content">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="value">{stats?.accounts || 0}</div>
                <div className="label">Аккаунтов</div>
              </div>
              <div className="stat-card">
                <div className="value">{stats?.groups_joined || 0} / {stats?.groups || 0}</div>
                <div className="label">Групп (вступили)</div>
              </div>
              <div className="stat-card">
                <div className="value">{stats?.posts || 0}</div>
                <div className="label">Рассылок</div>
              </div>
              <div className="stat-card">
                <div className="value">{stats?.successful_sends || 0}</div>
                <div className="label">Успешных отправок</div>
              </div>
            </div>

            {/* Joining Status */}
            {groupStats && (groupStats.pending > 0 || joiningStatus?.is_running) && (
              <div className="card">
                <h2>Статус вступления в группы</h2>
                <div className="stats-grid" style={{ marginBottom: '15px' }}>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: '#ffc107' }}>{groupStats?.pending || 0}</div>
                    <div className="label">Ожидают</div>
                  </div>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: '#17a2b8' }}>{groupStats?.joining || 0}</div>
                    <div className="label">В процессе</div>
                  </div>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: '#28a745' }}>{groupStats?.joined || 0}</div>
                    <div className="label">Вступили</div>
                  </div>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: '#dc3545' }}>{groupStats?.failed || 0}</div>
                    <div className="label">Ошибки</div>
                  </div>
                </div>

                {joiningStatus?.is_running && joiningStatus.stats.current_group && (
                  <p style={{ marginBottom: '10px' }}>
                    Текущая группа: <strong>{joiningStatus.stats.current_group}</strong>
                    <br />
                    Следующая попытка через: {joiningStatus.stats.next_attempt_in} сек
                  </p>
                )}

                <div style={{ display: 'flex', gap: '10px' }}>
                  {!joiningStatus?.is_running ? (
                    <button className="btn btn-success" onClick={handleStartJoining}>
                      Запустить вступление
                    </button>
                  ) : (
                    <button className="btn btn-danger" onClick={handleStopJoining}>
                      Остановить
                    </button>
                  )}
                </div>
              </div>
            )}

            <div className="card">
              <h2>Последние рассылки</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Подпись</th>
                    <th>Статус</th>
                    <th>Результат</th>
                    <th>Дата</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {posts.slice(0, 5).map((post) => (
                    <tr key={post.id}>
                      <td>{post.id}</td>
                      <td>{post.caption || '-'}</td>
                      <td>
                        <span className={`status status-${post.status}`}>{post.status}</span>
                      </td>
                      <td>{post.success_count}/{post.total_groups}</td>
                      <td>{new Date(post.created_at).toLocaleString('ru')}</td>
                      <td>
                        <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }} onClick={() => handleViewPost(post.id)}>
                          Детали
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Telegram Auth Tab */}
        {activeTab === 'telegram' && (
          <div className="card phone-auth">
            <h2>Авторизация Telegram</h2>

            {authStep === 'phone' && (
              <div className="step">
                <div className="form-group">
                  <label><span className="step-number">1</span>Номер телефона</label>
                  <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+7XXXXXXXXXX" />
                </div>
                <button className="btn" onClick={handleSendCode} disabled={authLoading || !phone}>
                  {authLoading ? 'Отправка...' : 'Получить код'}
                </button>
              </div>
            )}

            {authStep === 'code' && (
              <div className="step">
                <div className="form-group">
                  <label><span className="step-number">2</span>Код из Telegram</label>
                  <input type="text" value={code} onChange={(e) => setCode(e.target.value)} placeholder="12345" />
                </div>
                <button className="btn" onClick={handleVerifyCode} disabled={authLoading || !code}>
                  {authLoading ? 'Проверка...' : 'Подтвердить'}
                </button>
                <button className="btn btn-secondary mt-10" onClick={resetAuth}>Назад</button>
              </div>
            )}

            {authStep === '2fa' && (
              <div className="step">
                <div className="form-group">
                  <label><span className="step-number">3</span>Пароль 2FA</label>
                  <input type="password" value={password2fa} onChange={(e) => setPassword2fa(e.target.value)} placeholder="Ваш 2FA пароль" />
                </div>
                <button className="btn" onClick={handleVerifyCode} disabled={authLoading || !password2fa}>
                  {authLoading ? 'Проверка...' : 'Подтвердить'}
                </button>
              </div>
            )}

            {authStep === 'done' && authUser && (
              <div className="step">
                <div className="user-info">
                  <p><strong>Авторизация успешна!</strong></p>
                  <p>Имя: {authUser.first_name} {authUser.last_name}</p>
                  <p>Username: @{authUser.username}</p>
                </div>
                <button className="btn btn-secondary mt-10" onClick={resetAuth}>Добавить другой аккаунт</button>
              </div>
            )}

            {authError && <div className="error">{authError}</div>}

            {accounts.length > 0 && (
              <div className="mt-20">
                <h3>Авторизованные аккаунты</h3>
                <div className="groups-list">
                  {accounts.map((acc) => (
                    <div key={acc.id} className="group-item">
                      <div>
                        <div className="title">{acc.first_name} {acc.last_name} {acc.username && `(@${acc.username})`}</div>
                        <div className="id">{acc.phone}</div>
                      </div>
                      <span className={`status status-${acc.is_authorized ? 'success' : 'failed'}`}>
                        {acc.is_authorized ? 'Активен' : 'Неактивен'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Groups Tab */}
        {activeTab === 'groups' && (
          <>
            {/* Import Excel */}
            <div className="card">
              <h2>Импорт групп из Excel</h2>
              <p style={{ marginBottom: '15px', color: '#666' }}>
                Загрузите Excel файл с колонками: Город, Адрес, Ссылка на группу (t.me/+xxx или t.me/channel)
              </p>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px' }}>
                <input type="file" accept=".xlsx,.xls" onChange={(e) => setImportFile(e.target.files?.[0] || null)} />
                <button className="btn" onClick={handleImportExcel} disabled={importLoading || !importFile}>
                  {importLoading ? 'Загрузка...' : 'Импортировать'}
                </button>
              </div>
              <div style={{ marginBottom: '10px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={updateExisting}
                    onChange={(e) => setUpdateExisting(e.target.checked)}
                  />
                  Обновить город/адрес для существующих групп
                </label>
              </div>
              {importResult && (
                <div className={`user-info mt-10 ${importResult.status === 'error' ? 'error' : ''}`}>
                  {importResult.status === 'success' ? (
                    <p>Добавлено: {importResult.added}, Обновлено: {importResult.updated || 0}, Пропущено: {importResult.skipped}</p>
                  ) : (
                    <p>Ошибка: {importResult.message}</p>
                  )}
                </div>
              )}
            </div>

            {/* Joining Control */}
            <div className="card">
              <h2>Вступление в группы</h2>
              <div className="stats-grid" style={{ marginBottom: '15px' }}>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: '#ffc107' }}>{groupStats?.pending || 0}</div>
                  <div className="label">Ожидают</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: '#28a745' }}>{groupStats?.joined || 0}</div>
                  <div className="label">Вступили</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: '#dc3545' }}>{groupStats?.failed || 0}</div>
                  <div className="label">Ошибки</div>
                </div>
              </div>

              {joiningStatus?.is_running && (
                <div style={{ marginBottom: '15px', padding: '10px', background: '#e8f4fd', borderRadius: '8px' }}>
                  <p>Процесс вступления запущен</p>
                  {joiningStatus.stats.current_group && (
                    <p>Текущая: <strong>{joiningStatus.stats.current_group}</strong></p>
                  )}
                  <p>Следующая через: {joiningStatus.stats.next_attempt_in} сек</p>
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px' }}>
                {!joiningStatus?.is_running ? (
                  <button className="btn btn-success" onClick={handleStartJoining} disabled={!groupStats?.pending}>
                    Запустить вступление ({groupStats?.pending || 0})
                  </button>
                ) : (
                  <button className="btn btn-danger" onClick={handleStopJoining}>
                    Остановить
                  </button>
                )}
              </div>
            </div>

            {/* Groups List */}
            <div className="card">
              <h2>Список групп ({groups.length})</h2>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <button className={`nav-tab ${groupFilter === 'all' ? 'active' : ''}`} onClick={() => { setGroupFilter('all'); loadGroups(); }}>
                  Все
                </button>
                <button className={`nav-tab ${groupFilter === 'joined' ? 'active' : ''}`} onClick={() => { setGroupFilter('joined'); loadGroups('joined'); }}>
                  Вступили
                </button>
                <button className={`nav-tab ${groupFilter === 'pending' ? 'active' : ''}`} onClick={() => { setGroupFilter('pending'); loadGroups('pending'); }}>
                  Ожидают
                </button>
                <button className={`nav-tab ${groupFilter === 'failed' ? 'active' : ''}`} onClick={() => { setGroupFilter('failed'); loadGroups('failed'); }}>
                  Ошибки
                </button>
              </div>

              <div className="groups-list" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {groups.map((group) => (
                  <div key={group.id} className="group-item">
                    <div style={{ flex: 1 }}>
                      <div className="title">
                        <a href={group.link} target="_blank" rel="noopener noreferrer" style={{ color: '#007bff', textDecoration: 'none' }}>
                          {group.title || group.address || group.link}
                        </a>
                        {group.city && <span style={{ color: '#666', marginLeft: '8px' }}>({group.city})</span>}
                      </div>
                      <div className="id">
                        {group.address && `${group.address} | `}
                        {group.telegram_id && `ID: ${group.telegram_id} | `}
                        {group.source === 'excel' ? 'Excel' : 'Вручную'}
                        {group.join_error && <span style={{ color: '#dc3545' }}> | {group.join_error}</span>}
                      </div>
                    </div>
                    <span className={`status status-${group.status}`}>{group.status}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* Send Tab */}
        {activeTab === 'send' && (
          <div className="card send-form">
            <h2>Новая рассылка</h2>

            <div className="form-group">
              <label>Аккаунт отправителя</label>
              <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)} style={{ width: '100%', padding: '10px', fontSize: '14px' }}>
                <option value="">-- Выберите аккаунт --</option>
                {accounts.filter(a => a.is_authorized).map((acc) => (
                  <option key={acc.id} value={acc.phone}>{acc.first_name} ({acc.phone})</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label>Группы для рассылки</label>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '10px', alignItems: 'center' }}>
                <input type="text" placeholder="Поиск..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} style={{ flex: 1 }} />
                <button className="btn btn-secondary" style={{ padding: '8px 12px' }} onClick={handleSelectAll}>Выбрать все</button>
                <button className="btn btn-secondary" style={{ padding: '8px 12px' }} onClick={handleSelectNone}>Снять все</button>
              </div>
              <div className="checkbox-group">
                {filteredGroups.filter(g => g.status === 'joined').map((group) => (
                  <div key={group.id} className="checkbox-item">
                    <input
                      type="checkbox"
                      id={`group-${group.id}`}
                      checked={selectedGroups.includes(group.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedGroups([...selectedGroups, group.id]);
                        } else {
                          setSelectedGroups(selectedGroups.filter(id => id !== group.id));
                        }
                      }}
                    />
                    <label htmlFor={`group-${group.id}`}>
                      {group.title || group.address || group.link}
                      {group.city && <span style={{ color: '#888', fontSize: '12px' }}> ({group.city})</span>}
                    </label>
                  </div>
                ))}
              </div>
              <p style={{ marginTop: '10px', color: '#666' }}>Выбрано: {selectedGroups.length} групп</p>
            </div>

            <div className="form-group">
              <label>Подпись к фото</label>
              <textarea value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Текст подписи (необязательно)" />
            </div>

            <div className="form-group">
              <label>Фото</label>
              <input type="file" accept="image/*" className="file-input" onChange={(e) => setPhotoFile(e.target.files?.[0] || null)} />
            </div>

            <div className="form-group">
              <label>Задержка между отправками (секунд)</label>
              <select value={delaySeconds} onChange={(e) => setDelaySeconds(Number(e.target.value))} style={{ width: '100%', padding: '10px', fontSize: '14px' }}>
                <option value={0}>Без задержки</option>
                <option value={3}>3 секунды</option>
                <option value={5}>5 секунд</option>
                <option value={10}>10 секунд</option>
                <option value={15}>15 секунд</option>
                <option value={30}>30 секунд</option>
              </select>
            </div>

            <button className="btn btn-success" onClick={handleSendPost} disabled={sendLoading || !selectedAccount || selectedGroups.length === 0 || !photoFile}>
              {sendLoading ? 'Отправка...' : `Отправить в ${selectedGroups.length} групп`}
            </button>

            {sendResult && (
              <div className={`user-info mt-20 ${sendResult.status === 'error' ? '' : ''}`} style={sendResult.status === 'error' ? { background: '#f8d7da' } : {}}>
                {sendResult.status === 'completed' ? (
                  <>
                    <p><strong>Рассылка завершена!</strong></p>
                    <p>Успешно: {sendResult.success_count} | Ошибок: {sendResult.fail_count}</p>
                  </>
                ) : (
                  <p style={{ color: '#dc3545' }}>Ошибка: {sendResult.message}</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <>
            <div className="card">
              <h2>История рассылок</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Подпись</th>
                    <th>Статус</th>
                    <th>Успешно</th>
                    <th>Ошибок</th>
                    <th>Всего</th>
                    <th>Дата</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {posts.map((post) => (
                    <tr key={post.id}>
                      <td>{post.id}</td>
                      <td>{post.caption || '-'}</td>
                      <td><span className={`status status-${post.status}`}>{post.status}</span></td>
                      <td style={{ color: '#28a745' }}>{post.success_count}</td>
                      <td style={{ color: '#dc3545' }}>{post.fail_count}</td>
                      <td>{post.total_groups}</td>
                      <td>{new Date(post.created_at).toLocaleString('ru')}</td>
                      <td>
                        <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px' }} onClick={() => handleViewPost(post.id)}>
                          Детали
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Post Detail Modal */}
            {selectedPost && (
              <div className="card mt-20">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h2>Рассылка #{selectedPost.id}</h2>
                  <button className="btn btn-secondary" style={{ padding: '4px 8px' }} onClick={() => setSelectedPost(null)}>Закрыть</button>
                </div>
                <p style={{ margin: '10px 0' }}>Подпись: {selectedPost.caption || '-'}</p>
                <p style={{ margin: '10px 0' }}>Дата: {new Date(selectedPost.created_at).toLocaleString('ru')}</p>

                <h3 style={{ marginTop: '20px' }}>Результаты отправки</h3>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Группа</th>
                      <th>Статус</th>
                      <th>Ссылка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedPost.results.map((r, idx) => (
                      <tr key={idx}>
                        <td>{r.group_title}</td>
                        <td>
                          <span className={`status status-${r.status}`}>{r.status}</span>
                          {r.error && <span style={{ color: '#dc3545', marginLeft: '10px' }}>{r.error}</span>}
                        </td>
                        <td>
                          {r.message_link ? (
                            <a href={r.message_link} target="_blank" rel="noopener noreferrer">Открыть</a>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
