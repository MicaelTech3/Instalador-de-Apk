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
  Eye,
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
  
  // Referências para auto-scroll do console
  const consoleEndRef = useRef(null);

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

  // Auto-scroll do console de logs
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
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

  return (
    <div className="app-container">
      
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
          animation: 'spin-fade-in 0.3s ease-out'
        }}>
          {notification.type === 'success' && <CheckCircle2 size={18} className="text-teal" style={{color: 'var(--accent-teal)'}} />}
          {notification.type === 'error' && <XCircle size={18} className="text-red" style={{color: 'var(--accent-red)'}} />}
          {notification.type === 'info' && <Info size={18} className="text-blue" style={{color: 'var(--accent-blue)'}} />}
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
          <p style={{color: 'var(--text-muted)', fontSize: '0.95rem', maxWidth: '400px', textAlign: 'center'}}>{adbStatus.status}</p>
          
          {adbStatus.percent >= 0 && (
            <>
              <div className="progress-container">
                <div className="progress-bar" style={{ width: `${adbStatus.percent}%` }}></div>
              </div>
              <span style={{fontSize: '0.85rem', color: 'var(--text-muted)'}}>{adbStatus.percent}% concluído</span>
            </>
          )}

          {adbStatus.percent === -1 && (
            <button 
              className="btn btn-purple" 
              onClick={() => {
                setAdbStatus({ ready: false, percent: 0, status: 'Reiniciando download...' });
                apiFetch('/api/adb-download', { method: 'POST' });
              }}
              style={{ 
                marginTop: '20px', 
                padding: '10px 24px', 
                background: 'linear-gradient(135deg, var(--accent-purple) 0%, #a855f7 100%)',
                color: '#fff',
                fontWeight: 700,
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                boxShadow: '0 4px 10px rgba(124, 77, 255, 0.3)'
              }}
            >
              Tentar Configurar Novamente
            </button>
          )}
        </div>
      )}

      {/* --- BARRA SUPERIOR DE STATUS --- */}
      <header className="status-bar">
        <div className="status-info">
          <div className={`status-dot ${selectedDevice ? 'connected' : 'disconnected'}`}></div>
          <div className="status-text">
            {selectedDevice ? `Status: OK - Aparelho Conectado` : 'Nenhum dispositivo detectado'}
          </div>
        </div>
        
        <div className="device-picker-container">
          <label className="form-label" style={{margin: 0}}>Aparelho ativo:</label>
          <select 
            className="device-select"
            value={selectedDevice}
            onChange={handleDeviceChange}
            disabled={devices.length === 0}
          >
            {devices.length === 0 ? (
              <option value="">Sem dispositivos conectados</option>
            ) : (
              devices.map(dev => (
                <option key={dev} value={dev}>{dev}</option>
              ))
            )}
          </select>
          <button className="btn" onClick={refreshDevices} title="Atualizar aparelhos">
            <RefreshCw size={16} />
            <span>Atualizar</span>
          </button>
        </div>
      </header>

      {/* --- DASHBOARD PRINCIPAL GRID --- */}
      <main className="dashboard-grid">
        
        {/* COLUNA ESQUERDA: INSTALAÇÃO & LAUNCHERS */}
        <div style={{display: 'flex', flexDirection: 'column', gap: '20px'}}>
          
          {/* CARD 1: INSTALAÇÃO DE APK */}
          <section className="card">
            <h2 className="card-title">
              <Upload size={18} style={{color: 'var(--accent-purple)'}} />
              Instalar APK no Aparelho
            </h2>
            
            <div 
              className={`dropzone ${dragActive ? 'active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={() => document.getElementById('apk-file-input').click()}
            >
              <Upload className="dropzone-icon" size={32} />
              <p style={{fontWeight: 600, fontSize: '0.9rem'}}>Arrastar & Soltar APK aqui</p>
              <p style={{fontSize: '0.8rem', color: 'var(--text-muted)'}}>ou clique para selecionar arquivo</p>
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
                <div style={{display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden'}}>
                  <span style={{fontWeight: 600, whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden'}}>{selectedFile.name}</span>
                  <span style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>{(selectedFile.size / (1024*1024)).toFixed(2)} MB</span>
                </div>
                <button className="btn btn-red" onClick={() => setSelectedFile(null)} style={{padding: '5px 10px', fontSize: '0.8rem'}}>Remover</button>
              </div>
            )}

            <button 
              className="btn btn-primary" 
              onClick={installApk}
              disabled={!selectedFile || !selectedDevice}
              style={{padding: '12px'}}
            >
              <Sparkles size={16} />
              Instalar APK no Aparelho [OK]
            </button>
          </section>

          {/* CARD 2: CONTROLES DE LAUNCHER */}
          <section className="card">
            <h2 className="card-title">
              <Home size={18} style={{color: 'var(--accent-blue)'}} />
              Configurar Launcher Padrão
            </h2>

            <div className="form-group">
              <label className="form-label">Launcher Padrão Ativo:</label>
              <div className="launcher-status-value" style={{
                color: defaultLauncher.includes('Nenhum') || defaultLauncher.includes('Sem') ? 'var(--accent-blue)' : 'var(--accent-teal)',
                fontWeight: 600
              }}>
                {defaultLauncher}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Selecione para Ações:</label>
              <div className="launcher-picker-group">
                <select 
                  className="device-select"
                  style={{flex: 1}}
                  value={selectedLauncher}
                  onChange={(e) => setSelectedLauncher(e.target.value)}
                  disabled={launchers.length === 0}
                >
                  {launchers.length === 0 ? (
                    <option value="">Nenhum Launcher alternativo listado</option>
                  ) : (
                    launchers.map(lnc => (
                      <option key={lnc} value={lnc}>{lnc}</option>
                    ))
                  )}
                </select>
                <button className="btn" onClick={loadLauncherInfo} title="Buscar Launchers">
                  <RefreshCw size={15} />
                </button>
              </div>
            </div>

            <div className="app-actions-grid" style={{marginTop: '5px'}}>
              <button 
                className="btn btn-blue" 
                onClick={setLauncherDefault}
                disabled={!selectedLauncher || !selectedDevice}
              >
                🏠 Definir Padrão
              </button>
              <button 
                className="btn" 
                onClick={clearLauncherDefault}
                disabled={!selectedDevice}
                style={{background: '#2c2c36'}}
              >
                🧹 Limpar Padrão
              </button>
            </div>

            <button 
              className="btn" 
              onClick={triggerLauncherPicker}
              disabled={!selectedDevice}
              style={{background: '#2c2c36', padding: '10px'}}
            >
              📺 Abrir Menu do Seletor no Aparelho
            </button>
          </section>

        </div>

        {/* COLUNA DIREITA: LISTAGEM E CONTROLE DE APPS */}
        <section className="card">
          <h2 className="card-title">
            <Layers size={18} style={{color: 'var(--accent-teal)'}} />
            Gerenciador de Aplicativos
          </h2>

          <div className="search-container">
            <div style={{position: 'relative', flex: 1}}>
              <Search size={16} style={{position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)'}} />
              <input 
                type="text" 
                className="search-input" 
                style={{paddingLeft: '36px'}}
                placeholder="Filtrar aplicativos instalados..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <button className="btn" onClick={loadApps} title="Atualizar Lista">
              <RefreshCw size={15} />
            </button>
          </div>

          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
            <label className="checkbox-label">
              <input 
                type="checkbox" 
                checked={showSystemApps}
                onChange={(e) => setShowSystemApps(e.target.checked)}
              />
              Exibir Apps do Sistema
            </label>
            <span style={{fontSize: '0.8rem', color: 'var(--text-muted)'}}>
              {filteredApps.length} de {apps.length} apps
            </span>
          </div>

          <ul className="app-list">
            {filteredApps.length === 0 ? (
              <li style={{padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-family)', fontSize: '0.85rem'}}>
                {selectedDevice ? 'Nenhum aplicativo corresponde à busca.' : 'Conecte um aparelho para listar os aplicativos.'}
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

          <div className="app-actions-grid">
            <button 
              className="btn btn-teal" 
              onClick={launchApp}
              disabled={!selectedApp}
            >
              <Play size={15} />
              Iniciar App
            </button>
            <button 
              className="btn" 
              onClick={stopApp}
              disabled={!selectedApp}
              style={{background: '#2c2c36'}}
            >
              <Square size={15} />
              Forçar Parada
            </button>
            <button 
              className="btn" 
              onClick={clearAppData}
              disabled={!selectedApp}
              style={{background: '#2c2c36'}}
            >
              🧹 Limpar Dados
            </button>
            <button 
              className="btn btn-red" 
              onClick={uninstallApp}
              disabled={!selectedApp}
            >
              <Trash2 size={15} />
              Desinstalar App
            </button>

            {/* NOVA AÇÃO: TESTAR LAUNCHER SELECIONADO NA LISTA */}
            <button 
              className="btn btn-primary btn-wide" 
              onClick={testLauncherSelected}
              disabled={!selectedApp}
              style={{background: 'linear-gradient(135deg, var(--accent-purple) 0%, var(--accent-blue) 100%)'}}
            >
              <Sparkles size={15} />
              Testar Launcher Selecionado
            </button>

            {/* NOVA AÇÃO: EXTRAIR E BAIXAR APK PARA O COMPUTADOR */}
            <button 
              className="btn btn-teal btn-wide" 
              onClick={downloadSelectedAppApk}
              disabled={!selectedApp}
              style={{background: 'linear-gradient(135deg, var(--accent-teal) 0%, #00b0ff 100%)', color: '#0d0d0d'}}
            >
              <Upload size={15} style={{ transform: 'rotate(180deg)' }} />
              Baixar APK para o PC [Download]
            </button>
          </div>
        </section>

      </main>

      {/* --- CARD INFERIOR: CONSOLE LOG --- */}
      <footer className="card console-card">
        <h2 className="card-title" style={{borderBottom: 'none', paddingBottom: 0}}>
          <Terminal size={18} style={{color: 'var(--accent-teal)'}} />
          Log do Sistema / Terminal ADB
        </h2>

        <div className="console-output">
          {logs.length === 0 ? (
            <div style={{color: 'var(--text-muted)'}}>Console ocioso. Conecte um aparelho para iniciar logs.</div>
          ) : (
            logs.map((logLine, idx) => (
              <div key={idx}>{logLine}</div>
            ))
          )}
          <div ref={consoleEndRef} />
        </div>

        <div className="console-actions">
          <button className="btn" onClick={() => apiFetch('/api/logs', { method: 'POST' })} style={{padding: '5px 12px', fontSize: '0.75rem'}}>
            Limpar Logs do Console
          </button>
        </div>
      </footer>

      {/* OVERLAY DE SERVIDOR OFFLINE */}
      {!localServerRunning && (
        <div className="overlay" style={{ zIndex: 10000, background: 'rgba(10, 10, 15, 0.96)' }}>
          <div className="card" style={{ maxWidth: '550px', textAlign: 'center', padding: '40px', border: '1px solid rgba(124, 77, 255, 0.3)' }}>
            <AlertCircle size={48} style={{ color: 'var(--accent-purple)', margin: '0 auto 20px auto' }} />
            <h1 style={{ color: '#fff', fontSize: '1.8rem', fontWeight: 700, marginBottom: '10px' }}>
              Servidor Desktop Offline
            </h1>
            <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '25px', fontSize: '0.95rem' }}>
              Para que este painel da web possa se conectar com os seus dispositivos Android (TV, Celular) via USB ou Wi-Fi, o servidor local do ADB Companion precisa estar rodando no seu computador.
            </p>
            
            <div style={{ background: '#13131c', borderRadius: '12px', padding: '20px', marginBottom: '25px', border: '1px solid #1f1f2e' }}>
              <p style={{ fontSize: '0.9rem', color: '#8888a5', margin: '0 0 10px 0' }}>Já tem o aplicativo instalado?</p>
              <p style={{ fontSize: '0.95rem', color: 'var(--accent-teal)', fontWeight: 600, margin: 0 }}>
                Basta abrir o arquivo <strong>ADB_Companion.exe</strong>
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <a 
                href="/ADB_Companion_Setup.exe" 
                className="btn btn-purple btn-wide" 
                style={{ 
                  background: 'linear-gradient(135deg, var(--accent-purple) 0%, #a855f7 100%)', 
                  color: '#fff', 
                  textDecoration: 'none',
                  padding: '12.5px',
                  fontWeight: 700,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '8px',
                  boxShadow: '0 4px 15px rgba(124, 77, 255, 0.4)'
                }}
                download
              >
                <Smartphone size={18} style={{ marginRight: '8px' }} />
                Baixar Instalador do ADB Companion (.exe) - Recomendado
              </a>

              <a 
                href="/ADB_Companion.zip" 
                className="btn" 
                style={{ 
                  background: 'transparent', 
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#ccc', 
                  textDecoration: 'none',
                  padding: '10px',
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '8px',
                  fontSize: '0.9rem'
                }}
                download
              >
                <Upload size={16} style={{ marginRight: '8px', transform: 'rotate(180deg)' }} />
                Baixar Versão Portátil (.zip)
              </a>
              <span style={{ fontSize: '0.8rem', color: '#55556d' }}>
                O instalador oficial (.exe) ajuda a evitar falsos positivos de vírus no Windows Defender.
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
