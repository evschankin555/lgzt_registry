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
  approved: number;
  approved_pending: number;
  approved_joined: number;
}
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
    joined_this_session: number;
    limit: number;
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
  approved: boolean;
  can_leave: boolean;
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

interface BotSettings {
  active_message_id: number | null;
  daily_limit: number;
  join_limit_per_session: number;
  send_limit_per_session: number;
  join_start_hour: number;
  join_end_hour: number;
  send_start_hour: number;
  send_end_hour: number;
  join_delay_min: number;
  join_delay_max: number;
  send_delay_min: number;
  send_delay_max: number;
  wait_before_send_hours: number;
  auto_leave_enabled: boolean;
  leave_after_days: number;
  auto_mode_enabled: boolean;
}

interface AutoStatus {
  is_running: boolean;
  status: {
    mode: string;
    current_action: string | null;
    next_action_in: number;
    today_joins: number;
    today_sends: number;
    today_leaves: number;
    daily_limit: number;
    session_joins: number;
    session_sends: number;
  };
}

interface DailyStatsData {
  date: string;
  joins_count: number;
  sends_count: number;
  leaves_count: number;
  total: number;
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

  // Join settings
  const [joinLimit, setJoinLimit] = useState(20);
  const [joinDelayMin, setJoinDelayMin] = useState(30);
  const [joinDelayMax, setJoinDelayMax] = useState(60);

  // Bot settings & auto mode
  const [botSettings, setBotSettings] = useState<BotSettings | null>(null);
  const [autoStatus, setAutoStatus] = useState<AutoStatus | null>(null);
  const [dailyStats, setDailyStats] = useState<DailyStatsData | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);

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

  const loadBotSettings = useCallback(async () => {
    try {
      const res = await api.get('/api/settings');
      setBotSettings(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadAutoStatus = useCallback(async () => {
    try {
      const res = await api.get('/api/auto/status');
      setAutoStatus(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadDailyStats = useCallback(async () => {
    try {
      const res = await api.get('/api/daily-stats');
      setDailyStats(res.data);
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
    loadBotSettings();
    loadAutoStatus();
    loadDailyStats();

    // Polling for joining status and auto status
    const interval = setInterval(() => {
      loadJoiningStatus();
      loadGroupStats();
      loadAutoStatus();
      loadDailyStats();
    }, 3000);

    return () => clearInterval(interval);
  }, [loadStats, loadGroupStats, loadAccounts, loadGroups, loadPosts, loadJoiningStatus, loadMessages, loadBotSettings, loadAutoStatus, loadDailyStats]);

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
      await api.post('/api/groups/start-joining', {
        phone: acc.phone,
        limit: joinLimit,
        delay_min: joinDelayMin,
        delay_max: joinDelayMax
      });
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

  // Auto mode handlers
  const handleStartAutoMode = async () => {
    const acc = accounts.find(a => a.is_authorized);
    if (!acc) {
      alert('Нет авторизованного аккаунта');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('phone', acc.phone);
      await api.post('/api/auto/start', formData);
      loadAutoStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStopAutoMode = async () => {
    try {
      await api.post('/api/auto/stop');
      loadAutoStatus();
    } catch (e) {
      console.error(e);
    }
  };

  // Approve groups handler
  const handleApproveGroups = async (groupIds: number[], approved: boolean) => {
    try {
      const formData = new FormData();
      formData.append('group_ids', groupIds.join(','));
      formData.append('approved', String(approved));
      await api.post('/api/groups/approve', formData);
      loadGroups();
      loadGroupStats();
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveAllGroups = async (filter: string, approved: boolean) => {
    try {
      const formData = new FormData();
      formData.append('filter', filter);
      formData.append('approved', String(approved));
      await api.post('/api/groups/approve-all', formData);
      loadGroups();
      loadGroupStats();
    } catch (e) {
      console.error(e);
    }
  };

  // Save settings handler
  const handleSaveSettings = async () => {
    if (!botSettings) return;
    setSettingsLoading(true);

    try {
      const formData = new FormData();
      if (botSettings.active_message_id) {
        formData.append('active_message_id', String(botSettings.active_message_id));
      }
      formData.append('daily_limit', String(botSettings.daily_limit));
      formData.append('join_limit_per_session', String(botSettings.join_limit_per_session));
      formData.append('send_limit_per_session', String(botSettings.send_limit_per_session));
      formData.append('join_start_hour', String(botSettings.join_start_hour));
      formData.append('join_end_hour', String(botSettings.join_end_hour));
      formData.append('send_start_hour', String(botSettings.send_start_hour));
      formData.append('send_end_hour', String(botSettings.send_end_hour));
      formData.append('join_delay_min', String(botSettings.join_delay_min));
      formData.append('join_delay_max', String(botSettings.join_delay_max));
      formData.append('send_delay_min', String(botSettings.send_delay_min));
      formData.append('send_delay_max', String(botSettings.send_delay_max));
      formData.append('wait_before_send_hours', String(botSettings.wait_before_send_hours));
      formData.append('auto_leave_enabled', String(botSettings.auto_leave_enabled));
      formData.append('leave_after_days', String(botSettings.leave_after_days));

      await api.post('/api/settings', formData);
      alert('Настройки сохранены');
    } catch (e) {
      console.error(e);
      alert('Ошибка сохранения настроек');
    } finally {
      setSettingsLoading(false);
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
        <button className={`nav-tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => { setActiveTab('settings'); loadBotSettings(); }}>
          Настройки
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
                    <div className="value" style={{ fontSize: '24px', color: 'var(--warning)' }}>{groupStats?.pending || 0}</div>
                    <div className="label">Ожидают</div>
                  </div>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: 'var(--info)' }}>{groupStats?.joining || 0}</div>
                    <div className="label">В процессе</div>
                  </div>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: 'var(--success)' }}>{groupStats?.joined || 0}</div>
                    <div className="label">Вступили</div>
                  </div>
                  <div className="stat-card" style={{ padding: '15px' }}>
                    <div className="value" style={{ fontSize: '24px', color: 'var(--error)' }}>{groupStats?.failed || 0}</div>
                    <div className="label">Ошибки</div>
                  </div>
                </div>

                {joiningStatus?.is_running && joiningStatus.stats.current_group && (
                  <p style={{ marginBottom: '10px' }}>
                    Текущая группа: <strong>{joiningStatus.stats.current_group}</strong>
                    <br />
                    Следующая попытка через: {joiningStatus.stats.next_attempt_in} сек
                    {joiningStatus.stats.limit > 0 && (
                      <>
                        <br />
                        Вступили в сессии: <strong>{joiningStatus.stats.joined_this_session}</strong> / {joiningStatus.stats.limit}
                      </>
                    )}
                  </p>
                )}

                {!joiningStatus?.is_running && (
                  <div style={{ marginBottom: '15px', padding: '15px', background: 'var(--panel-card)', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                      <div className="form-group" style={{ margin: 0, flex: '1', minWidth: '120px' }}>
                        <label style={{ fontSize: '12px' }}>Лимит групп</label>
                        <input
                          type="number"
                          value={joinLimit}
                          onChange={(e) => setJoinLimit(parseInt(e.target.value) || 0)}
                          min={0}
                          max={100}
                          style={{ padding: '8px 12px' }}
                        />
                      </div>
                      <div className="form-group" style={{ margin: 0, flex: '1', minWidth: '120px' }}>
                        <label style={{ fontSize: '12px' }}>Мин. задержка (сек)</label>
                        <input
                          type="number"
                          value={joinDelayMin}
                          onChange={(e) => setJoinDelayMin(parseInt(e.target.value) || 30)}
                          min={10}
                          max={300}
                          style={{ padding: '8px 12px' }}
                        />
                      </div>
                      <div className="form-group" style={{ margin: 0, flex: '1', minWidth: '120px' }}>
                        <label style={{ fontSize: '12px' }}>Макс. задержка (сек)</label>
                        <input
                          type="number"
                          value={joinDelayMax}
                          onChange={(e) => setJoinDelayMax(parseInt(e.target.value) || 60)}
                          min={10}
                          max={600}
                          style={{ padding: '8px 12px' }}
                        />
                      </div>
                    </div>
                    <p style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {joinLimit > 0
                        ? `Вступим в ${joinLimit} групп с задержкой ${joinDelayMin}-${joinDelayMax} сек`
                        : `Вступим во все группы с задержкой ${joinDelayMin}-${joinDelayMax} сек`
                      }
                      {joinLimit > 0 && ` (~${Math.round(joinLimit * (joinDelayMin + joinDelayMax) / 2 / 60)} мин)`}
                    </p>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '10px' }}>
                  {!joiningStatus?.is_running ? (
                    <button className="btn btn-success" onClick={handleStartJoining}>
                      Вступить в {joinLimit > 0 ? joinLimit : 'все'} групп
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
              <p style={{ marginBottom: '15px', color: 'var(--text-muted)' }}>
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
                  <div className="value" style={{ fontSize: '24px', color: 'var(--warning)' }}>{groupStats?.pending || 0}</div>
                  <div className="label">Ожидают</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--success)' }}>{groupStats?.joined || 0}</div>
                  <div className="label">Вступили</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--error)' }}>{groupStats?.failed || 0}</div>
                  <div className="label">Ошибки</div>
                </div>
              </div>

              {joiningStatus?.is_running && (
                <div style={{ marginBottom: '15px', padding: '10px', background: 'var(--info-bg)', borderRadius: '8px' }}>
                  <p>Процесс вступления запущен</p>
                  {joiningStatus.stats.current_group && (
                    <p>Текущая: <strong>{joiningStatus.stats.current_group}</strong></p>
                  )}
                  <p>Следующая через: {joiningStatus.stats.next_attempt_in} сек</p>
                  {joiningStatus.stats.limit > 0 && (
                    <p>Прогресс: <strong>{joiningStatus.stats.joined_this_session}</strong> / {joiningStatus.stats.limit}</p>
                  )}
                </div>
              )}

              {!joiningStatus?.is_running && (
                <div style={{ marginBottom: '15px', padding: '15px', background: 'var(--panel-card)', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
                    <div className="form-group" style={{ margin: 0, flex: '1', minWidth: '120px' }}>
                      <label style={{ fontSize: '12px' }}>Лимит групп</label>
                      <input
                        type="number"
                        value={joinLimit}
                        onChange={(e) => setJoinLimit(parseInt(e.target.value) || 0)}
                        min={0}
                        max={100}
                        style={{ padding: '8px 12px' }}
                      />
                    </div>
                    <div className="form-group" style={{ margin: 0, flex: '1', minWidth: '120px' }}>
                      <label style={{ fontSize: '12px' }}>Мин. задержка (сек)</label>
                      <input
                        type="number"
                        value={joinDelayMin}
                        onChange={(e) => setJoinDelayMin(parseInt(e.target.value) || 30)}
                        min={10}
                        max={300}
                        style={{ padding: '8px 12px' }}
                      />
                    </div>
                    <div className="form-group" style={{ margin: 0, flex: '1', minWidth: '120px' }}>
                      <label style={{ fontSize: '12px' }}>Макс. задержка (сек)</label>
                      <input
                        type="number"
                        value={joinDelayMax}
                        onChange={(e) => setJoinDelayMax(parseInt(e.target.value) || 60)}
                        min={10}
                        max={600}
                        style={{ padding: '8px 12px' }}
                      />
                    </div>
                  </div>
                  <p style={{ marginTop: '10px', fontSize: '12px', color: 'var(--text-muted)' }}>
                    {joinLimit > 0
                      ? `Вступим в ${joinLimit} групп с задержкой ${joinDelayMin}-${joinDelayMax} сек`
                      : `Вступим во все группы с задержкой ${joinDelayMin}-${joinDelayMax} сек`
                    }
                    {joinLimit > 0 && ` (~${Math.round(joinLimit * (joinDelayMin + joinDelayMax) / 2 / 60)} мин)`}
                  </p>
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px' }}>
                {!joiningStatus?.is_running ? (
                  <button className="btn btn-success" onClick={handleStartJoining} disabled={!groupStats?.pending}>
                    Вступить в {joinLimit > 0 ? `${joinLimit} из ${groupStats?.pending || 0}` : `все ${groupStats?.pending || 0}`} групп
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
              <h2>Список групп ({groups.length}) {groupStats?.approved ? `| Одобрено: ${groupStats.approved}` : ''}</h2>
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
                <button className={`nav-tab ${groupFilter === 'approved' ? 'active' : ''}`} onClick={() => { setGroupFilter('approved'); loadGroups('approved'); }}>
                  Одобренные
                </button>
              </div>

              {/* Bulk approve buttons */}
              <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
                <button className="btn btn-success" style={{ padding: '6px 12px' }} onClick={() => handleApproveAllGroups('pending', true)}>
                  Одобрить все pending
                </button>
                <button className="btn" style={{ padding: '6px 12px' }} onClick={() => handleApproveAllGroups('joined', true)}>
                  Одобрить все joined
                </button>
                <button className="btn btn-secondary" style={{ padding: '6px 12px' }} onClick={() => handleApproveAllGroups('all', false)}>
                  Снять все одобрения
                </button>
              </div>

              <div className="groups-list" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {groups.map((group) => (
                  <div key={group.id} className="group-item" style={{ background: group.approved ? 'rgba(34, 197, 94, 0.1)' : undefined }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <input
                        type="checkbox"
                        checked={group.approved}
                        onChange={(e) => handleApproveGroups([group.id], e.target.checked)}
                        title="Одобрить для автопостинга"
                      />
                      <div style={{ flex: 1 }}>
                        <div className="title">
                          <a href={group.link} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary-light)', textDecoration: 'none' }}>
                            {group.title || group.address || group.link}
                          </a>
                          {group.city && <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>({group.city})</span>}
                        </div>
                        <div className="id">
                          {group.address && `${group.address} | `}
                          {group.telegram_id && `ID: ${group.telegram_id} | `}
                          {group.source === 'excel' ? 'Excel' : 'Вручную'}
                          {group.can_leave && <span style={{ color: 'var(--warning)' }}> | Можно выйти</span>}
                          {group.join_error && <span style={{ color: 'var(--error)' }}> | {group.join_error}</span>}
                        </div>
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
                <p style={{ color: 'var(--text-muted)' }}>Нет созданных сообщений</p>
              ) : (
                <div className="groups-list">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`group-item ${selectedMessage?.id === msg.id ? 'selected' : ''}`}
                      style={{
                        cursor: 'pointer',
                        background: selectedMessage?.id === msg.id ? 'rgba(99, 102, 241, 0.15)' : undefined
                      }}
                      onClick={() => handleSelectMessage(msg)}
                    >
                      <div style={{ flex: 1 }}>
                        <div className="title">{msg.name}</div>
                        <div className="id">
                          {msg.caption ? msg.caption.substring(0, 50) + '...' : 'Без текста'}
                          {' | '}
                          Отправлено: {msg.stats.sent}/{msg.stats.total || 'нет'}
                          {msg.stats.failed > 0 && <span style={{ color: 'var(--error)' }}> | Ошибок: {msg.stats.failed}</span>}
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
                  <div style={{ marginBottom: '15px', padding: '10px', background: 'var(--panel-card)', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', gap: '20px', marginBottom: '10px' }}>
                      <span>Отправлено: <strong style={{ color: 'var(--success)' }}>{sendingStatus.stats.sent}</strong></span>
                      <span>Ошибок: <strong style={{ color: 'var(--error)' }}>{sendingStatus.stats.failed}</strong></span>
                      <span>Ожидает: <strong style={{ color: 'var(--warning)' }}>{sendingStatus.stats.pending}</strong></span>
                      {sendingStatus.is_sending && <span style={{ color: 'var(--info)' }}>Идёт отправка...</span>}
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
                  <span style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>Выбрано: {messageSelectedGroups.length}</span>
                </div>

                {/* Groups List */}
                <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid var(--panel-border)', borderRadius: '8px' }}>
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
                        <tr key={g.id} style={{ background: g.send_status === 'sent' ? 'var(--success-bg)' : g.send_status === 'failed' ? 'var(--error-bg)' : undefined }}>
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
                            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                              {g.city && `${g.city} | `}{g.address}
                            </div>
                          </td>
                          <td>
                            {g.send_status === 'sent' && <span style={{ color: 'var(--success)' }}>Отправлено</span>}
                            {g.send_status === 'failed' && <span style={{ color: 'var(--error)' }} title={g.error || ''}>Ошибка</span>}
                            {g.send_status === 'sending' && <span style={{ color: 'var(--info)' }}>Отправка...</span>}
                            {!g.send_status && <span style={{ color: 'var(--text-muted)' }}>—</span>}
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

        {/* Settings Tab */}
        {activeTab === 'settings' && botSettings && (
          <>
            {/* Auto Mode Status */}
            <div className="card">
              <h2>Автоматический режим</h2>

              {/* Current Status */}
              <div className="stats-grid" style={{ marginBottom: '15px' }}>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: autoStatus?.is_running ? 'var(--success)' : 'var(--text-muted)' }}>
                    {autoStatus?.is_running ? 'ВКЛ' : 'ВЫКЛ'}
                  </div>
                  <div className="label">Статус</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--info)' }}>
                    {autoStatus?.status.mode === 'joining' ? 'Вступление' :
                     autoStatus?.status.mode === 'sending' ? 'Рассылка' :
                     autoStatus?.status.mode === 'sleeping' ? 'Сон' : 'Ожидание'}
                  </div>
                  <div className="label">Режим</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--warning)' }}>
                    {dailyStats?.total || 0} / {botSettings.daily_limit}
                  </div>
                  <div className="label">Действий сегодня</div>
                </div>
              </div>

              {autoStatus?.is_running && autoStatus.status.current_action && (
                <div style={{ marginBottom: '15px', padding: '10px', background: 'var(--info-bg)', borderRadius: '8px' }}>
                  <p>{autoStatus.status.current_action}</p>
                  {autoStatus.status.next_action_in > 0 && (
                    <p>Следующее действие через: {autoStatus.status.next_action_in} сек</p>
                  )}
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px' }}>
                {!autoStatus?.is_running ? (
                  <button className="btn btn-success" onClick={handleStartAutoMode}>
                    Запустить автоматику
                  </button>
                ) : (
                  <button className="btn btn-danger" onClick={handleStopAutoMode}>
                    Остановить
                  </button>
                )}
              </div>
            </div>

            {/* Settings Form */}
            <div className="card">
              <h2>Настройки</h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
                {/* Active Message */}
                <div className="form-group">
                  <label>Активное сообщение для автопостинга</label>
                  <select
                    value={botSettings.active_message_id || ''}
                    onChange={(e) => setBotSettings({ ...botSettings, active_message_id: e.target.value ? Number(e.target.value) : null })}
                  >
                    <option value="">Не выбрано</option>
                    {messages.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>

                {/* Daily Limit */}
                <div className="form-group">
                  <label>Дневной лимит действий</label>
                  <input
                    type="number"
                    value={botSettings.daily_limit}
                    onChange={(e) => setBotSettings({ ...botSettings, daily_limit: Number(e.target.value) })}
                    min={10}
                    max={500}
                  />
                </div>

                {/* Session Limits */}
                <div className="form-group">
                  <label>Лимит вступлений за сессию</label>
                  <input
                    type="number"
                    value={botSettings.join_limit_per_session}
                    onChange={(e) => setBotSettings({ ...botSettings, join_limit_per_session: Number(e.target.value) })}
                    min={1}
                    max={100}
                  />
                </div>

                <div className="form-group">
                  <label>Лимит отправок за сессию</label>
                  <input
                    type="number"
                    value={botSettings.send_limit_per_session}
                    onChange={(e) => setBotSettings({ ...botSettings, send_limit_per_session: Number(e.target.value) })}
                    min={1}
                    max={100}
                  />
                </div>
              </div>

              <h3 style={{ marginTop: '20px' }}>Расписание (МСК)</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
                <div className="form-group">
                  <label>Вступление: начало</label>
                  <input
                    type="number"
                    value={botSettings.join_start_hour}
                    onChange={(e) => setBotSettings({ ...botSettings, join_start_hour: Number(e.target.value) })}
                    min={0}
                    max={23}
                  />
                </div>
                <div className="form-group">
                  <label>Вступление: конец</label>
                  <input
                    type="number"
                    value={botSettings.join_end_hour}
                    onChange={(e) => setBotSettings({ ...botSettings, join_end_hour: Number(e.target.value) })}
                    min={0}
                    max={23}
                  />
                </div>
                <div className="form-group">
                  <label>Рассылка: начало</label>
                  <input
                    type="number"
                    value={botSettings.send_start_hour}
                    onChange={(e) => setBotSettings({ ...botSettings, send_start_hour: Number(e.target.value) })}
                    min={0}
                    max={23}
                  />
                </div>
                <div className="form-group">
                  <label>Рассылка: конец</label>
                  <input
                    type="number"
                    value={botSettings.send_end_hour}
                    onChange={(e) => setBotSettings({ ...botSettings, send_end_hour: Number(e.target.value) })}
                    min={0}
                    max={23}
                  />
                </div>
              </div>

              <h3 style={{ marginTop: '20px' }}>Задержки (секунды)</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '20px' }}>
                <div className="form-group">
                  <label>Вступление мин.</label>
                  <input
                    type="number"
                    value={botSettings.join_delay_min}
                    onChange={(e) => setBotSettings({ ...botSettings, join_delay_min: Number(e.target.value) })}
                    min={10}
                  />
                </div>
                <div className="form-group">
                  <label>Вступление макс.</label>
                  <input
                    type="number"
                    value={botSettings.join_delay_max}
                    onChange={(e) => setBotSettings({ ...botSettings, join_delay_max: Number(e.target.value) })}
                    min={10}
                  />
                </div>
                <div className="form-group">
                  <label>Рассылка мин.</label>
                  <input
                    type="number"
                    value={botSettings.send_delay_min}
                    onChange={(e) => setBotSettings({ ...botSettings, send_delay_min: Number(e.target.value) })}
                    min={10}
                  />
                </div>
                <div className="form-group">
                  <label>Рассылка макс.</label>
                  <input
                    type="number"
                    value={botSettings.send_delay_max}
                    onChange={(e) => setBotSettings({ ...botSettings, send_delay_max: Number(e.target.value) })}
                    min={10}
                  />
                </div>
              </div>

              <h3 style={{ marginTop: '20px' }}>Дополнительно</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
                <div className="form-group">
                  <label>Ждать перед отправкой (часов)</label>
                  <input
                    type="number"
                    value={botSettings.wait_before_send_hours}
                    onChange={(e) => setBotSettings({ ...botSettings, wait_before_send_hours: Number(e.target.value) })}
                    min={0}
                    max={48}
                  />
                  <small style={{ color: 'var(--text-muted)' }}>После вступления ждём перед отправкой</small>
                </div>
                <div className="form-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={botSettings.auto_leave_enabled}
                      onChange={(e) => setBotSettings({ ...botSettings, auto_leave_enabled: e.target.checked })}
                      style={{ marginRight: '10px' }}
                    />
                    Авто-выход из групп
                  </label>
                </div>
                <div className="form-group">
                  <label>Выходить через (дней)</label>
                  <input
                    type="number"
                    value={botSettings.leave_after_days}
                    onChange={(e) => setBotSettings({ ...botSettings, leave_after_days: Number(e.target.value) })}
                    min={1}
                    max={30}
                  />
                </div>
              </div>

              <div style={{ marginTop: '20px' }}>
                <button className="btn btn-success" onClick={handleSaveSettings} disabled={settingsLoading}>
                  {settingsLoading ? 'Сохранение...' : 'Сохранить настройки'}
                </button>
              </div>
            </div>

            {/* Daily Stats */}
            <div className="card">
              <h2>Статистика за сегодня</h2>
              <div className="stats-grid">
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--info)' }}>{dailyStats?.joins_count || 0}</div>
                  <div className="label">Вступлений</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--success)' }}>{dailyStats?.sends_count || 0}</div>
                  <div className="label">Отправок</div>
                </div>
                <div className="stat-card" style={{ padding: '15px' }}>
                  <div className="value" style={{ fontSize: '24px', color: 'var(--warning)' }}>{dailyStats?.leaves_count || 0}</div>
                  <div className="label">Выходов</div>
                </div>
              </div>
            </div>
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
                      <td style={{ color: 'var(--success)' }}>{post.success_count}</td>
                      <td style={{ color: 'var(--error)' }}>{post.fail_count}</td>
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
                          {r.error && <span style={{ color: 'var(--error)', marginLeft: '10px' }}>{r.error}</span>}
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
