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

interface Message {
  id: number;
  name: string;
  caption: string | null;
  photo_path: string | null;
  status: string;
  created_at: string;
  stats: {
    total: number;
    sent: number;
    failed: number;
    pending: number;
  };
}

interface MessageGroup {
  id: number;
  title: string;
  link: string;
  city: string | null;
  address: string | null;
  send_status: string | null;
  message_link: string | null;
  error: string | null;
  sent_at: string | null;
}

interface SendingStatus {
  message_status: string;
  is_sending: boolean;
  stats: {
    pending: number;
    sending: number;
    sent: number;
    failed: number;
  };
  recent_sends: Array<{
    group_id: number;
    group_title: string;
    group_link: string;
    status: string;
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

  // Messages state (new)
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [messageGroups, setMessageGroups] = useState<MessageGroup[]>([]);
  const [sendingStatus, setSendingStatus] = useState<SendingStatus | null>(null);
  const [newMessageName, setNewMessageName] = useState('');
  const [newMessageCaption, setNewMessageCaption] = useState('');
  const [newMessagePhoto, setNewMessagePhoto] = useState<File | null>(null);
  const [createMessageLoading, setCreateMessageLoading] = useState(false);
  const [messageSearchQuery, setMessageSearchQuery] = useState('');
  const [messageSelectedGroups, setMessageSelectedGroups] = useState<number[]>([]);
  const [messageSendLoading, setMessageSendLoading] = useState(false);
  const [messageFilter, setMessageFilter] = useState('all'); // all, not_sent, sent, failed

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

  const loadMessages = useCallback(async () => {
    try {
      const res = await api.get('/api/messages');
      setMessages(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadMessageGroups = useCallback(async (messageId: number) => {
    try {
      const res = await api.get(`/api/messages/${messageId}/groups`);
      setMessageGroups(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadSendingStatus = useCallback(async (messageId: number) => {
    try {
      const res = await api.get(`/api/messages/${messageId}/sending-status`);
      setSendingStatus(res.data);
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
    loadMessages();

    // Polling for joining status
    const interval = setInterval(() => {
      loadJoiningStatus();
      loadGroupStats();
    }, 3000);

    return () => clearInterval(interval);
  }, [loadStats, loadGroupStats, loadAccounts, loadGroups, loadPosts, loadJoiningStatus, loadMessages]);

  // Polling for sending status when message is selected and sending
  useEffect(() => {
    if (!selectedMessage || !sendingStatus?.is_sending) return;

    const interval = setInterval(() => {
      loadSendingStatus(selectedMessage.id);
      loadMessageGroups(selectedMessage.id);
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedMessage, sendingStatus?.is_sending, loadSendingStatus, loadMessageGroups]);

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

  // === Message handlers ===

  const handleCreateMessage = async () => {
    if (!newMessagePhoto) {
      alert('Выберите фото');
      return;
    }

    setCreateMessageLoading(true);

    try {
      const formData = new FormData();
      formData.append('name', newMessageName);
      formData.append('caption', newMessageCaption);
      formData.append('photo', newMessagePhoto);

      await api.post('/api/messages', formData);
      loadMessages();
      setNewMessageName('');
      setNewMessageCaption('');
      setNewMessagePhoto(null);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Ошибка создания');
    } finally {
      setCreateMessageLoading(false);
    }
  };

  const handleSelectMessage = async (msg: Message) => {
    setSelectedMessage(msg);
    setMessageSelectedGroups([]);
    await loadMessageGroups(msg.id);
    await loadSendingStatus(msg.id);
  };

  const handleDeleteMessage = async (messageId: number) => {
    if (!confirm('Удалить сообщение?')) return;

    try {
      await api.delete(`/api/messages/${messageId}`);
      loadMessages();
      if (selectedMessage?.id === messageId) {
        setSelectedMessage(null);
        setMessageGroups([]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedMessage || messageSelectedGroups.length === 0) {
      alert('Выберите группы');
      return;
    }

    const acc = accounts.find(a => a.is_authorized);
    if (!acc) {
      alert('Нет авторизованного аккаунта');
      return;
    }

    setMessageSendLoading(true);

    try {
      const formData = new FormData();
      formData.append('phone', acc.phone);
      formData.append('group_ids', messageSelectedGroups.join(','));
      formData.append('delay_seconds', String(delaySeconds));

      await api.post(`/api/messages/${selectedMessage.id}/send`, formData);
      await loadMessageGroups(selectedMessage.id);
      await loadSendingStatus(selectedMessage.id);
      loadMessages();
      setMessageSelectedGroups([]);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Ошибка отправки');
    } finally {
      setMessageSendLoading(false);
    }
  };

  // Filter message groups
  const filteredMessageGroups = messageGroups.filter(g => {
    // Search filter
    if (messageSearchQuery) {
      const q = messageSearchQuery.toLowerCase();
      if (!g.title?.toLowerCase().includes(q) &&
          !g.link.toLowerCase().includes(q) &&
          !g.city?.toLowerCase().includes(q) &&
          !g.address?.toLowerCase().includes(q)) {
        return false;
      }
    }

    // Status filter
    if (messageFilter === 'not_sent' && g.send_status) return false;
    if (messageFilter === 'sent' && g.send_status !== 'sent') return false;
    if (messageFilter === 'failed' && g.send_status !== 'failed') return false;

    return true;
  });

  const handleMessageSelectAll = () => {
    // Select all not sent groups
    setMessageSelectedGroups(
      filteredMessageGroups.filter(g => !g.send_status || g.send_status === 'failed').map(g => g.id)
    );
  };

  const handleMessageSelectNone = () => {
    setMessageSelectedGroups([]);
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
        <button className={`nav-tab ${activeTab === 'messages' ? 'active' : ''}`} onClick={() => { setActiveTab('messages'); loadMessages(); }}>
          Сообщения
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

        {/* Messages Tab */}
        {activeTab === 'messages' && (
          <>
            {/* Create Message */}
            <div className="card">
              <h2>Создать сообщение</h2>
              <div className="form-group">
                <label>Название (для себя)</label>
                <input
                  type="text"
                  value={newMessageName}
                  onChange={(e) => setNewMessageName(e.target.value)}
                  placeholder="Например: Акция февраль"
                />
              </div>
              <div className="form-group">
                <label>Текст сообщения</label>
                <textarea
                  value={newMessageCaption}
                  onChange={(e) => setNewMessageCaption(e.target.value)}
                  placeholder="Текст подписи к фото"
                />
              </div>
              <div className="form-group">
                <label>Фото</label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setNewMessagePhoto(e.target.files?.[0] || null)}
                />
              </div>
              <button
                className="btn btn-success"
                onClick={handleCreateMessage}
                disabled={createMessageLoading || !newMessagePhoto}
              >
                {createMessageLoading ? 'Создание...' : 'Создать сообщение'}
              </button>
            </div>

            {/* Messages List */}
            <div className="card">
              <h2>Мои сообщения</h2>
              {messages.length === 0 ? (
                <p style={{ color: '#666' }}>Нет созданных сообщений</p>
              ) : (
                <div className="groups-list">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`group-item ${selectedMessage?.id === msg.id ? 'selected' : ''}`}
                      style={{
                        cursor: 'pointer',
                        background: selectedMessage?.id === msg.id ? '#e3f2fd' : undefined
                      }}
                      onClick={() => handleSelectMessage(msg)}
                    >
                      <div style={{ flex: 1 }}>
                        <div className="title">{msg.name}</div>
                        <div className="id">
                          {msg.caption ? msg.caption.substring(0, 50) + '...' : 'Без текста'}
                          {' | '}
                          Отправлено: {msg.stats.sent}/{msg.stats.total || 'нет'}
                          {msg.stats.failed > 0 && <span style={{ color: '#dc3545' }}> | Ошибок: {msg.stats.failed}</span>}
                        </div>
                      </div>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '4px 8px', fontSize: '12px', flexShrink: 0, alignSelf: 'center' }}
                        onClick={(e) => { e.stopPropagation(); handleDeleteMessage(msg.id); }}
                      >
                        X
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Selected Message - Send to Groups */}
            {selectedMessage && (
              <div className="card">
                <h2>Отправка: {selectedMessage.name}</h2>

                {/* Sending Status */}
                {sendingStatus && (
                  <div style={{ marginBottom: '15px', padding: '10px', background: '#f8f9fa', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', gap: '20px', marginBottom: '10px' }}>
                      <span>Отправлено: <strong style={{ color: '#28a745' }}>{sendingStatus.stats.sent}</strong></span>
                      <span>Ошибок: <strong style={{ color: '#dc3545' }}>{sendingStatus.stats.failed}</strong></span>
                      <span>Ожидает: <strong style={{ color: '#ffc107' }}>{sendingStatus.stats.pending}</strong></span>
                      {sendingStatus.is_sending && <span style={{ color: '#17a2b8' }}>Идёт отправка...</span>}
                    </div>
                  </div>
                )}

                {/* Filters */}
                <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Поиск..."
                    value={messageSearchQuery}
                    onChange={(e) => setMessageSearchQuery(e.target.value)}
                    style={{ flex: 1, minWidth: '200px' }}
                  />
                  <button className={`nav-tab ${messageFilter === 'all' ? 'active' : ''}`} onClick={() => setMessageFilter('all')}>
                    Все
                  </button>
                  <button className={`nav-tab ${messageFilter === 'not_sent' ? 'active' : ''}`} onClick={() => setMessageFilter('not_sent')}>
                    Не отправлено
                  </button>
                  <button className={`nav-tab ${messageFilter === 'sent' ? 'active' : ''}`} onClick={() => setMessageFilter('sent')}>
                    Отправлено
                  </button>
                  <button className={`nav-tab ${messageFilter === 'failed' ? 'active' : ''}`} onClick={() => setMessageFilter('failed')}>
                    Ошибки
                  </button>
                </div>

                {/* Select buttons */}
                <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px' }} onClick={handleMessageSelectAll}>
                    Выбрать неотправленные
                  </button>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px' }} onClick={handleMessageSelectNone}>
                    Снять все
                  </button>
                  <span style={{ marginLeft: 'auto', color: '#666' }}>Выбрано: {messageSelectedGroups.length}</span>
                </div>

                {/* Groups List */}
                <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #ddd', borderRadius: '8px' }}>
                  <table className="table" style={{ marginBottom: 0 }}>
                    <thead>
                      <tr>
                        <th style={{ width: '30px' }}></th>
                        <th>Группа</th>
                        <th style={{ width: '100px' }}>Статус</th>
                        <th style={{ width: '120px' }}>Ссылки</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMessageGroups.map((g) => (
                        <tr key={g.id} style={{ background: g.send_status === 'sent' ? '#d4edda' : g.send_status === 'failed' ? '#f8d7da' : undefined }}>
                          <td>
                            <input
                              type="checkbox"
                              checked={messageSelectedGroups.includes(g.id)}
                              disabled={g.send_status === 'sent'}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setMessageSelectedGroups([...messageSelectedGroups, g.id]);
                                } else {
                                  setMessageSelectedGroups(messageSelectedGroups.filter(id => id !== g.id));
                                }
                              }}
                            />
                          </td>
                          <td>
                            <div>{g.title}</div>
                            <div style={{ fontSize: '12px', color: '#666' }}>
                              {g.city && `${g.city} | `}{g.address}
                            </div>
                          </td>
                          <td>
                            {g.send_status === 'sent' && <span style={{ color: '#28a745' }}>Отправлено</span>}
                            {g.send_status === 'failed' && <span style={{ color: '#dc3545' }} title={g.error || ''}>Ошибка</span>}
                            {g.send_status === 'sending' && <span style={{ color: '#17a2b8' }}>Отправка...</span>}
                            {!g.send_status && <span style={{ color: '#666' }}>—</span>}
                          </td>
                          <td>
                            <a href={g.link} target="_blank" rel="noopener noreferrer" style={{ marginRight: '8px' }}>Группа</a>
                            {g.message_link && <a href={g.message_link} target="_blank" rel="noopener noreferrer">Пост</a>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Delay and Send button */}
                <div style={{ marginTop: '15px', display: 'flex', gap: '15px', alignItems: 'center' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    Задержка:
                    <select value={delaySeconds} onChange={(e) => setDelaySeconds(Number(e.target.value))} style={{ padding: '6px' }}>
                      <option value={0}>Без задержки</option>
                      <option value={3}>3 сек</option>
                      <option value={5}>5 сек</option>
                      <option value={10}>10 сек</option>
                      <option value={30}>30 сек</option>
                    </select>
                  </label>
                  <button
                    className="btn btn-success"
                    onClick={handleSendMessage}
                    disabled={messageSendLoading || messageSelectedGroups.length === 0}
                  >
                    {messageSendLoading ? 'Отправка...' : `Отправить в ${messageSelectedGroups.length} групп`}
                  </button>
                </div>
              </div>
            )}
          </>
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
