import React, { useState, useEffect, useRef } from 'react';
import { 
  Smartphone, 
  RefreshCw, 
  Upload, 
  Play, 
  Square, 
  Trash2, 
  Home, 
  Terminal, 
  Search, 
  Layers, 
  Sparkles, 
  Info,
  CheckCircle2,
  XCircle,
  AlertCircle
} from 'lucide-react';

// --- CENTRALIZADOR DE REQUISIÇÕES COM BACKEND LOCAL ---
const apiFetch = (url, options) => {
  const isLocal = window.location.hostname === 'localhost' || 
                  window.location.hostname === '127.0.0.1' || 
                  window.location.port === '5000' || 
                  window.location.port === '5173';
  const apiBase = isLocal ? '' : 'http://localhost:5000';
  return fetch(`${apiBase}${url}`, options);
};

export default function App() {
  // Estados da Aplicação
  const [adbStatus, setAdbStatus] = useState({ ready: false, percent: 0, status: 'Verificando...' });
  const [localServerRunning, setLocalServerRunning] = useState(true);
  const [activeTab, setActiveTab] = useState('apps'); // tabs: apps, install, launcher, terminal
  const [devices, setDevices] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState('');
  const [apps, setApps] = useState([]);
  const [selectedApp, setSelectedApp] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showSystemApps, setShowSystemApps] = useState(false);
  const [defaultLauncher, setDefaultLauncher] = useState('Buscando...');
  const [launchers, setLaunchers] = useState([]);
  const [selectedLauncher, setSelectedLauncher] = useState('');
  const [logs, setLogs] = useState([]);
  
  // Estados de Operação / Upload
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loadingAction, setLoadingAction] = useState('');
  
  // Notificação customizada
  const [notification, setNotification] = useState({ message: '', type: '' });
  
  // Referência para auto-scroll do console log
  const consoleContainerRef = useRef(null);

  // Mostrar notificação
  const showToast = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => {
      setNotification({ message: '', type: '' });
    }, 4500);
  };

  // --- EFEITOS DE POLLING (SEGUNDO PLANO) ---
  
  // 1. Monitorar ADB Status
  useEffect(() => {
    const checkAdb = async () => {
      try {
        const res = await apiFetch('/api/adb-status');
        const data = await res.json();
        setAdbStatus(data);
        setLocalServerRunning(true);
        
        // Se o ADB não estiver pronto e não estiver baixando, inicia o download
        if (!data.ready && data.percent === 0 && data.status === 'Aguardando inicialização') {
          apiFetch('/api/adb-download', { method: 'POST' });
        }
      } catch (err) {
        console.error("Erro ao verificar ADB:", err);
        setLocalServerRunning(false);
      }
    };

    checkAdb();
    const interval = setInterval(checkAdb, 2500);
    return () => clearInterval(interval);
  }, []);

  // 2. Monitorar Dispositivos e Logs
  useEffect(() => {
    if (!adbStatus.ready) return;

    const fetchDevices = async () => {
      try {
        const res = await apiFetch('/api/devices');
        const data = await res.json();
        setDevices(data.devices);
        setSelectedDevice(data.selected || '');
      } catch (err) {
        console.error("Erro ao buscar dispositivos:", err);
      }
    };

    const fetchLogs = async () => {
      try {
        const res = await apiFetch('/api/logs');
        const data = await res.json();
        setLogs(data.logs);
      } catch (err) {
        console.error("Erro ao buscar logs:", err);
      }
    };

    fetchDevices();
    fetchLogs();

    const devInterval = setInterval(fetchDevices, 4000);
    const logInterval = setInterval(fetchLogs, 2000);

    return () => {
      clearInterval(devInterval);
      clearInterval(logInterval);
    };
  }, [adbStatus.ready]);

  // 3. Atualizar lista de apps e launcher quando mudar o dispositivo selecionado
  useEffect(() => {
    if (selectedDevice) {
      loadApps();
      loadLauncherInfo();
    } else {
      setApps([]);
      setSelectedApp('');
      setDefaultLauncher('Sem dispositivo conectado');
      setLaunchers([]);
      setSelectedLauncher('');
    }
  }, [selectedDevice, showSystemApps]);

  // Auto-scroll do console de logs (apenas no container interno do console)
  useEffect(() => {
    const container = consoleContainerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [logs]);

  // --- FUNÇÕES DE API ---

  // Alterar dispositivo selecionado
  const handleDeviceChange = async (e) => {
    const dev = e.target.value;
    setSelectedDevice(dev);
    try {
      await apiFetch('/api/select-device', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device: dev })
      });
      showToast(`Dispositivo alterado para ${dev}`, 'success');
    } catch (err) {
      showToast('Erro ao selecionar dispositivo', 'error');
    }
  };

  // Atualizar dispositivos conectados manualmente
  const refreshDevices = async () => {
    setLoadingAction('Buscando dispositivos...');
    try {
      const res = await apiFetch('/api/devices');
      const data = await res.json();
      setDevices(data.devices);
      setSelectedDevice(data.selected || '');
      showToast('Lista de dispositivos atualizada', 'success');
    } catch (err) {
      showToast('Erro ao atualizar dispositivos', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // Carregar lista de aplicativos
  const loadApps = async () => {
    try {
      const res = await apiFetch(`/api/apps?system=${showSystemApps}`);
      const data = await res.json();
      if (res.ok) {
        setApps(data.packages);
        // Deseleciona se o app antigo sumiu
        if (data.packages && !data.packages.includes(selectedApp)) {
          setSelectedApp('');
        }
      } else {
        console.error(data.error);
      }
    } catch (err) {
      console.error("Erro ao carregar apps:", err);
    }
  };

  // Carregar dados de launcher
  const loadLauncherInfo = async () => {
    try {
      // Default launcher
      const resDefault = await apiFetch('/api/launcher/default');
      const dataDefault = await resDefault.json();
      setDefaultLauncher(dataDefault.launcher);

      // Launcher list
      const resList = await apiFetch('/api/launcher/list');
      const dataList = await resList.json();
      setLaunchers(dataList.launchers);
      if (dataList.launchers.length > 0) {
        setSelectedLauncher(dataList.launchers[0]);
      } else {
        setSelectedLauncher('');
      }
    } catch (err) {
      console.error("Erro ao carregar informações de launcher:", err);
    }
  };

  // Instalação do APK enviado
  const installApk = async () => {
    if (!selectedFile) return;
    setLoadingAction('Instalando APK no aparelho...');
    
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await apiFetch('/api/install', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast('APK instalado com sucesso!', 'success');
        setSelectedFile(null);
        loadApps();
      } else {
        showToast(`Erro na instalação: ${data.error}`, 'error');
      }
    } catch (err) {
      showToast('Falha na comunicação com o servidor', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // Desinstalar App selecionado
  const uninstallApp = async () => {
    if (!selectedApp) return;
    if (!confirm(`Deseja realmente desinstalar o aplicativo ${selectedApp}?`)) return;

    setLoadingAction('Desinstalando aplicativo...');
    try {
      const res = await apiFetch('/api/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package: selectedApp })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`Aplicativo ${selectedApp} desinstalado!`, 'success');
        setSelectedApp('');
        loadApps();
      } else {
        showToast(`Erro ao desinstalar: ${data.error}`, 'error');
      }
    } catch (err) {
      showToast('Falha ao desinstalar aplicativo', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // Iniciar App selecionado
  const launchApp = async () => {
    if (!selectedApp) return;
    showToast(`Iniciando ${selectedApp}...`);
    try {
      const res = await apiFetch('/api/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package: selectedApp })
      });
      const data = await res.json();
      if (!res.ok) showToast(`Erro ao iniciar: ${data.error}`, 'error');
    } catch (err) {
      showToast('Erro ao enviar comando de iniciar', 'error');
    }
  };

  // Forçar parada de App selecionado
  const stopApp = async () => {
    if (!selectedApp) return;
    showToast(`Parando ${selectedApp}...`);
    try {
      const res = await apiFetch('/api/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package: selectedApp })
      });
      const data = await res.json();
      if (res.ok) showToast('Comando de parada forçada enviado.', 'success');
      else showToast(`Erro: ${data.error}`, 'error');
    } catch (err) {
      showToast('Erro ao parar app', 'error');
    }
  };

  // Limpar dados de App selecionado
  const clearAppData = async () => {
    if (!selectedApp) return;
    if (!confirm(`Tem certeza que deseja apagar todos os dados de ${selectedApp}?\nIsso resetará o app.`)) return;

    setLoadingAction('Limpando dados do app...');
    try {
      const res = await apiFetch('/api/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package: selectedApp })
      });
      const data = await res.json();
      if (res.ok) showToast('Dados limpos com sucesso.', 'success');
      else showToast(`Erro: ${data.error}`, 'error');
    } catch (err) {
      showToast('Erro ao limpar dados', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // --- AÇÕES DO LAUNCHER CONTROLS ---

  // Definir launcher selecionado como padrão
  const setLauncherDefault = async () => {
    if (!selectedLauncher) return;
    setLoadingAction('Definindo launcher padrão...');
    try {
      const res = await apiFetch('/api/launcher/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ launcher: selectedLauncher })
      });
      const data = await res.json();
      if (res.ok) {
        showToast('Launcher padrão definido com sucesso!', 'success');
        loadLauncherInfo();
      } else {
        alert(`Falha ao definir pelo ADB:\n${data.error}\n\nPor favor, use o botão 'Abrir Seletor' na tela da TV/celular.`);
      }
    } catch (err) {
      showToast('Erro ao configurar launcher', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // Limpar launcher padrão
  const clearLauncherDefault = async () => {
    setLoadingAction('Limpando launcher padrão...');
    try {
      const res = await apiFetch('/api/launcher/clear', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        showToast('Launcher padrão limpo! O sistema pedirá escolha ao apertar HOME.', 'success');
        loadLauncherInfo();
      } else {
        showToast(`Erro ao limpar launcher: ${data.error}`, 'error');
      }
    } catch (err) {
      showToast('Erro ao limpar launcher', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // Abrir seletor no aparelho
  const triggerLauncherPicker = async () => {
    try {
      await apiFetch('/api/launcher/picker', { method: 'POST' });
      showToast('Seletor disparado na tela do dispositivo.', 'success');
    } catch (err) {
      showToast('Erro ao disparar seletor', 'error');
    }
  };

  // --- NOVA FUNÇÃO: TESTAR LAUNCHER SELECIONADO NA LISTA ---
  const testLauncherSelected = async () => {
    if (!selectedApp) return;
    setLoadingAction('Testando app como Launcher...');
    try {
      const res = await apiFetch('/api/launcher/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package: selectedApp })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast('Launcher definido e tela inicial disparada!', 'success');
        loadLauncherInfo();
      } else {
        alert(`Não foi possível testar:\n${data.error || 'Erro desconhecido'}`);
      }
    } catch (err) {
      showToast('Erro ao testar launcher', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // --- NOVA FUNÇÃO: BAIXAR APK DO DISPOSITIVO PARA O COMPUTADOR ---
  const downloadSelectedAppApk = async () => {
    if (!selectedApp) return;
    setLoadingAction('Extraindo APK do dispositivo... (Aguarde)');
    try {
      const url = `/api/apps/download?package=${selectedApp}`;
      const res = await apiFetch(url);
      
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Falha ao baixar APK');
      }
      
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', `${selectedApp}.apk`);
      document.body.appendChild(link);
      link.click();
      
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);
      
      showToast('APK baixado com sucesso para o PC!', 'success');
    } catch (err) {
      alert(`Erro ao extrair e baixar o APK:\n${err.message}`);
      showToast('Falha no download', 'error');
    } finally {
      setLoadingAction('');
    }
  };

  // --- MANIPULADORES DE ARQUIVO (DRAG & DROP) ---
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.apk')) {
        setSelectedFile(file);
        showToast(`APK selecionado: ${file.name}`);
      } else {
        showToast('Por favor, selecione apenas arquivos com extensão .apk', 'error');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      showToast(`APK selecionado: ${e.target.files[0].name}`);
    }
  };

  // Filtragem local dos aplicativos instalados
  const filteredApps = apps.filter(pkg => 
    pkg.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // SE O SERVIDOR DESKTOP NÃO ESTIVER RODANDO, EXIBE A PÁGINA DE BOAS VINDAS / DOWNLOAD
  if (!localServerRunning) {
    return (
      <div className="landing-page">
        {/* HEADER DE BOAS VINDAS */}
        <header className="landing-header">
          <div className="landing-brand">
            <Smartphone size={24} style={{ color: 'var(--accent-purple)' }} />
            <span style={{ fontWeight: 800 }}>ADB Companion</span>
          </div>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
            v1.0.0 Oficial
          </span>
        </header>

        {/* HERO SECTION */}
        <section className="hero-section">
          <h1 className="hero-title">
            Gerencie seu Android e Android TV <span>direto pelo navegador</span>
          </h1>
          <p className="hero-subtitle">
            Instale APKs, gerencie pacotes, altere launchers padrão e envie comandos ADB para a sua TV Box, Fire Stick ou Celular através de um instalador leve e prático.
          </p>

          <div className="hero-buttons">
            <a 
              href="https://github.com/MicaelTech3/Instalador-de-Apk/releases/download/v1.0.0/ADB_Companion_Setup.exe" 
              className="btn-hero-primary"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Smartphone size={20} />
              Baixar Instalador Oficial (.exe)
            </a>
            
            <a 
              href="https://github.com/MicaelTech3/Instalador-de-Apk/releases/download/v1.0.0/ADB_Companion.zip" 
              className="btn-hero-secondary"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Upload size={18} style={{ transform: 'rotate(180deg)' }} />
              Baixar Versão Portátil (.zip)
            </a>
          </div>
        </section>

        {/* CARDS DE FUNCIONALIDADES */}
        <section className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <Upload size={20} />
            </div>
            <h3>Instalador de APKs</h3>
            <p>Arraste e solte arquivos APK diretamente do seu computador para a janela da web e instale-os no seu aparelho sem digitar nenhum comando.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <Layers size={20} />
            </div>
            <h3>Gerenciador de Aplicativos</h3>
            <p>Monitore os apps instalados. Você pode iniciar aplicativos remotamente, forçar parada, limpar cache/dados ou desinstalar com um clique.</p>
          </div>

          <div className="feature-card">
            <div className="feature-icon">
              <Home size={20} />
            </div>
            <h3>Configurador de Launcher</h3>
            <p>Defina launchers alternativos como Projectivy Launcher, Wolf Launcher ou ATV Launcher como padrão no seu sistema Android TV de forma simples.</p>
          </div>
        </section>
      </div>
    );
  }

  // SE O SERVIDOR DESKTOP ESTIVER RODANDO, EXIBE O DASHBOARD COMPLETO COM SIDEBAR
  return (
    <div className="app-layout">
      {/* Toast de Notificação flutuante */}
      {notification.message && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          zIndex: 9999,
          background: 'rgba(20, 20, 28, 0.95)',
          border: `1px solid ${notification.type === 'success' ? 'var(--accent-teal)' : notification.type === 'error' ? 'var(--accent-red)' : 'var(--accent-blue)'}`,
          boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
          padding: '12px 20px',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          animation: 'spin-fade-in 0.3s ease-out',
          color: '#ffffff'
        }}>
          {notification.type === 'success' && <CheckCircle2 size={18} style={{color: 'var(--accent-teal)'}} />}
          {notification.type === 'error' && <XCircle size={18} style={{color: 'var(--accent-red)'}} />}
          {notification.type === 'info' && <Info size={18} style={{color: 'var(--accent-blue)'}} />}
          <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{notification.message}</span>
        </div>
      )}

      {/* OVERLAY DE CARREGAMENTO PARA AÇÕES LENTAS */}
      {loadingAction && (
        <div className="overlay">
          <div className="spinner"></div>
          <p style={{fontWeight: 700, fontSize: '1.1rem'}}>{loadingAction}</p>
        </div>
      )}

      {/* OVERLAY DE DOWNLOAD DO ADB */}
      {!adbStatus.ready && (
        <div className="overlay">
          <Smartphone size={48} style={{color: 'var(--accent-purple)'}} />
          <h2 style={{fontWeight: 800}}>Configurando Android Tools (ADB)</h2>
          <p style={{color: 'var(--text-secondary)', fontSize: '0.95rem', maxWidth: '400px', textAlign: 'center'}}>{adbStatus.status}</p>
          
          {adbStatus.percent >= 0 && (
            <>
              <div className="progress-container">
                <div className="progress-bar" style={{ width: `${adbStatus.percent}%` }}></div>
              </div>
              <span style={{fontSize: '0.85rem', color: 'var(--text-secondary)'}}>{adbStatus.percent}% concluído</span>
            </>
          )}

          {adbStatus.percent === -1 && (
            <button 
              className="btn btn-primary" 
              onClick={() => {
                setAdbStatus({ ready: false, percent: 0, status: 'Reiniciando download...' });
                apiFetch('/api/adb-download', { method: 'POST' });
              }}
            >
              Tentar Configurar Novamente
            </button>
          )}
        </div>
      )}

      {/* SIDEBAR DA APLICAÇÃO */}
      <aside className="sidebar">
        <div className="sidebar-header-group">
          <div className="sidebar-brand">
            <Smartphone size={22} style={{ color: 'var(--accent-purple)' }} />
            <span>ADB Companion</span>
          </div>

          <div className="sidebar-device-status">
            <div className={`status-dot ${selectedDevice ? 'connected' : 'disconnected'}`}></div>
            <span className="status-text-compact">
              {selectedDevice ? selectedDevice : 'Sem dispositivo'}
            </span>
          </div>

          <nav className="sidebar-nav">
            <button 
              className={`nav-item ${activeTab === 'apps' ? 'active' : ''}`}
              onClick={() => setActiveTab('apps')}
            >
              <Layers size={18} />
              <span>Meus Aplicativos</span>
            </button>

            <button 
              className={`nav-item ${activeTab === 'install' ? 'active' : ''}`}
              onClick={() => setActiveTab('install')}
            >
              <Upload size={18} />
              <span>Instalar APK</span>
            </button>

            <button 
              className={`nav-item ${activeTab === 'launcher' ? 'active' : ''}`}
              onClick={() => setActiveTab('launcher')}
            >
              <Home size={18} />
              <span>Gerenciar Launcher</span>
            </button>

            <button 
              className={`nav-item ${activeTab === 'terminal' ? 'active' : ''}`}
              onClick={() => setActiveTab('terminal')}
            >
              <Terminal size={18} />
              <span>Console & Logs</span>
            </button>
          </nav>
        </div>

        <div className="sidebar-footer">
          <label className="sidebar-label">Aparelho Conectado</label>
          <select 
            className="device-select-sidebar"
            value={selectedDevice}
            onChange={handleDeviceChange}
            disabled={devices.length === 0}
          >
            {devices.length === 0 ? (
              <option value="">Nenhum conectado</option>
            ) : (
              devices.map(dev => (
                <option key={dev} value={dev}>{dev}</option>
              ))
            )}
          </select>
          <button className="btn-sidebar-refresh" onClick={refreshDevices}>
            <RefreshCw size={14} />
            <span>Atualizar Lista</span>
          </button>
        </div>
      </aside>

      {/* PAINEL PRINCIPAL DE CONTEÚDO */}
      <main className="main-content">
        
        {/* ABA: MEUS APLICATIVOS */}
        {activeTab === 'apps' && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <h1 className="tab-title">Meus Aplicativos</h1>
            <p className="tab-subtitle">Monitore, inicie, pare ou remova aplicativos instalados no aparelho conectado.</p>
            
            {/* TOOLBAR DE AÇÕES NO TOPO */}
            <div className="card" style={{ padding: '16px', marginBottom: '16px', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                <button 
                  className="btn btn-teal" 
                  onClick={launchApp}
                  disabled={!selectedApp}
                >
                  <Play size={15} />
                  Iniciar Aplicativo
                </button>

                <button 
                  className="btn" 
                  onClick={stopApp}
                  disabled={!selectedApp}
                >
                  <Square size={15} />
                  Forçar Parada
                </button>

                <button 
                  className="btn" 
                  onClick={clearAppData}
                  disabled={!selectedApp}
                >
                  <RefreshCw size={15} />
                  Limpar Dados / Cache
                </button>

                <button 
                  className="btn" 
                  onClick={downloadSelectedAppApk}
                  disabled={!selectedApp}
                >
                  <Upload size={15} style={{ transform: 'rotate(180deg)' }} />
                  Download do APK para o PC
                </button>

                <button 
                  className="btn btn-red" 
                  onClick={uninstallApp}
                  disabled={!selectedApp}
                >
                  <Trash2 size={15} />
                  Desinstalar Aplicativo
                </button>
              </div>

              {selectedApp && (
                <div style={{ 
                  background: 'var(--bg-input)', 
                  border: '1px solid var(--border-color)', 
                  borderRadius: '6px', 
                  padding: '6px 12px',
                  fontFamily: 'var(--font-monospace)', 
                  fontSize: '0.8rem', 
                  fontWeight: 600, 
                  color: 'var(--text-main)' 
                }}>
                  {selectedApp}
                </div>
              )}
            </div>

            {/* LISTA COMPLETA DOS APLICATIVOS */}
            <div className="app-list-container-full" style={{ flex: 1, minHeight: 0 }}>
              <div className="search-container">
                <input 
                  type="text" 
                  placeholder="Buscar aplicativo..." 
                  className="search-input"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <div className="checkbox-group" style={{ marginBottom: '12px' }}>
                <label className="checkbox-label">
                  <input 
                    type="checkbox" 
                    checked={showSystemApps}
                    onChange={(e) => setShowSystemApps(e.target.checked)}
                  />
                  Exibir Apps de Sistema
                </label>
              </div>

              <ul className="app-list" style={{ flex: 1, minHeight: 0 }}>
                {filteredApps.length === 0 ? (
                  <li style={{padding: '16px', color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center'}}>
                    Nenhum aplicativo localizado.
                  </li>
                ) : (
                  filteredApps.map(pkg => (
                    <li 
                      key={pkg} 
                      className={`app-item ${selectedApp === pkg ? 'selected' : ''}`}
                      onClick={() => setSelectedApp(pkg)}
                    >
                      {pkg}
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        )}

        {/* ABA: INSTALAR APK */}
        {activeTab === 'install' && (
          <div>
            <h1 className="tab-title">Instalar APK</h1>
            <p className="tab-subtitle">Arraste e solte ou envie um APK do computador para instalá-lo no aparelho conectado.</p>
            
            <div className="card">
              <h2 className="card-title">
                <Upload size={18} style={{color: 'var(--accent-purple)'}} />
                Enviar APK do PC
              </h2>
              
              <div 
                className={`dropzone ${dragActive ? 'active' : ''}`}
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => document.getElementById('apk-file-input').click()}
              >
                <Upload className="dropzone-icon" size={36} />
                <p style={{fontWeight: 700, fontSize: '0.95rem'}}>Arrastar & Soltar arquivo APK aqui</p>
                <p style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>ou clique para explorar arquivos</p>
                <input 
                  id="apk-file-input"
                  type="file" 
                  accept=".apk" 
                  style={{display: 'none'}} 
                  onChange={handleFileChange}
                />
              </div>

              {selectedFile && (
                <div className="file-info">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Smartphone size={18} style={{ color: 'var(--accent-purple)' }} />
                    <span style={{ fontWeight: 600 }}>{selectedFile.name}</span>
                  </div>
                  <button className="btn" onClick={() => setSelectedFile(null)} style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
                    Remover
                  </button>
                </div>
              )}

              <button 
                className="btn btn-primary btn-wide" 
                onClick={installApk}
                disabled={!selectedFile || !selectedDevice}
                style={{ marginTop: '8px' }}
              >
                <Upload size={16} />
                Iniciar Instalação Remota
              </button>
            </div>
          </div>
        )}

        {/* ABA: CONFIGURAÇÕES DE LAUNCHER */}
        {activeTab === 'launcher' && (
          <div>
            <h1 className="tab-title">Gerenciar Launcher</h1>
            <p className="tab-subtitle">Defina e altere o launcher (tela inicial) padrão do seu aparelho Android.</p>
            
            <div className="card">
              <h2 className="card-title">
                <Home size={18} style={{color: 'var(--accent-purple)'}} />
                Launcher Padrão Ativo
              </h2>
              <div className="launcher-status-value">
                {defaultLauncher}
              </div>
            </div>

            <div className="card">
              <h2 className="card-title">
                <Home size={18} style={{color: 'var(--accent-purple)'}} />
                Configurar Novo Launcher
              </h2>
              
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px', lineHeight: '1.5' }}>
                Selecione o launcher instalado abaixo para defini-lo como padrão, ou dispare o seletor nativo do Android.
              </p>

              <div className="launcher-picker-group">
                <select 
                  className="launcher-picker-select"
                  value={selectedLauncher}
                  onChange={(e) => setSelectedLauncher(e.target.value)}
                  disabled={launchers.length === 0}
                >
                  {launchers.length === 0 ? (
                    <option value="">Nenhum Launcher detectado</option>
                  ) : (
                    launchers.map(l => (
                      <option key={l} value={l}>{l}</option>
                    ))
                  )}
                </select>

                <button 
                  className="btn btn-primary" 
                  onClick={setLauncherDefault}
                  disabled={!selectedLauncher}
                >
                  Definir Selecionado
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '16px' }}>
                <button className="btn" onClick={clearLauncherDefault}>
                  Limpar Launcher Padrão
                </button>
                
                <button className="btn" onClick={triggerLauncherPicker}>
                  Abrir Seletor Nativamente
                </button>
              </div>
              
              <button 
                className="btn btn-teal btn-wide" 
                onClick={testLauncherSelected}
                disabled={!selectedApp}
                style={{ marginTop: '12px' }}
              >
                <Sparkles size={16} />
                Testar Launcher Selecionado na Lista
              </button>
            </div>
          </div>
        )}

        {/* ABA: TERMINAL E LOGS */}
        {activeTab === 'terminal' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <h1 className="tab-title">Logs do Sistema</h1>
            <p className="tab-subtitle">Acompanhe as operações do ADB executadas no dispositivo em tempo real.</p>
            
            <div className="card" style={{ flex: 1, marginBottom: 0 }}>
              <h2 className="card-title" style={{ borderBottom: 'none', paddingBottom: 0 }}>
                <Terminal size={18} style={{color: 'var(--accent-purple)'}} />
                Console ADB
              </h2>

              <div className="console-output" ref={consoleContainerRef}>
                {logs.length === 0 ? (
                  <div style={{color: 'var(--text-muted)'}}>Nenhum evento registrado.</div>
                ) : (
                  logs.map((logLine, idx) => (
                    <div key={idx}>{logLine}</div>
                  ))
                )}
              </div>

              <div className="console-actions">
                <button className="btn btn-red" onClick={() => apiFetch('/api/logs', { method: 'POST' })} style={{ padding: '8px 16px', fontSize: '0.8rem' }}>
                  Limpar logs do console
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
