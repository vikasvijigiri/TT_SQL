import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Zap, RefreshCw, Brain, Trash2, Database,
  FolderKanban, MessageSquare, Eraser, HardDrive,
  Clock, Calendar, ShieldAlert
} from 'lucide-react';
import QueryInput from './components/QueryInput';
import AgentLogs from './components/AgentLogs';
import ResultDisplay from './components/ResultDisplay';
import DatasetView from './components/DatasetView';
import DatabaseView from './components/DatabaseView';
import ProjectsScreen from './components/ProjectsScreen';
import './App.css';

const API_BASE_URL = 'http://localhost:8001';

function App() {
  const [loading, setLoading] = useState(false);
  const [isCheckingDb, setIsCheckingDb] = useState(false);
  const [dbConnected, setDbConnected] = useState(null);
  const [executionHistory, setExecutionHistory] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [currentStage, setCurrentStage] = useState('');
  const [messages, setMessages] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('sample.jsonl');
  const [isPrepping, setIsPrepping] = useState(false);
  const [prepStatus, setPrepStatus] = useState('Ready');
  const [currentView, setCurrentView] = useState('projects');
  const [showRawLogs, setShowRawLogs] = useState({});
  const [lastInstanceId, setLastInstanceId] = useState(null);
  const [activeProject, setActiveProject] = useState(null);
  const [sampleQuestions, setSampleQuestions] = useState([]);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const [storageStats, setStorageStats] = useState(null);

  const get_active_project_slug_js = (project) => {
    if (!project) return 'default_project';
    return project.name.toLowerCase().replace(/[^a-z0-9]/g, '_');
  };

  const chatEndRef = useRef(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStage]);

  useEffect(() => {
    checkDbStatus();
    fetchActiveProject();
  }, []);

  useEffect(() => {
    if (activeProject?.id) {
      fetchSampleQuestions(activeProject.id);
    } else {
      setSampleQuestions([
        "How many batches had OTIF issues last month?",
        "Show me the top 5 products by delay"
      ]);
    }
  }, [activeProject]);

  useEffect(() => {
    if (currentView === 'maintenance') {
      fetchStorageStats();
    }
  }, [currentView, activeProject]);

  const fetchStorageStats = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/data/storage/workspaces`);
      setStorageStats(res.data);
    } catch (err) {
      console.error("Failed to fetch storage stats", err);
    }
  };

  const handleWipeWorkspace = async (slug, projectName) => {
    if (!window.confirm(`CRITICAL: This will permanently delete ALL results (SQL, CSV, logs) for the workspace "${projectName || slug}". This action cannot be undone. Proceed?`)) return;

    try {
      setLoading(true);
      await axios.delete(`${API_BASE_URL}/api/data/cleanup/workspace/${slug}`);
      if (activeProject && get_active_project_slug_js(activeProject) === slug) {
        setExecutionHistory("");
        setMessages([]);
        setLastInstanceId(null);
      }
      fetchStorageStats();
      alert(`Workspace "${projectName || slug}" cleared.`);
    } catch (err) {
      console.error(err);
      alert("Failed to wipe workspace data");
    } finally {
      setLoading(false);
    }
  };

  const fetchActiveProject = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/projects/active`);
      if (res.data.project) {
        setActiveProject(res.data.project);
      } else {
        setActiveProject(null);
      }
    } catch (err) {
      console.error("Failed to fetch active project", err);
    }
  };

  const fetchSampleQuestions = async (projectId) => {
    setIsLoadingSamples(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/projects/${projectId}/samples`);
      if (res.data.questions) {
        setSampleQuestions(res.data.questions);
      }
    } catch (err) {
      console.error("Failed to fetch sample questions", err);
    } finally {
      setIsLoadingSamples(false);
    }
  };

  const checkDbStatus = async () => {
    setIsCheckingDb(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/health/db`);
      setDbConnected(response.data.connected);
    } catch (err) {
      console.error('Failed to check DB status:', err);
      setDbConnected(false);
    } finally {
      setIsCheckingDb(false);
    }
  };

  const handleConnectDB = async (force = false) => {
    if (isPrepping) return;
    setIsPrepping(true);
    setPrepStatus('Starting');

    try {
      const response = await fetch(`${API_BASE_URL}/api/prep/run?force=${force}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error("Failed to start preparation");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.replace('data: ', '').trim());
              setPrepStatus(data.message);
              if (data.level === 'SUCCESS') {
                checkDbStatus();
                setTimeout(() => setPrepStatus('Ready'), 5000);
              } else if (data.level === 'ERROR') {
                setTimeout(() => setPrepStatus('Ready'), 5000);
              }
            } catch (e) {
              console.error("Error parsing SSE data", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setPrepStatus('Error');
      setTimeout(() => setPrepStatus('Ready'), 5000);
    } finally {
      setIsPrepping(false);
    }
  };

  const handleDeleteCollection = async () => {
    if (isPrepping) return;
    if (!window.confirm("Are you sure you want to delete the current vector collection? This action cannot be undone.")) return;
    setIsPrepping(true);
    setPrepStatus('Deleting');

    try {
      const response = await axios.delete(`${API_BASE_URL}/api/prep/collection`);
      if (response.data.status === 'success') {
        setPrepStatus('Deleted');
        checkDbStatus();
        setTimeout(() => setPrepStatus('Ready'), 3000);
      }
    } catch (err) {
      console.error('Failed to delete collection:', err);
      setPrepStatus('Error');
      setTimeout(() => setPrepStatus('Ready'), 3000);
    } finally {
      setIsPrepping(false);
    }
  };

  const fetchExecutionHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/api/data/logs/history`);
      setExecutionHistory(response.data.content);
    } catch (err) {
      console.error("Failed to fetch execution history:", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleClearCache = async () => {
    if (!lastInstanceId) {
      alert("No active query to clear from cache.");
      return;
    }

    if (!window.confirm(`Are you sure you want to clear the cache for query ${lastInstanceId}?`)) return;

    try {
      const response = await axios.delete(`${API_BASE_URL}/api/data/cache/${lastInstanceId}`);
      if (response.data.status === 'success') {
        alert(`Cache cleared successfully for ${lastInstanceId}.`);
        fetchExecutionHistory();
      }
    } catch (err) {
      console.error("Failed to clear cache:", err);
      alert("Error clearing cache: " + err.message);
    }
  };

  const handlePurgeProject = async () => {
    if (!activeProject) return;
    if (!window.confirm(`WARNING: This will permanently delete ALL analytical results (SQL, CSV, logs) for the project "${activeProject.name}". This action cannot be undone. Proceed?`)) return;

    try {
      setLoading(true);
      await axios.delete(`${API_BASE_URL}/api/data/cleanup/project`);
      setExecutionHistory("");
      setMessages([]);
      setLastInstanceId(null);
      fetchStorageStats();
      alert("Project results successfully purged.");
    } catch (err) {
      console.error(err);
      alert("Failed to purge project results");
    } finally {
      setLoading(false);
    }
  };

  const handlePurgeSession = async (period) => {
    const periodLabels = { hour: 'Last Hour', today: 'Today', yesterday: 'Yesterday' };
    if (!window.confirm(`Clear session results for: ${periodLabels[period]}?`)) return;

    try {
      setLoading(true);
      const res = await axios.delete(`${API_BASE_URL}/api/data/cleanup/session?period=${period}`);
      alert(`Cleaned up ${res.data.deleted_files || 0} files from session.`);
      fetchExecutionHistory();
      fetchStorageStats();
    } catch (err) {
      console.error(err);
      alert("Failed to clear session data");
    } finally {
      setLoading(false);
    }
  };

  // Real-time log polling while query is active
  useEffect(() => {
    let interval;
    if (loading) {
      interval = setInterval(() => {
        fetchExecutionHistory();
      }, 3000); // Poll every 3 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading]);

  const handleSendQuery = async (query) => {
    if (loading) return;

    const userMessage = { id: Date.now(), role: 'user', content: query };
