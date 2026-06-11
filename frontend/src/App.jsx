import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  BarChart3,
  Database,
  Activity,
  Cpu,
  CheckCircle2,
  XCircle,
  Play,
  Settings,
  Search,
  ChevronRight,
  Zap,
  Clock,
  Layers,
  ArrowLeft,
  TerminalSquare,
  Copy,
  Check,
  Filter,
  RefreshCw,
  Sliders,
  Terminal,
  FileSpreadsheet,
  Save,
  FileCode,
  SlidersHorizontal,
  Workflow,
  Repeat,
  Move,
  Plus,
  Minus,
  Network,
  Sparkles,
  Globe,
  ShieldCheck,
  Brain,
  Compass,
  Maximize2,
  Minimize2,
  PlusCircle,
  Wand2,
  CornerDownRight,
  Trash2,
  ListFilter,
  Send,
  MessageSquare,
  AlertTriangle,
  DollarSign,
  ShieldAlert,
  Trophy,
  TrendingUp,
  FolderOpen
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import CustomWorkspace from './components/CustomWorkspace';
import PipelineFlow from './components/PipelineFlow';
import LandingPage from './components/LandingPage';
import PipelinePulse from './components/PipelinePulse';

const API_BASE = "http://localhost:8001/api";


const colorClasses = {
  blue: {
    border: 'hover:border-blue-500/50',
    bg: 'bg-blue-500/5',
    bgHover: 'group-hover:bg-blue-500/10',
    text: 'text-blue-400 bg-blue-500/10'
  },
  indigo: {
    border: 'hover:border-indigo-500/50',
    bg: 'bg-indigo-500/5',
    bgHover: 'group-hover:bg-indigo-500/10',
    text: 'text-indigo-400 bg-indigo-500/10'
  },
  emerald: {
    border: 'hover:border-emerald-500/50',
    bg: 'bg-emerald-500/5',
    bgHover: 'group-hover:bg-emerald-500/10',
    text: 'text-emerald-400 bg-emerald-500/10'
  },
  rose: {
    border: 'hover:border-rose-500/50',
    bg: 'bg-rose-500/5',
    bgHover: 'group-hover:bg-rose-500/10',
    text: 'text-rose-400 bg-rose-500/10'
  },
  violet: {
    border: 'hover:border-violet-500/50',
    bg: 'bg-violet-500/5',
    bgHover: 'group-hover:bg-violet-500/10',
    text: 'text-violet-400 bg-violet-500/10'
  }
};

const App = () => {
  const [selectedProject, setSelectedProject] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(null);
  const [dbResults, setDbResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [runningDbs, setRunningDbs] = useState({});
  const [runningInstances, setRunningInstances] = useState({});
  const [copiedType, setCopiedType] = useState(null);
  const [workers, setWorkers] = useState(4);
  const [currentView, setCurrentView] = useState('landing');
  const [searchQuery, setSearchQuery] = useState('');

  // â”€â”€ DAB Benchmark State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const [dabQueries, setDabQueries] = useState([]);
  const [dabDatabases, setDabDatabases] = useState([]);
  const [dabMetrics, setDabMetrics] = useState(null);
  const [dabRepoOk, setDabRepoOk] = useState(null);
  const [dabLoading, setDabLoading] = useState(false);
  const [dabRunning, setDabRunning] = useState(false);
  const [dabFilter, setDabFilter] = useState('all'); // all | pending | passed | failed | running
  const [dabSearchQ, setDabSearchQ] = useState('');
  const [dabSelectedQuery, setDabSelectedQuery] = useState(null);
  const [dabDetail, setDabDetail] = useState(null);
  const [dabDetailLoading, setDabDetailLoading] = useState(false);
  const [dabSkipDocker, setDabSkipDocker] = useState(true);
  const [dabSubmissions, setDabSubmissions] = useState([]);
  const [selectedSubmission, setSelectedSubmission] = useState(null);
  const [dabActiveTab, setDabActiveTab] = useState('pipeline'); // 'pipeline' | 'leaderboard'
  // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  // Self-Improvement Pipeline State
  const [improvementStatus, setImprovementStatus] = useState(null);
  const [improvementRunning, setImprovementRunning] = useState(false);

  // DAB Live Investigation Feed State
  const [dabRecentRuns, setDabRecentRuns] = useState([]);

  // LangSmith Evaluator State
  const [langsmithStatus, setLangsmithStatus] = useState(null);
  const [langsmithEvalRunning, setLangsmithEvalRunning] = useState(false);
  const [langsmithScores, setLangsmithScores] = useState([]);

  // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  // Modal state
  const [selectedDetails, setSelectedDetails] = useState(null);
  const [detailsTab, setDetailsTab] = useState('sql');
  const [recentRuns, setRecentRuns] = useState([]);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [isGlobalRunning, setIsGlobalRunning] = useState(false);

  // Metric Modal State
  const [showMetricModal, setShowMetricModal] = useState(false);
  const [activeMetricFilter, setActiveMetricFilter] = useState('total');
  const [allInstanceResults, setAllInstanceResults] = useState([]);
  const [loadingMetricInstances, setLoadingMetricInstances] = useState(false);
  const [metricSearchQuery, setMetricSearchQuery] = useState('');

  // Global Run Dialog & Spidey Mascot State
  const [showGlobalRunModal, setShowGlobalRunModal] = useState(false);
  const [spideyQuip, setSpideyQuip] = useState("Crawling Snowflake schemas... ðŸ•µï¸");
  const [globalRunConfig, setGlobalRunConfig] = useState({
    temperature: 0.0,
    scope: 'missing_only',
    maxRetries: 4,
    dialect: 'snowflake'
  });

  // Single Instance Live Execution Drawer State
  const [showLiveDrawer, setShowLiveDrawer] = useState(false);
  const [activeLiveInstance, setActiveLiveInstance] = useState(null);
  const [liveExecutionData, setLiveExecutionData] = useState(null);
  const [liveTimer, setLiveTimer] = useState(0);

  // Pipeline Tuning & Settings State
  const [prompts, setPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [promptContent, setPromptContent] = useState('');
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [systemSettings, setSystemSettings] = useState({
    llm: { temperature: 0.0, model: "bedrock/openai.gpt-oss-safeguard-120b" },
    batch: { workers: 4 },
    orchestrator: { max_retries: 4, pruning_threshold_tokens: 3500 }
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [saveStatusMessage, setSaveStatusMessage] = useState('');


  // ðŸ”¬ FORENSIC DIAGNOSTICS TELEMETRY STATE
  const [showDiagnoseDrawer, setShowDiagnoseDrawer] = useState(false);
  const [diagnoseData, setDiagnoseData] = useState(null);
  const [loadingDiagnose, setLoadingDiagnose] = useState(false);

  const handleDiagnose = async (dbName, instanceId) => {
    setLoadingDiagnose(true);
    setShowDiagnoseDrawer(true);
    setDiagnoseData(null);
    try {
      const res = await axios.get(`${API_BASE}/diagnose/${dbName}/${instanceId}`);
      setDiagnoseData(res.data);
    } catch (err) {
      console.error("Diagnosis request failed", err);
      setDiagnoseData({
        success: false,
        error: "Failed to connect to the forensic diagnosis engine."
      });
    } finally {
      setLoadingDiagnose(false);
    }
  };

  const [fixingIssues, setFixingIssues] = useState(false);
  const [fixResult, setFixResult] = useState(null);

  const handleFixIssues = async (dbName, instanceId) => {
    setFixingIssues(true);
    setFixResult(null);
    try {
      const res = await axios.post(`${API_BASE}/fix_issues/${dbName}/${instanceId}`);
      setFixResult(res.data);
      if (res.data.success && !res.data.pending_acceptance) {
        const diagRes = await axios.get(`${API_BASE}/diagnose/${dbName}/${instanceId}`);
        setDiagnoseData(diagRes.data);
        if (selectedDb) {
          axios.get(`${API_BASE}/results/${selectedDb}`).then(r => setDbResults(r.data));
        }
      }
    } catch (err) {
      console.error("Fix issues request failed", err);
      setFixResult({
        success: false,
        reverted: true,
        message: "Autonomous repair loop encountered an exception and reverted all artifacts back to original state."
      });
    } finally {
      setFixingIssues(false);
    }
  };

  const handleAcceptFix = async (dbName, instanceId) => {
    if (!fixResult) return;
    try {
      await axios.post(`${API_BASE}/accept_fix/${dbName}/${instanceId}`, {
        corrected_sql: fixResult.corrected_sql,
        reasoning: fixResult.reasoning || [],
        modifications: fixResult.modifications || [],
        verification: fixResult.verification || "",
        temp_id: fixResult.temp_id
      });
      setFixResult(prev => ({
        ...prev,
        pending_acceptance: false,
        success: true,
        message: "Repair accepted and permanently saved to artifacts."
      }));
      const diagRes = await axios.get(`${API_BASE}/diagnose/${dbName}/${instanceId}`);
      setDiagnoseData(diagRes.data);
      if (selectedDb) {
        axios.get(`${API_BASE}/results/${selectedDb}`).then(r => setDbResults(r.data));
      }
    } catch (err) {
      console.error("Accept fix failed", err);
    }
  };

  const handleRejectFix = async (dbName, instanceId) => {
    if (!fixResult) return;
    try {
      await axios.post(`${API_BASE}/reject_fix/${dbName}/${instanceId}`, {
        temp_id: fixResult.temp_id
      });
      setFixResult(null);
    } catch (err) {
      console.error("Reject fix failed", err);
      setFixResult(null);
    }
  };

  useEffect(() => {
    fetchData();
    fetchPromptsAndSettings();
    fetchImprovementStatus();
    fetchLangsmithStatus();
    fetchLangsmithScores();
    const interval = setInterval(fetchData, 3000);
    const improvementInterval = setInterval(fetchImprovementStatus, 60000);
    const langsmithInterval = setInterval(fetchLangsmithStatus, 120000);
    return () => {
      clearInterval(interval);
      clearInterval(improvementInterval);
      clearInterval(langsmithInterval);
    };
  }, []);

  const fetchData = async () => {
    try {
      const [mRes, dRes, rRes, eRes] = await Promise.all([
        axios.get(`${API_BASE}/metrics`),
        axios.get(`${API_BASE}/databases`),
        axios.get(`${API_BASE}/results/recent`),
        axios.get(`${API_BASE}/evaluate/status`)
      ]);
      setMetrics(mRes.data);
      setDatabases(dRes.data);
      setRecentRuns(rRes.data);
      setIsEvaluating(eRes.data.running);
      setLoading(false);
    } catch (err) {
      console.error("Fetch failed", err);
    }
  };

  const fetchDabRecentRuns = async () => {
    try {
      const res = await axios.get(`${API_BASE}/dab/results/recent`);
      setDabRecentRuns(res.data);
    } catch (err) {
      // fail silently
    }
  };

  const fetchImprovementStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/improvement/status`);
      setImprovementStatus(res.data);
    } catch (err) {
      // endpoint may not exist yet â€” fail silently
    }
  };

  const triggerImprovementRun = async () => {
    setImprovementRunning(true);
    try {
      await axios.post(`${API_BASE}/improvement/run`);
      setTimeout(fetchImprovementStatus, 3000);
    } catch (err) {
      console.error("Failed to trigger improvement run", err);
    } finally {
      setImprovementRunning(false);
    }
  };

  const fetchLangsmithStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/langsmith/status`);
      setLangsmithStatus(res.data);
      setLangsmithEvalRunning(res.data?.eval_running ?? false);
    } catch (err) {
      // fail silently
    }
  };

  const fetchLangsmithScores = async () => {
    try {
      const res = await axios.get(`${API_BASE}/langsmith/scores`);
      setLangsmithScores(res.data?.scores ?? []);
    } catch (err) {
      // fail silently
    }
  };

  const triggerLangsmithEval = async () => {
    setLangsmithEvalRunning(true);
    try {
      await axios.post(`${API_BASE}/langsmith/run_eval`);
      setTimeout(fetchLangsmithStatus, 5000);
    } catch (err) {
      console.error("Failed to trigger LangSmith eval", err);
      setLangsmithEvalRunning(false);
    }
  };

  const buildLangsmithDataset = async () => {
    try {
      await axios.post(`${API_BASE}/langsmith/build_dataset`);
      setTimeout(fetchLangsmithStatus, 3000);
    } catch (err) {
      console.error("Failed to build LangSmith dataset", err);
    }
  };

  const fetchPromptsAndSettings = async () => {
    try {
      const [pRes, sRes, tRes] = await Promise.all([
        axios.get(`${API_BASE}/prompts`),
        axios.get(`${API_BASE}/settings`),
        axios.get(`${API_BASE}/topology`)
      ]);
      setPrompts(pRes.data);
      if (pRes.data.length > 0) {
        setSelectedPrompt(pRes.data[0]);
        setPromptContent(pRes.data[0].content);
      }
      if (sRes.data && sRes.data.llm) {
        setSystemSettings(sRes.data);
        if (sRes.data.batch && sRes.data.batch.workers) {
          setWorkers(sRes.data.batch.workers);
        }
      }
      if (tRes.data && tRes.data.nodes && tRes.data.nodes.length > 0) {
        setWorkflowNodes(tRes.data.nodes);
        setWorkflowConnections(tRes.data.connections || []);
      }
    } catch (err) {
      console.error("Failed to load prompts/settings/topology", err);
    }
  };

  const handleSelectPrompt = (p) => {
    if (!p) return;
    setSelectedPrompt(p);
    setPromptContent(p.content || '');
  };

  const handleSelectNode = (node) => {
    if (isConnectingMode) {
      if (!connectingFrom) {
        setConnectingFrom(node.id);
        setSaveStatusMessage(`Arrow Source: [${node.title}] â€¢ Click target agent`);
      } else {
        if (connectingFrom !== node.id) {
          const isExists = workflowConnections.some(c => c.from === connectingFrom && c.to === node.id);
          if (!isExists) {
            const newConn = {
              id: `c_${Date.now()}`,
              from: connectingFrom,
              to: node.id,
              isFeedback: false
            };
            setWorkflowConnections(prev => [...prev, newConn]);
            setSaveStatusMessage(`Created Arrow: ${connectingFrom} âž” ${node.id}`);
          } else {
            setSaveStatusMessage("Connection already exists.");
          }
        }
        setConnectingFrom(null);
        setIsConnectingMode(false);
        setTimeout(() => setSaveStatusMessage(''), 2500);
      }
      return;
    }

    const found = prompts.find(p => p.id === node.targetFile);
    if (found) {
      handleSelectPrompt(found);
    } else {
      const newP = {
        id: node.targetFile,
        category: 'Custom Spawned Agent',
        path: `backend/app/prompts/${node.targetFile}`,
        content: `# System prompt protocol for ${node.title}\n# Category: ${node.category}\n\n`
      };
      setPrompts(prev => [...prev, newP]);
      handleSelectPrompt(newP);
    }

    setShowCopilotDrawer(true);
    setCopilotInput(`Modify agent [${node.title}] (${node.targetFile}): `);
  };

  const handleSavePrompt = async () => {
    if (!selectedPrompt) return;
    setSavingPrompt(true);
    try {
      await axios.post(`${API_BASE}/prompts/${selectedPrompt.id}`, { content: promptContent });
      setSaveStatusMessage(`Saved protocol: ${selectedPrompt.id}`);
      setTimeout(() => setSaveStatusMessage(''), 2500);
      setPrompts(prev => prev.map(item => item.id === selectedPrompt.id ? { ...item, content: promptContent } : item));
    } catch (err) {
      console.error("Failed to save prompt", err);
      setSaveStatusMessage("Save failed!");
      setTimeout(() => setSaveStatusMessage(''), 2500);
    } finally {
      setSavingPrompt(false);
    }
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      const updated = {
        ...systemSettings,
        batch: { ...systemSettings.batch, workers: workers }
      };
      await Promise.all([
        axios.post(`${API_BASE}/settings`, updated),
        axios.post(`${API_BASE}/topology`, { nodes: workflowNodes, connections: workflowConnections })
      ]);
      setSaveStatusMessage("Architecture, Wiring & Config updated successfully!");
      setTimeout(() => setSaveStatusMessage(''), 3000);
    } catch (err) {
      console.error("Failed to save settings/topology", err);
      setSaveStatusMessage("Settings save failed!");
      setTimeout(() => setSaveStatusMessage(''), 3000);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleCopilotSubmit = async (e) => {
    e.preventDefault();
    if (!copilotInput.trim() || copilotLoading) return;

    const userMsg = copilotInput.trim();
    const nextId = Date.now();
    setCopilotMessages(prev => [...prev, { id: nextId, sender: 'user', text: userMsg }]);
    setCopilotInput('');
    setCopilotLoading(true);

    try {
      const res = await axios.post(`${API_BASE}/copilot/agent`, {
        user_prompt: userMsg,
        active_agents: workflowNodes.map(n => n.title)
      });

      if (res.data.error) {
        setCopilotMessages(prev => [...prev, { id: Date.now(), sender: 'ai', isError: true, text: `âš ï¸ Error: ${res.data.error}` }]);
      } else {
        const { agent, prompt, message } = res.data;
        setCopilotMessages(prev => [...prev, { id: Date.now(), sender: 'ai', text: `âš¡ Successfully architected agent: **${agent.title}**\nðŸ’¾ Saved protocol to \`${agent.targetFile}\`!` }]);

        const spawnY = Math.max(100, Math.min(650, workflowNodes.length * 80));
        const selectedColor = categoryColors[agent.category] || categoryColors['Custom'];

        const newNode = {
          ...agent,
          x: 260,
          y: spawnY,
          color: selectedColor,
          icon: Wand2
        };

        setWorkflowNodes(prev => [...prev, newNode]);
        setPrompts(prev => [...prev, prompt]);
        handleSelectPrompt(prompt);
        setSaveStatusMessage(`ðŸ¤– Spawned AI agent: ${agent.title}!`);
        setTimeout(() => setSaveStatusMessage(''), 3000);
      }
    } catch (err) {
      console.error("Copilot request failed", err);
      setCopilotMessages(prev => [...prev, { id: Date.now(), sender: 'ai', isError: true, text: "âš ï¸ LLM generation failed or network timeout." }]);
    } finally {
      setCopilotLoading(false);
    }
  };

  const handleRunSandbox = async (e) => {
    e.preventDefault();
    if (!sandboxAgent || sandboxLoading) return;
    setSandboxLoading(true);
    setSandboxResult(null);
    try {
      const res = await axios.post(`${API_BASE}/test/agent`, {
        agent_id: sandboxAgent.title,
        prompt_file: sandboxAgent.targetFile,
        input_query: sandboxInput,
        context_data: sandboxContext
      });
      setSandboxResult(res.data);
      setSaveStatusMessage(`ðŸ§ª Tested agent ${sandboxAgent.title} successfully!`);
      setTimeout(() => setSaveStatusMessage(''), 3000);
    } catch (err) {
      console.error("Sandbox test failed", err);
      setSandboxResult({ error: "Network error or LLM execution timeout." });
    } finally {
      setSandboxLoading(false);
    }
  };

  const handleSpawnAgent = (e) => {
    e.preventDefault();
    if (!newAgentForm.title || !newAgentForm.targetFile) {
      alert("Please provide both Title and Target Filename (e.g., my_agent.yaml)");
      return;
    }

    const newId = `agent_${Date.now()}`;
    const newFileName = newAgentForm.targetFile.endsWith('.yaml') ? newAgentForm.targetFile : `${newAgentForm.targetFile}.yaml`;
    const selectedColor = categoryColors[newAgentForm.category] || categoryColors['Custom'];

    const spawnY = Math.max(100, Math.min(650, workflowNodes.length * 80));

    const newNode = {
      id: newId,
      targetFile: newFileName,
      title: newAgentForm.title,
      category: newAgentForm.category,
      desc: newAgentForm.desc || 'Custom dynamically spawned agentic processor.',
      x: 260,
      y: spawnY,
      color: selectedColor,
      icon: Wand2,
      isLoop: newAgentForm.isLoop
    };

    setWorkflowNodes(prev => [...prev, newNode]);

    const newPromptEntry = {
      id: newFileName,
      category: `${newAgentForm.category} Protocol`,
      path: `backend/app/prompts/${newFileName}`,
      content: `# Dynamic Prompt Protocol: ${newAgentForm.title}\n# Category: ${newAgentForm.category}\n\n# INSTRUCTIONS:\n# Define your custom agent execution rules and reasoning laws here...\n`
    };

    setPrompts(prev => [...prev, newPromptEntry]);
    handleSelectPrompt(newPromptEntry);

    setShowCreateModal(false);
    setNewAgentForm({ title: '', category: 'Custom', desc: '', targetFile: '', isLoop: false });
    setSaveStatusMessage(`Spawned new agent: ${newAgentForm.title}!`);
    setTimeout(() => setSaveStatusMessage(''), 2500);
  };

  const updateLoopRetries = (delta) => {
    const current = systemSettings.orchestrator?.max_retries ?? 4;
    const nextVal = Math.max(1, Math.min(10, current + delta));
    setSystemSettings(prev => ({
      ...prev,
      orchestrator: { ...prev.orchestrator, max_retries: nextVal }
    }));
  };

  // DRAG CARD LOGIC
  const handleMouseDown = (e, node) => {
    if (e.target.closest('.no-drag') || activeDragWire || isConnectingMode) return;
    const activeRef = isMaxCanvas ? canvasRefMax : canvasRefStandard;
    if (!activeRef.current) return;
    const container = activeRef.current;
    const rect = container.getBoundingClientRect();
    setDraggingNode(node.id);
    setDragOffset({
      x: e.clientX - rect.left - node.x,
      y: e.clientY - rect.top - node.y
    });
  };

  // DRAGGABLE WIRE MOUSE DOWN (ORIGIN SOCKET)
  const handleWireMouseDown = (e, node) => {
    e.stopPropagation();
    e.preventDefault();
    if (isConnectingMode) return;

    const activeRef = isMaxCanvas ? canvasRefMax : canvasRefStandard;
    if (!activeRef.current) return;
    const container = activeRef.current;
    const rect = container.getBoundingClientRect();

    const startX = node.x + 150;
    const startY = node.y + (node.isLoop ? 175 : 145);

    const curX = e.clientX - rect.left;
    const curY = e.clientY - rect.top;

    setActiveDragWire({
      fromNodeId: node.id,
      startX: startX,
      startY: startY,
      currentX: curX,
      currentY: curY
    });
    setHoveredTargetNode(null);
    setSaveStatusMessage(`âš¡ Dragging connection from [${node.title}]... Drop onto any target agent!`);
  };

  // GLOBAL MOUSE MOVE
  const handleMouseMove = (e) => {
    const activeRef = isMaxCanvas ? canvasRefMax : canvasRefStandard;
    if (!activeRef.current) return;
    const container = activeRef.current;
    const rect = container.getBoundingClientRect();

    const curX = e.clientX - rect.left;
    const curY = e.clientY - rect.top;

    const scrollBox = document.getElementById(isMaxCanvas ? 'scrollContainerMax' : 'scrollContainerStandard');
    if (scrollBox && (draggingNode || activeDragWire)) {
      const boxRect = scrollBox.getBoundingClientRect();
      if (e.clientY < boxRect.top + 80) scrollBox.scrollTop -= 25;
      if (e.clientY > boxRect.bottom - 80) scrollBox.scrollTop += 25;
    }

    if (draggingNode) {
      const newX = Math.max(10, Math.min(rect.width - 300, curX - dragOffset.x));
      const newY = Math.max(10, Math.min(1200, curY - dragOffset.y));
      setWorkflowNodes(prev => prev.map(n => n.id === draggingNode ? { ...n, x: newX, y: newY } : n));
    }

    if (activeDragWire) {
      setActiveDragWire(prev => ({ ...prev, currentX: curX, currentY: curY }));

      const targetCard = workflowNodes.find(n => {
        if (n.id === activeDragWire.fromNodeId) return false;
        const cardWidth = 300;
        const cardHeight = n.isLoop ? 175 : 145;
        return curX >= n.x && curX <= n.x + cardWidth && curY >= n.y && curY <= n.y + cardHeight;
      });

      if (targetCard && hoveredTargetNode !== targetCard.id) {
        setHoveredTargetNode(targetCard.id);
      } else if (!targetCard && hoveredTargetNode) {
        setHoveredTargetNode(null);
      }
    }
  };

  const handleCardMouseUp = (e, targetId) => {
    e.stopPropagation();
    if (activeDragWire && activeDragWire.fromNodeId !== targetId) {
      const isExists = workflowConnections.some(c => c.from === activeDragWire.fromNodeId && c.to === targetId);
      if (!isExists) {
        const newConn = {
          id: `c_${Date.now()}`,
          from: activeDragWire.fromNodeId,
          to: targetId,
          isFeedback: false
        };
        setWorkflowConnections(prev => [...prev, newConn]);
        setSaveStatusMessage(`Successfully wired ${activeDragWire.fromNodeId} âž” ${targetId}!`);
      } else {
        setSaveStatusMessage("Connection already exists.");
      }
      setActiveDragWire(null);
      setHoveredTargetNode(null);
      setTimeout(() => setSaveStatusMessage(''), 2500);
    }
  };

  const handleMouseUp = () => {
    if (draggingNode) {
      setDraggingNode(null);
    }

    if (activeDragWire) {
      if (hoveredTargetNode && hoveredTargetNode !== activeDragWire.fromNodeId) {
        const isExists = workflowConnections.some(c => c.from === activeDragWire.fromNodeId && c.to === hoveredTargetNode);
        if (!isExists) {
          const newConn = {
            id: `c_${Date.now()}`,
            from: activeDragWire.fromNodeId,
            to: hoveredTargetNode,
            isFeedback: false
          };
          setWorkflowConnections(prev => [...prev, newConn]);
          setSaveStatusMessage(`Successfully wired ${activeDragWire.fromNodeId} âž” ${hoveredTargetNode}!`);
        } else {
          setSaveStatusMessage("Connection already exists.");
        }
      } else {
        setSaveStatusMessage("Connection released without snapping to target.");
      }
      setActiveDragWire(null);
      setHoveredTargetNode(null);
      setTimeout(() => setSaveStatusMessage(''), 2500);
    }
  };

  const handleRemoveConnection = (connId) => {
    setWorkflowConnections(prev => prev.filter(c => c.id !== connId));
  };

  useEffect(() => {
    let interval;
    const isRunning = Object.values(runningInstances).some(v => v === true);
    if (currentView === 'database' && selectedDb) {
      const pollRate = isRunning ? 2000 : 8000;
      interval = setInterval(() => {
        axios.get(`${API_BASE}/results/${selectedDb}`).then(res => {
          const newData = res.data;
          setDbResults(newData);
          if (isRunning) {
            setRunningInstances(prev => {
              const next = { ...prev };
              let changed = false;
              const finalStatuses = ['success', 'empty', 'error'];
              newData.forEach(inst => {
                if (next[inst.id] && inst.status !== 'running' && finalStatuses.includes(inst.status)) {
                  next[inst.id] = false;
                  changed = true;
                }
              });
              return changed ? next : prev;
            });
          }
        }).catch(console.error);
      }, pollRate);
    }
    return () => clearInterval(interval);
  }, [currentView, selectedDb, runningInstances]);

  useEffect(() => {
    let interval;
    if (showLiveDrawer && activeLiveInstance && selectedDb) {
      const pollLive = () => {
        axios.get(`${API_BASE}/live_execution/${selectedDb}/${activeLiveInstance}`)
          .then(res => {
            setLiveExecutionData(res.data);
            setLiveTimer(res.data?.elapsed_seconds || 0);
            if (res.data.status !== 'running') {
              axios.get(`${API_BASE}/results/${selectedDb}`).then(r => setDbResults(r.data));
            }
          })
          .catch(console.error);
      };
      pollLive();
      interval = setInterval(pollLive, 1500);
    }
    return () => clearInterval(interval);
  }, [showLiveDrawer, activeLiveInstance, selectedDb]);

  useEffect(() => {
    let ticker;
    if (showLiveDrawer && liveExecutionData?.status === 'running') {
      ticker = setInterval(() => {
        setLiveTimer(prev => parseFloat((prev + 0.1).toFixed(1)));
      }, 100);
    }
    return () => clearInterval(ticker);
  }, [showLiveDrawer, liveExecutionData?.status]);

  useEffect(() => {
    const quips = [
      "Crawling Snowflake schemas... no bugs found! ðŸ•µï¸",
      "Pruning 50,000 columns before breakfast! â˜•",
      "Did someone say INNER JOIN? ðŸ•¸ï¸",
      "Zero-knowledge identifier rules active! ðŸ›¡ï¸",
      "Self-correcting your syntax errors... âœ¨",
      "Data IQ probe parity match 1.000! ðŸŽ¯",
      "All identifiers properly FQN escaped! ðŸš€"
    ];
    let idx = 0;
    const interval = setInterval(() => {
      idx = (idx + 1) % quips.length;
      setSpideyQuip(quips[idx]);
    }, 4500);
    return () => clearInterval(interval);
  }, []);

  const handleRunDb = async (dbName) => {
    setRunningDbs(prev => ({ ...prev, [dbName]: true }));
    try {
      await axios.post(`${API_BASE}/run/${dbName}?workers=${workers}`);
      setTimeout(fetchData, 1500);
    } catch (err) {
      console.error("Run failed", err);
    } finally {
      setTimeout(() => setRunningDbs(prev => ({ ...prev, [dbName]: false })), 2500);
    }
  };

  const handleRunInstance = async (instanceId) => {
    setRunningInstances(prev => ({ ...prev, [instanceId]: true }));
    setActiveLiveInstance(instanceId);
    setShowLiveDrawer(true);
    try {
      await axios.post(`${API_BASE}/run_instance/${instanceId}`);
      setTimeout(() => {
        axios.get(`${API_BASE}/results/${selectedDb}`).then(res => setDbResults(res.data));
      }, 1500);
    } catch (err) {
      console.error("Run instance failed", err);
      setRunningInstances(prev => ({ ...prev, [instanceId]: false }));
    }
  };

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    setCopiedType(type);
    setTimeout(() => setCopiedType(null), 2000);
  };

  // â”€â”€ DAB Handler Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const fetchDabData = async () => {
    setDabLoading(true);
    try {
      const [rCheck, rQueries, rMetrics, rSubmissions, rDatabases] = await Promise.all([
        axios.get(`${API_BASE}/dab/repo_check`),
        axios.get(`${API_BASE}/dab/queries`),
        axios.get(`${API_BASE}/dab/metrics`),
        axios.get(`${API_BASE}/dab/submissions`),
        axios.get(`${API_BASE}/dab/databases`),
      ]);
      setDabRepoOk(rCheck.data);
      setDabQueries(rQueries.data);
      setDabMetrics(rMetrics.data);
      setDabSubmissions(rSubmissions.data);
      setDabDatabases(rDatabases.data);
      if (rDatabases.data && rDatabases.data.length > 0) {
        // Reset/validate selectedDb for DAB workspace
        const isDabDb = rDatabases.data.some(db => db.name === selectedDb);
        if (!isDabDb) {
          setSelectedDb(rDatabases.data[0].name);
        }
      }
      if (rSubmissions.data && rSubmissions.data.length > 0) {
        setSelectedSubmission(prev => prev || rSubmissions.data[0]);
      }
      fetchDabRecentRuns();
    } catch (err) {
      console.error('DAB fetch failed', err);
    } finally {
      setDabLoading(false);
    }
  };

  const fetchDabDetail = async (dataset, queryId) => {
    setDabDetailLoading(true);
    setDabDetail(null);
    try {
      const res = await axios.get(`${API_BASE}/dab/results/${dataset}/${queryId}`);
      setDabDetail(res.data);
    } catch (err) {
      console.error('DAB detail fetch failed', err);
    } finally {
      setDabDetailLoading(false);
    }
  };

  const runDabSingle = async (dataset, queryId) => {
    try {
      await axios.post(`${API_BASE}/dab/run/${dataset}/${queryId}`);
      setTimeout(fetchDabData, 1500);
    } catch (err) {
      console.error('DAB single run failed', err);
    }
  };

  const runDabAll = async () => {
    setDabRunning(true);
    try {
      await axios.post(`${API_BASE}/dab/run_all`, { skip_docker: dabSkipDocker, force_rerun: false });
      const pollInterval = setInterval(async () => {
        try {
          const [rQ, rM, rStatus] = await Promise.all([
            axios.get(`${API_BASE}/dab/queries`),
            axios.get(`${API_BASE}/dab/metrics`),
            axios.get(`${API_BASE}/dab/status`),
          ]);
          setDabQueries(rQ.data);
          setDabMetrics(rM.data);
          if (rStatus.data.count === 0) {
            clearInterval(pollInterval);
            setDabRunning(false);
          }
        } catch { clearInterval(pollInterval); setDabRunning(false); }
      }, 5000);
    } catch (err) {
      console.error('DAB batch run failed', err);
      setDabRunning(false);
    }
  };

  const stopDabAll = async () => {
    try {
      await axios.post(`${API_BASE}/dab/stop`);
      // UI will naturally exit running state when the backend finishes the active query
      // and returns count === 0 in the pollInterval
    } catch (err) {
      console.error('DAB stop failed', err);
    }
  };
  // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const fetchResults = async (dbName) => {
    setSelectedDb(dbName);
    setCurrentView('database');
    setLoadingDetails(true);


    try {
      const res = await axios.get(`${API_BASE}/results/${dbName}`);
      setDbResults(res.data);
    } catch (err) {
      console.error("Results fetch failed", err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const fetchInstanceDetails = async (instanceId) => {
    try {
      const res = await axios.get(`${API_BASE}/details/${selectedDb}/${instanceId}`);
      setSelectedDetails({ id: instanceId, ...res.data });
      setDetailsTab('sql');
    } catch (err) {
      console.error("Failed to fetch instance details", err);
    }
  };

  const handleOpenMetricModal = async (filterType) => {
    setActiveMetricFilter(filterType);
    setShowMetricModal(true);
    setLoadingMetricInstances(true);
    try {
      const res = await axios.get(`${API_BASE}/results/all`);
      setAllInstanceResults(res.data);
    } catch (err) {
      console.error("Failed to fetch all instances", err);
    } finally {
      setLoadingMetricInstances(false);
    }
  };

  const fetchInstanceDetailsFromModal = async (dbName, instanceId) => {
    try {
      setSelectedDb(dbName);
      const res = await axios.get(`${API_BASE}/details/${dbName}/${instanceId}`);
      setSelectedDetails({ id: instanceId, ...res.data });
      setDetailsTab('sql');
      setShowMetricModal(false);
    } catch (err) {
      console.error("Failed to fetch details", err);
    }
  };

  const filteredMetricInstances = allInstanceResults.filter(inst => {
    const matchesSearch = inst.id.toLowerCase().includes(metricSearchQuery.toLowerCase()) || inst.db.toLowerCase().includes(metricSearchQuery.toLowerCase());
    if (!matchesSearch) return false;
    if (activeMetricFilter === 'succeeded') return inst.status === 'success' || inst.status === 'empty';
    if (activeMetricFilter === 'errored') return inst.status === 'error';
    if (activeMetricFilter === 'gold') return inst.gold_status === 'gold_pass';
    return true;
  });

  const handleGlobalRunAll = async () => {
    setIsGlobalRunning(true);
    setShowGlobalRunModal(false);
    try {
      await axios.post(`${API_BASE}/run_all?workers=1&scope=${globalRunConfig.scope}&temperature=${globalRunConfig.temperature}&max_retries=${globalRunConfig.maxRetries}&dialect=${globalRunConfig.dialect}`);
      setTimeout(fetchData, 1000);
    } catch (err) {
      console.error("Global run all failed", err);
    } finally {
      setTimeout(() => {
        setIsGlobalRunning(false);
      }, 3500);
    }
  };

  const handleGlobalEvaluate = async () => {
    setIsEvaluating(true);
    try {
      await axios.post(`${API_BASE}/evaluate/all`);
      setTimeout(fetchData, 1000);
    } catch (err) {
      console.error("Global evaluate failed", err);
      setIsEvaluating(false);
    }
  };

  const getComplexityBadge = (complexity, type, score) => {
    const displayScore = score > 0 ? score.toFixed(2) : null;
    const displayType = type || (complexity ? String(complexity).toUpperCase() : 'UNCLASSIFIED');

    let colorClass = "text-slate-400 bg-slate-800/80 border border-slate-700/30";
    if (score >= 0.75 || complexity === 'complex' || (complexity && complexity.includes('nested') && !complexity.includes('non_nested'))) {
      colorClass = "text-pink-400 bg-pink-500/10 border border-pink-500/20";
    } else if (score >= 0.45 || complexity === 'medium' || (complexity && complexity.includes('non_nested'))) {
      colorClass = "text-purple-400 bg-purple-500/10 border border-purple-500/20";
    } else if (score > 0 || complexity === 'easy') {
      colorClass = "text-blue-400 bg-blue-500/10 border border-blue-500/20";
    }

    return (
      <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1.5 shrink-0 ${colorClass}`} title={`Complexity Type: ${displayType}`}>
        <span>{displayType}</span>
        {displayScore && (
          <span className="opacity-90 px-1 rounded bg-black/40 text-[8px] font-black text-white border border-white/10">
            {displayScore}
          </span>
        )}
      </span>
    );
  };

  const getStatusIcon = (status) => {
    if (status === 'success') return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
    if (status === 'empty') return <Activity className="w-4 h-4 text-amber-400 shrink-0" />;
    if (status === 'error') return <XCircle className="w-4 h-4 text-rose-500 shrink-0" />;
    if (status === 'running') return <Activity className="w-4 h-4 text-blue-400 animate-spin shrink-0" />;
    return <Layers className="w-4 h-4 text-slate-500 shrink-0" />;
  };

  const filteredDatabases = databases.filter(db =>
    db.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Landing page must be checked before project selection
  if (currentView === 'landing') {
    return <LandingPage onEnter={() => setCurrentView('dashboard')} />;
  }

  if (selectedProject === null) {
    return (
      <div
        className="flex flex-col items-center justify-center min-h-screen w-full bg-[#070709] text-slate-200 font-sans p-6 overflow-y-auto select-none"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          backgroundColor: '#07070b'
        }}
      >
        <div className="max-w-5xl w-full space-y-10 text-center">
          {/* Main Title & Header */}
          <div className="space-y-4">
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="inline-flex items-center gap-3 bg-[#12121a] border border-[#222232] px-4 py-2 rounded-full text-xs font-mono text-cyan-400 font-bold"
            >
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span>ZEN AGENTIC SQL WORKBENCH v2.0</span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.8 }}
              className="text-4xl sm:text-5xl font-black tracking-tight text-white leading-none bg-gradient-to-r from-white via-slate-200 to-slate-500 bg-clip-text text-transparent"
            >
              Forensic Benchmark Hub
            </motion.h1>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.8 }}
              className="text-sm sm:text-base text-slate-400 max-w-xl mx-auto leading-relaxed"
            >
              Select an execution workspace benchmark to inspect reasoning graphs, audit database outputs, edit prompt protocols, and execute autonomous SQL agent repairs.
            </motion.p>
          </div>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 text-left">
            {/* Spider2-Lite Card */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 100 }}
              whileHover={{ y: -6, borderColor: 'rgba(59, 130, 246, 0.5)' }}
              onClick={() => { setSelectedProject('spider'); setCurrentView('dashboard'); }}
              className="bg-[#0e0e14]/90 backdrop-blur border border-[#1e1e2c] p-6 rounded-2xl cursor-pointer shadow-xl relative overflow-hidden group flex flex-col justify-between min-h-[280px]"
            >
              <div className="absolute -right-12 -bottom-12 w-40 h-40 bg-blue-500/5 rounded-full blur-3xl group-hover:bg-blue-500/10 transition-all pointer-events-none" />
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 bg-blue-600/10 border border-blue-500/30 rounded-xl flex items-center justify-center text-blue-400 shadow-lg shadow-blue-500/10">
                    <Database className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/20">
                    DIALECT PROBES
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-black font-mono text-white group-hover:text-blue-400 transition-colors">
                    Spider2-Lite Studio
                  </h2>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Evaluate agentic text-to-SQL workflows on complex databases (Snowflake, SQLite, DuckDB). Inspect schema links, bridge table queries, FQN casing resolution, and closed-loop syntax corrections.
                  </p>
                </div>
              </div>
              <div className="pt-6 flex items-center gap-1.5 text-xs text-blue-400 font-bold font-mono group-hover:gap-2.5 transition-all">
                <span>OPEN WORKSPACE</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </motion.div>

            {/* DAB Card */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 100 }}
              whileHover={{ y: -6, borderColor: 'rgba(139, 92, 246, 0.5)' }}
              onClick={() => { setSelectedProject('dab'); setCurrentView('dashboard'); fetchDabData(); }}
              className="bg-[#0e0e14]/90 backdrop-blur border border-[#1e1e2c] p-6 rounded-2xl cursor-pointer shadow-xl relative overflow-hidden group flex flex-col justify-between min-h-[280px]"
            >
              <div className="absolute -right-12 -bottom-12 w-40 h-40 bg-violet-500/5 rounded-full blur-3xl group-hover:bg-violet-500/10 transition-all pointer-events-none" />
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 bg-violet-600/10 border border-violet-500/30 rounded-xl flex items-center justify-center text-violet-400 shadow-lg shadow-violet-500/10">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-violet-500/15 text-violet-400 border border-violet-500/20">
                    REASONING AGENTS
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-black font-mono text-white group-hover:text-violet-400 transition-colors">
                    DataAgentBench (DAB) Studio
                  </h2>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Evaluate data agents executing multi-step reasoning questions, interacting with complex datasets using DuckDB and SQLite, and verifying execution outputs under rigorous evaluation rules.
                  </p>
                </div>
              </div>
              <div className="pt-6 flex items-center gap-1.5 text-xs text-violet-400 font-bold font-mono group-hover:gap-2.5 transition-all">
                <span>OPEN WORKSPACE</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </motion.div>

            {/* Custom Project Card */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, type: 'spring', stiffness: 100 }}
              whileHover={{ y: -6, borderColor: 'rgba(16, 185, 129, 0.5)' }}
              onClick={() => { setSelectedProject('custom'); setCurrentView('projects'); }}
              className="bg-[#0e0e14]/90 backdrop-blur border border-[#1e1e2c] p-6 rounded-2xl cursor-pointer shadow-xl relative overflow-hidden group flex flex-col justify-between min-h-[280px]"
            >
              <div className="absolute -right-12 -bottom-12 w-40 h-40 bg-emerald-500/5 rounded-full blur-3xl group-hover:bg-emerald-500/10 transition-all pointer-events-none" />
              <div className="absolute -left-6 -top-6 w-24 h-24 bg-teal-500/3 rounded-full blur-2xl pointer-events-none" />
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 bg-emerald-600/10 border border-emerald-500/30 rounded-xl flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/10">
                    <FolderOpen className="w-6 h-6" />
                  </div>
                  <span className="text-[10px] font-mono font-bold tracking-wider px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                    YOUR DATA
                  </span>
                </div>
                <div>
                  <h2 className="text-lg font-black font-mono text-white group-hover:text-emerald-400 transition-colors">
                    Custom Project
                  </h2>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Connect your own database â€” PostgreSQL, SQLite, BigQuery, or Snowflake â€” and explore it with AI-powered natural language queries. No benchmarks, just your data.
                  </p>
                </div>
              </div>
              <div className="pt-6 flex items-center gap-1.5 text-xs text-emerald-400 font-bold font-mono group-hover:gap-2.5 transition-all">
                <span>START PROJECT</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    );
  }

  if (selectedProject === 'custom') {
    return <CustomWorkspace onBack={() => setSelectedProject(null)} />;
  }

  return (
    <div
      className="flex h-screen w-full overflow-hidden bg-[#070709] text-slate-200 font-sans selection:bg-blue-500/30 selection:text-white"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* Compact Pro Sidebar */}
      <aside className="w-16 lg:w-56 border-r border-[#1a1a22] bg-[#0c0c10] flex flex-col p-4 gap-6 shrink-0 z-20 shadow-2xl animate-fadeIn">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 px-1">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shadow-lg border border-white/10 shrink-0 ${selectedProject === 'spider' ? 'bg-gradient-to-tr from-blue-600 to-indigo-500 shadow-blue-500/20' : 'bg-gradient-to-tr from-violet-600 to-indigo-500 shadow-violet-500/20'}`}>
              {selectedProject === 'spider' ? <Database className="w-4 h-4 text-white" /> : <Sparkles className="w-4 h-4 text-white" />}
            </div>
            <span className="hidden lg:block font-black text-sm tracking-tighter bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              {selectedProject === 'spider' ? (
                <>Spider<span className="text-blue-400 font-extrabold">DIN</span></>
              ) : (
                <>DAB<span className="text-violet-400 font-extrabold">Bench</span></>
              )}
            </span>
          </div>

          <button
            onClick={() => setSelectedProject(null)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#14141d] border border-[#262638] hover:border-amber-500/50 hover:bg-[#1a1a26] text-slate-400 hover:text-amber-400 transition-all font-bold text-[11px] font-mono justify-center w-full shadow-md shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Switch Project</span>
          </button>
        </div>

        <nav className="flex flex-col gap-1 flex-1">
          <button
            onClick={() => setCurrentView('dashboard')}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'dashboard' ? (selectedProject === 'spider' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-inner' : 'bg-violet-500/10 text-violet-400 border border-violet-500/20 shadow-inner') : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <BarChart3 className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block truncate">Audit Dashboard</span>
          </button>
          <button
            onClick={() => {
              if (selectedProject === 'spider') {
                if (databases.length > 0) fetchResults(selectedDb || databases[0].name);
                else setCurrentView('database');
              } else {
                setCurrentView('database');
                if (!dabQueries.length) fetchDabData();
              }
            }}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${currentView === 'database' ? (selectedProject === 'spider' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-inner' : 'bg-violet-500/10 text-violet-400 border border-violet-500/20 shadow-inner') : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'}`}
          >
            <Terminal className="w-4 h-4 shrink-0" />
            <span className="hidden lg:block truncate">Execution Probes</span>
          </button>
        </nav>

        {/* Persistent Soothing Mascot: Zen SQL Core */}
        <div className="hidden lg:flex flex-col my-auto p-3.5 bg-[#0e0e14] rounded-2xl border border-[#20202a] shadow-[0_0_25px_rgba(6,182,212,0.06)] relative overflow-hidden group select-none transition-all hover:border-[#06b6d4]/40 hover:shadow-[0_0_30px_rgba(6,182,212,0.12)]">
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-cyan-500 via-indigo-500 to-purple-500 animate-pulse" />
          <div className="absolute -right-12 -bottom-12 w-32 h-32 bg-cyan-500/5 rounded-full blur-2xl group-hover:bg-cyan-500/10 transition-all pointer-events-none" />

          {/* Speech Bubble */}
          <div className="relative mb-3 bg-[#14141e] border border-[#252535] p-2.5 rounded-xl rounded-bl-none shadow-lg transition-all">
            <div className="text-[11px] font-mono text-slate-300 leading-tight min-h-[28px] flex items-center">
              {spideyQuip}
            </div>
            {/* Pointer triangle */}
            <div className="absolute -bottom-2 left-3 w-0 h-0 border-t-8 border-t-[#14141e] border-r-8 border-r-transparent border-l-0" />
          </div>

          {/* Animated SVG Mascot Illustration */}
          <div className="flex items-center justify-center py-4 relative">
            {/* Glowing background matrix particles */}
            <div className="absolute inset-0 flex items-center justify-around pointer-events-none opacity-20 group-hover:opacity-40 transition-opacity font-mono text-[9px] text-cyan-500">
              <span className="animate-[bounce_3s_infinite] inline-block">SELECT</span>
              <span className="animate-[ping_4s_infinite] inline-block">âœ§</span>
              <span className="animate-[bounce_3.5s_infinite] inline-block">JOIN</span>
            </div>

            {/* Highly Peaceful Zen Holographic Sphere Core */}
            <svg className="w-24 h-24 overflow-visible" viewBox="0 0 100 100">
              <defs>
                <radialGradient id="peaceGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.4" />
                  <stop offset="60%" stopColor="#3b82f6" stopOpacity="0.15" />
                  <stop offset="100%" stopColor="#0e0e14" stopOpacity="0" />
                </radialGradient>
                <linearGradient id="coreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#22d3ee" />
                  <stop offset="50%" stopColor="#06b6d4" />
                  <stop offset="100%" stopColor="#3b82f6" />
                </linearGradient>
                <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#a855f7" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.4" />
                </linearGradient>
              </defs>

              {/* Soothing background glow */}
              <circle cx="50" cy="50" r="45" fill="url(#peaceGlow)" className="animate-pulse" style={{ animationDuration: '4s' }} />

              {/* Slow moving orbital ring 1 */}
              <g className="animate-[spin_20s_linear_infinite]" style={{ transformOrigin: '50px 50px' }}>
                <ellipse
                  cx="50" cy="50" rx="36" ry="10"
                  fill="none" stroke="url(#ringGrad)" strokeWidth="1.2"
                  transform="rotate(30 50 50)"
                />
              </g>
              {/* Slow moving orbital ring 2 */}
              <g className="animate-[spin_30s_linear_infinite_reverse]" style={{ transformOrigin: '50px 50px' }}>
                <ellipse
                  cx="50" cy="50" rx="36" ry="10"
                  fill="none" stroke="url(#ringGrad)" strokeWidth="1.2"
                  transform="rotate(-45 50 50)"
                />
              </g>

              {/* The Central Breathing Core */}
              <circle
                cx="50" cy="50" r="14"
                fill="url(#coreGrad)"
                className="animate-pulse"
                style={{
                  animationDuration: '3s',
                  filter: 'drop-shadow(0 0 10px rgba(6, 182, 212, 0.5))'
                }}
              />

              {/* Tiny inner pure white sparkling element */}
              <circle
                cx="50" cy="50" r="5"
                fill="#ffffff"
                className="animate-ping"
                style={{ animationDuration: '3.5s' }}
              />
            </svg>
          </div>

          <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#1f1f2a] text-[10px] font-mono text-slate-400">
            <span className="flex items-center gap-1.5 text-cyan-400 font-bold tracking-tight">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse inline-block" />
              <span>ZEN SQL CORE</span>
            </span>
            <span className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded font-black text-[9px]">
              ONLINE
            </span>
          </div>
        </div>

        <div className="hidden lg:block mt-auto border-t border-[#1a1a22] pt-4">
          <div className="bg-[#121216] p-3 rounded-lg border border-[#22222a] shadow-inner">
            <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider mb-2">
              <span className="flex items-center gap-1.5"><Cpu className="w-3 h-3 text-blue-400" /> Concurrency</span>
              <span className="text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded font-black">{workers}x</span>
            </div>
            <input
              type="range" min="1" max="16" value={workers}
              onChange={(e) => setWorkers(parseInt(e.target.value))}
              className="w-full h-1.5 bg-[#22222a] rounded-full appearance-none accent-blue-500 cursor-pointer"
            />
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-[#070709] relative">
        {/* Compact Pro Top Navbar */}
        <header className="h-14 border-b border-[#1a1a22] bg-[#0c0c10]/90 backdrop-blur px-6 flex items-center justify-between shrink-0 z-10">
          <div className="flex items-center gap-4">
            <h1 className="text-sm font-black tracking-tight text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-blue-500" />
              {selectedProject === 'spider' ? (
                <>
                  {currentView === 'dashboard' && 'Spider2-Lite: Forensic Telemetry & Audit Matrix'}
                  {currentView === 'database' && `Spider2-Lite Manifest: ${selectedDb}`}
                  {currentView === 'tuning' && 'Spider2-Lite: Pipeline Monitor'}
                </>
              ) : (
                <>
                  {currentView === 'dashboard' && 'DataAgentBench: Forensic Dashboard'}
                  {currentView === 'database' && 'DataAgentBench: Execution Probes & Query Index'}
                  {currentView === 'tuning' && 'DataAgentBench: Pipeline Monitor'}
                </>
              )}
            </h1>
            <div className="hidden md:flex items-center gap-1.5 px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-mono text-emerald-400 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              SYSTEM ONLINE
            </div>
            {saveStatusMessage && (
              <span className="bg-blue-500/10 text-blue-400 border border-blue-500/30 px-3 py-1 rounded-lg text-xs font-mono font-bold animate-pulse">
                {saveStatusMessage}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {selectedProject === 'spider' ? (
              <>
                {currentView === 'dashboard' && (
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text" placeholder="Filter databases..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="bg-[#121216] border border-[#22222a] rounded-lg pl-8 pr-3 py-1 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500/50 transition-all w-44 font-mono"
                    />
                  </div>
                )}
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => setShowGlobalRunModal(true)}
                  disabled={isGlobalRunning || isEvaluating}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono font-bold text-xs transition-all shadow-lg border ${isGlobalRunning || isEvaluating
                    ? 'bg-[#16161e] text-slate-500 border-slate-800 cursor-not-allowed'
                    : 'bg-emerald-600/90 text-white border-emerald-400/40 hover:bg-emerald-500 shadow-emerald-500/20 hover:shadow-emerald-500/40'
                    }`}
                >
                  {isGlobalRunning ? <Activity className="w-3.5 h-3.5 animate-spin text-emerald-400" /> : <Play className="w-3.5 h-3.5" />}
                  {isGlobalRunning ? 'RUNNING ALL...' : 'GLOBAL RUN ALL'}
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={handleGlobalEvaluate}
                  disabled={isEvaluating || isGlobalRunning}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono font-bold text-xs transition-all shadow-lg border ${isEvaluating || isGlobalRunning
                    ? 'bg-[#16161e] text-slate-500 border-slate-800 cursor-not-allowed'
                    : 'bg-blue-600/90 text-white border-blue-400/40 hover:bg-blue-500 shadow-blue-500/20 hover:shadow-blue-500/40'
                    }`}
                >
                  {isEvaluating ? <Activity className="w-3.5 h-3.5 animate-spin text-blue-400" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  {isEvaluating ? 'AUDITING...' : 'GLOBAL EVALUATE'}
                </motion.button>
              </>
            ) : (
              <>
                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={fetchDabData}
                  disabled={dabLoading}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono font-bold text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-500 transition-all shadow-lg"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${dabLoading ? 'animate-spin' : ''}`} />
                  {dabLoading ? 'REFRESHING...' : 'REFRESH'}
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={runDabAll}
                  disabled={dabRunning || !dabRepoOk?.exists}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono font-bold text-xs transition-all border shadow-lg ${dabRunning ? 'bg-[#16161e] text-slate-500 border-slate-800 cursor-not-allowed' : 'bg-violet-600 text-white border-violet-400 hover:bg-violet-500 shadow-violet-500/20'
                    }`}
                >
                  {dabRunning ? <Activity className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                  {dabRunning ? 'RUNNING...' : 'RUN ALL QUERIES'}
                </motion.button>

                {dabRunning && (
                  <motion.button
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={stopDabAll}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono font-bold text-xs bg-red-600/10 text-red-500 border border-red-500/30 hover:bg-red-600/20 hover:border-red-500 transition-all shadow-lg"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    STOP
                  </motion.button>
                )}
              </>
            )}
          </div>
        </header>

        {/* Scrollable View Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 no-scrollbar">
          {currentView === 'dashboard' && (
            selectedProject === 'spider' ? (
              <>
                {/* Comprehensive Metrics Row */}
                <section className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3.5">
                  {metrics ? (
                    <>
                      <div
                        onClick={() => handleOpenMetricModal('total')}
                        className="bg-[#101014] border border-[#1f1f27] hover:border-blue-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-blue-500/5 rounded-full blur-xl group-hover:bg-blue-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>TOTAL PROCESSED</span>
                          <Database className="w-3.5 h-3.5 text-blue-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.total_processed ?? 0}</span>
                          <span className="text-[10px] font-mono text-blue-400 font-bold bg-blue-500/10 px-1.5 py-0.5 rounded">RUNS</span>
                        </div>
                      </div>

                      <div
                        onClick={() => handleOpenMetricModal('succeeded')}
                        className="bg-[#101014] border border-[#1f1f27] hover:border-emerald-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-emerald-500/5 rounded-full blur-xl group-hover:bg-emerald-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>SUCCEEDED (CSV)</span>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.succeeded_count ?? 0}</span>
                          <span className="text-[10px] font-mono text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded">VALID</span>
                        </div>
                      </div>

                      <div
                        onClick={() => handleOpenMetricModal('errored')}
                        className="bg-[#101014] border border-[#1f1f27] hover:border-rose-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-rose-500/5 rounded-full blur-xl group-hover:bg-rose-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>ERRORED</span>
                          <XCircle className="w-3.5 h-3.5 text-rose-500" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.errored_count ?? 0}</span>
                          <span className="text-[10px] font-mono text-rose-500 font-bold bg-rose-500/10 px-1.5 py-0.5 rounded">FAILED</span>
                        </div>
                      </div>

                      <div
                        onClick={() => handleOpenMetricModal('gold')}
                        className="bg-[#101014] border border-[#1f1f27] hover:border-amber-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-amber-500/5 rounded-full blur-xl group-hover:bg-amber-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>GOLD PASSED</span>
                          <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.gold_succeeded_count ?? 0}</span>
                          <span className="text-[10px] font-mono text-amber-400 font-bold bg-amber-500/10 px-1.5 py-0.5 rounded">PARITY</span>
                        </div>
                      </div>

                      <div
                        onClick={() => handleOpenMetricModal('gold')}
                        className="bg-[#101014] border border-[#1f1f27] hover:border-purple-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-purple-500/5 rounded-full blur-xl group-hover:bg-purple-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>GOLD ACCURACY</span>
                          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.gold_accuracy ?? '0.0%'}</span>
                          <span className="text-[10px] font-mono text-purple-400 font-bold bg-purple-500/10 px-1.5 py-0.5 rounded">BENCHMARK</span>
                        </div>
                      </div>

                      <div
                        onClick={() => handleOpenMetricModal('total')}
                        className="bg-[#101014] border border-[#1f1f27] hover:border-cyan-500/50 p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group cursor-pointer transition-all hover:scale-[1.02]"
                      >
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-cyan-500/5 rounded-full blur-xl group-hover:bg-cyan-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>AVG LATENCY</span>
                          <Clock className="w-3.5 h-3.5 text-cyan-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.avg_latency ?? '0.0s'}</span>
                          <span className="text-[10px] font-mono text-cyan-400 font-bold bg-cyan-500/10 px-1.5 py-0.5 rounded">PER QUERY</span>
                        </div>
                      </div>

                      <div className="bg-[#101014] border border-[#1f1f27] p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group">
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-fuchsia-500/5 rounded-full blur-xl group-hover:bg-fuchsia-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>AVG TOKENS / AGENT</span>
                          <Zap className="w-3.5 h-3.5 text-fuchsia-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-white">{metrics.avg_tokens_per_agent ?? '0'}</span>
                          <span className="text-[10px] font-mono text-fuchsia-400 font-bold bg-fuchsia-500/10 px-1.5 py-0.5 rounded">TOKENS</span>
                        </div>
                      </div>

                      <div className="bg-[#101014] border border-[#1f1f27] p-3.5 rounded-xl shadow-sm relative overflow-hidden flex flex-col justify-between group">
                        <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-violet-500/5 rounded-full blur-xl group-hover:bg-violet-500/10 transition-colors" />
                        <div className="flex justify-between items-center text-slate-400 text-[10px] font-mono font-bold uppercase tracking-wider">
                          <span>TOTAL / AVG COST</span>
                          <DollarSign className="w-3.5 h-3.5 text-violet-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-2xl font-mono font-extrabold tracking-tight text-violet-400">{metrics.total_cost ?? '$0.0000'}</span>
                          <span className="text-[10px] font-mono text-violet-400 font-bold bg-violet-500/10 px-1.5 py-0.5 rounded" title="Average Cost per Query Run">
                            {metrics.avg_cost_per_query ?? '$0.0000'} AVG
                          </span>
                        </div>
                      </div>
                    </>
                  ) : (
                    [1, 2, 3, 4, 5, 6, 7, 8].map(i => <div key={i} className="bg-[#101014] h-20 rounded-xl animate-pulse border border-[#1f1f27]" />)
                  )}
                </section>

                {/* â”€â”€ Daily Self-Improvement Audit Panel â”€â”€ */}
                <section className="bg-[#101014] border border-[#1f1f27] rounded-xl p-4 shadow-lg">
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                    <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                      Daily Self-Improvement Audit
                      {improvementStatus?.saturated && (
                        <span className="ml-2 text-[10px] font-mono font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 normal-case tracking-normal">
                          SATURATED
                        </span>
                      )}
                    </h2>
                    <button
                      onClick={triggerImprovementRun}
                      disabled={improvementRunning || improvementStatus?.saturated}
                      className="flex items-center gap-1.5 text-[10px] font-mono font-bold px-2.5 py-1 rounded border transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                    >
                      <RefreshCw className={`w-3 h-3 ${improvementRunning ? 'animate-spin' : ''}`} />
                      {improvementRunning ? 'RUNNINGâ€¦' : 'RUN NOW'}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Rule counts */}
                    <div className="flex flex-col gap-2">
                      <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1">Learned Rules</p>
                      <div className="grid grid-cols-2 gap-1.5">
                        {[
                          { label: 'ACTIVE', val: improvementStatus?.rule_counts?.ACTIVE ?? 0, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
                          { label: 'CANDIDATE', val: improvementStatus?.rule_counts?.CANDIDATE ?? 0, color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
                          { label: 'REJECTED', val: improvementStatus?.rule_counts?.REJECTED ?? 0, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20' },
                          { label: 'INACTIVE', val: improvementStatus?.rule_counts?.INACTIVE ?? 0, color: 'text-slate-400 bg-slate-500/10 border-slate-500/20' },
                        ].map(({ label, val, color }) => (
                          <div key={label} className={`rounded-lg p-2 text-center border ${color}`}>
                            <div className="text-xl font-mono font-extrabold">{val}</div>
                            <div className="text-[9px] font-mono opacity-70">{label}</div>
                          </div>
                        ))}
                      </div>
                      {improvementStatus?.baseline_pass_rate != null && (
                        <p className="text-[10px] font-mono text-slate-500 mt-1">
                          Baseline: <span className="text-slate-300">{improvementStatus.baseline_pass_rate}%</span>
                          &nbsp;â†’&nbsp;Now: <span className="text-emerald-400 font-bold">
                            {improvementStatus.accuracy_trend?.at(-1)?.pass_rate ?? improvementStatus.baseline_pass_rate}%
                          </span>
                        </p>
                      )}
                      {improvementStatus?.last_run && (
                        <p className="text-[10px] font-mono text-slate-600">
                          Last run: {new Date(improvementStatus.last_run).toLocaleString()}
                        </p>
                      )}
                    </div>

                    {/* Accuracy trend chart */}
                    <div className="flex flex-col gap-2">
                      <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1">Pass@1 Trend</p>
                      {improvementStatus?.accuracy_trend?.length > 1 ? (
                        <ResponsiveContainer width="100%" height={90}>
                          <LineChart data={improvementStatus.accuracy_trend} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                            <XAxis dataKey="date" tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#475569' }} tickLine={false} axisLine={false} />
                            <YAxis domain={[0, 100]} tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#475569' }} tickLine={false} axisLine={false} />
                            <Tooltip
                              contentStyle={{ background: '#101014', border: '1px solid #1f1f27', fontSize: 11, fontFamily: 'monospace', borderRadius: 6 }}
                              formatter={(v) => [`${v}%`, 'Pass@1']}
                              labelStyle={{ color: '#94a3b8' }}
                            />
                            <Line type="monotone" dataKey="pass_rate" stroke="#10b981" strokeWidth={2} dot={{ r: 3, fill: '#10b981' }} />
                          </LineChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="flex items-center justify-center h-[90px] rounded-lg bg-[#141419] border border-[#202029]">
                          <p className="text-[10px] font-mono text-slate-600">No trend data yet</p>
                        </div>
                      )}
                    </div>

                    {/* Round history */}
                    <div className="flex flex-col gap-2">
                      <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1">
                        Round History&nbsp;
                        <span className="normal-case font-normal text-slate-600">({improvementStatus?.total_rounds ?? 0} total)</span>
                      </p>
                      {improvementStatus?.recent_runs?.length > 0 ? (
                        <div className="space-y-1 max-h-[110px] overflow-y-auto no-scrollbar">
                          {[...(improvementStatus.recent_runs)].reverse().map((r, i) => {
                            const statusColor =
                              r.status === 'improved' ? 'text-emerald-400' :
                                r.status === 'saturated' ? 'text-amber-400' :
                                  r.status === 'perfect' ? 'text-sky-400' : 'text-slate-500';
                            return (
                              <div key={i} className="flex items-center justify-between bg-[#141419] rounded px-2.5 py-1.5 gap-2">
                                <span className="text-[9px] font-mono text-slate-500 shrink-0">{r.date} R{r.round}</span>
                                <span className={`text-[10px] font-mono font-bold ${statusColor} shrink-0`}>
                                  {r.delta > 0 ? `+${r.delta}` : r.delta} queries
                                </span>
                                <span className="text-[9px] font-mono text-slate-400 shrink-0">{r.pass_rate > 0 ? `${r.pass_rate}%` : 'â€”'}</span>
                                <span className="text-[9px] font-mono text-slate-600 shrink-0">{r.new_rules_added > 0 ? `${r.new_rules_added} rules` : ''}</span>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="flex items-center justify-center h-[90px] rounded-lg bg-[#141419] border border-[#202029]">
                          <p className="text-[10px] font-mono text-slate-600 text-center px-2">
                            No runs yet â€” pipeline runs daily at 02:00 UTC or click RUN NOW
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </section>

                {/* LangSmith Evaluator Scorecard */}
                <section className="bg-[#101014] border border-[#1f1f27] rounded-xl p-4 shadow-lg">
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                    <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                      <ShieldCheck className="w-3.5 h-3.5 text-violet-400" />
                      LangSmith Evaluator Scorecard
                      <span className={`ml-2 px-1.5 py-0.5 rounded text-[9px] font-mono ${
                        langsmithStatus?.connected ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-500/15 text-slate-500'
                      }`}>
                        {langsmithStatus?.connected ? 'CONNECTED' : 'CONNECTING...'}
                      </span>
                    </h2>
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono text-slate-600">
                        {langsmithStatus?.dataset_examples ?? 0} examples in dataset
                      </span>
                      <button
                        onClick={buildLangsmithDataset}
                        className="px-2 py-1 rounded text-[9px] font-mono bg-[#1a1a24] border border-[#2a2a3a] text-slate-400 hover:text-violet-400 hover:border-violet-500/40 transition-colors"
                      >
                        SYNC DATASET
                      </button>
                      <button
                        onClick={triggerLangsmithEval}
                        disabled={langsmithEvalRunning}
                        className={`px-2 py-1 rounded text-[9px] font-mono border transition-colors ${
                          langsmithEvalRunning
                            ? 'bg-violet-500/10 border-violet-500/30 text-violet-400 cursor-not-allowed'
                            : 'bg-[#1a1a24] border-[#2a2a3a] text-slate-400 hover:text-violet-400 hover:border-violet-500/40'
                        }`}
                      >
                        <span className="flex items-center gap-1">
                          <RefreshCw className={`w-2.5 h-2.5 ${langsmithEvalRunning ? 'animate-spin' : ''}`} />
                          {langsmithEvalRunning ? 'EVALUATING...' : 'RUN ALL EVALS'}
                        </span>
                      </button>
                      <a
                        href="https://smith.langchain.com"
                        target="_blank"
                        rel="noreferrer"
                        className="px-2 py-1 rounded text-[9px] font-mono bg-[#1a1a24] border border-[#2a2a3a] text-slate-400 hover:text-sky-400 hover:border-sky-500/40 transition-colors"
                      >
                        VIEW IN LANGSMITH â†—
                      </a>
                    </div>
                  </div>

                  {/* Evaluator cards grid */}
                  {(() => {
                    const evalKeys = [
                      { key: 'correctness', label: 'Correctness', desc: 'Ground-truth match', higherGood: true, color: 'emerald' },
                      { key: 'hallucination', label: 'Hallucination', desc: 'Fabricated output', higherGood: false, color: 'rose' },
                      { key: 'pii_leakage', label: 'PII Leakage', desc: 'Personal data exposure', higherGood: false, color: 'rose' },
                      { key: 'prompt_injection', label: 'Prompt Injection', desc: 'Injection in prompt', higherGood: false, color: 'amber' },
                      { key: 'toxicity', label: 'Toxicity', desc: 'Toxic output', higherGood: false, color: 'rose' },
                      { key: 'bias_fairness', label: 'Bias & Fairness', desc: 'Demographic bias', higherGood: false, color: 'amber' },
                      { key: 'perceived_error', label: 'Perceived Error', desc: 'User-visible errors', higherGood: false, color: 'amber' },
                      { key: 'user_satisfaction', label: 'User Satisfaction', desc: 'Satisfied responses', higherGood: true, color: 'emerald' },
                    ];

                    const summaries = langsmithStatus?.evaluator_summaries ?? {};

                    return (
                      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
                        {evalKeys.map(({ key, label, desc, higherGood, color }) => {
                          const s = summaries[key];
                          const mean = s?.mean ?? null;
                          const n = s?.n ?? 0;
                          const flagged = s?.flagged ?? 0;

                          // For "higherGood" metrics: green when high; for "lowerGood" (risk) metrics: green when low
                          const pct = mean !== null ? Math.round(mean * 100) : null;
                          const isGood = mean !== null && (higherGood ? mean >= 0.5 : mean <= 0.15);
                          const isMid  = mean !== null && (higherGood ? mean >= 0.3 : mean <= 0.4);

                          const valueColor = mean === null ? 'text-slate-600'
                            : isGood ? 'text-emerald-400'
                            : isMid ? 'text-amber-400'
                            : 'text-rose-400';

                          return (
                            <div key={key} className="bg-[#141419] border border-[#202029] rounded-lg p-2.5 flex flex-col gap-1">
                              <p className="text-[9px] font-mono font-bold uppercase tracking-wider text-slate-500 truncate">{label}</p>
                              <p className={`text-xl font-mono font-bold ${valueColor}`}>
                                {pct !== null ? `${pct}%` : 'â€”'}
                              </p>
                              <p className="text-[8px] font-mono text-slate-600 leading-tight">{desc}</p>
                              {n > 0 && (
                                <p className="text-[8px] font-mono text-slate-700">
                                  {higherGood ? `${Math.round(mean * n)}/${n} pass` : `${flagged}/${n} flagged`}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}

                  {/* Per-query score table (collapsed by default) */}
                  {langsmithScores.length > 0 && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-[9px] font-mono text-slate-500 hover:text-slate-300 transition-colors select-none">
                        Per-query evaluator scores ({langsmithScores.length} queries) â–¾
                      </summary>
                      <div className="mt-2 overflow-x-auto max-h-[200px] overflow-y-auto">
                        <table className="w-full text-[9px] font-mono border-collapse">
                          <thead>
                            <tr className="border-b border-[#202029] text-slate-500">
                              <th className="text-left py-1 pr-2 font-bold uppercase">ID</th>
                              <th className="text-left py-1 pr-2 font-bold uppercase">Dataset</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Correct</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Halluc.</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">PII</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Inject.</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Toxic</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Bias</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Err</th>
                              <th className="text-center py-1 px-1 font-bold uppercase">Sat.</th>
                            </tr>
                          </thead>
                          <tbody>
                            {langsmithScores.map((row, i) => (
                              <tr key={i} className="border-b border-[#161619] hover:bg-[#18181f] transition-colors">
                                <td className="py-1 pr-2 text-slate-400 truncate max-w-[80px]">{row.instance_id}</td>
                                <td className="py-1 pr-2 text-slate-500 truncate max-w-[60px]">{row.dataset}</td>
                                {['correctness','hallucination','pii_leakage','prompt_injection','toxicity','bias_fairness','perceived_error','user_satisfaction'].map(k => {
                                  const v = row[k];
                                  const isRisk = ['hallucination','pii_leakage','prompt_injection','toxicity','bias_fairness','perceived_error'].includes(k);
                                  const isBad = isRisk ? v > 0.5 : v < 0.5;
                                  return (
                                    <td key={k} className={`py-1 px-1 text-center font-bold ${
                                      v === null || v === undefined ? 'text-slate-700' :
                                      isBad ? 'text-rose-400' : 'text-emerald-400'
                                    }`}>
                                      {v !== null && v !== undefined ? (v > 0.5 ? (isRisk ? 'âœ—' : 'âœ“') : (isRisk ? 'âœ“' : 'âœ—')) : 'â€”'}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </details>
                  )}
                </section>

                {/* Grid Content: Databases & Recent Feed */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Repositories High-Density Table */}
                  <section className="lg:col-span-7 bg-[#101014] border border-[#1f1f27] rounded-xl p-4 flex flex-col shadow-lg">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                      <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                        <Database className="w-3.5 h-3.5 text-blue-400" />
                        Target Repositories Matrix
                      </h2>
                      <span className="text-[10px] font-mono font-bold text-slate-500 bg-[#16161c] px-2 py-0.5 rounded border border-white/5">
                        {filteredDatabases.length} UNITS
                      </span>
                    </div>

                    <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1 no-scrollbar">
                      {filteredDatabases.map((db) => {
                        const totalProcessed = db.results_count + db.empty_count + db.error_count;
                        const successPct = db.total_questions ? (db.results_count / db.total_questions) * 100 : 0;
                        const emptyPct = db.total_questions ? (db.empty_count / db.total_questions) * 100 : 0;
                        const errorPct = db.total_questions ? (db.error_count / db.total_questions) * 100 : 0;

                        return (
                          <div
                            key={db.name}
                            onClick={() => fetchResults(db.name)}
                            className={`group p-3 rounded-lg bg-[#141419] border border-[#202029] hover:border-blue-500/40 hover:bg-[#181820] transition-all cursor-pointer flex items-center justify-between ${selectedDb === db.name ? 'border-blue-500 bg-blue-500/5 shadow-[0_0_15px_rgba(59,130,246,0.15)]' : ''
                              }`}
                          >
                            <div className="flex items-center gap-3 w-full pr-4">
                              <div className={`w-8 h-8 shrink-0 rounded-md flex items-center justify-center font-bold text-xs ${db.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400'
                                }`}>
                                {db.status === 'completed' ? <CheckCircle2 className="w-4 h-4" /> : <Database className="w-4 h-4" />}
                              </div>

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <h3 className="font-mono font-bold text-xs truncate text-white group-hover:text-blue-400 transition-colors">
                                    {db.name}
                                  </h3>
                                  <div className="flex items-center gap-1.5 shrink-0">
                                    {db.tables_count > 0 && (
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-purple-400 bg-purple-500/10 border border-purple-500/20 flex items-center gap-1">
                                        <Layers className="w-2.5 h-2.5 shrink-0" />
                                        {db.tables_count} Tbls
                                      </span>
                                    )}
                                    {db.tokens > 0 && (
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1">
                                        <Zap className="w-2.5 h-2.5 shrink-0" />
                                        {db.tokens > 1000 ? `${(db.tokens / 1000).toFixed(1)}K` : db.tokens} Tokens
                                      </span>
                                    )}
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-blue-400 bg-blue-500/10 border border-blue-500/20">
                                      {db.total_questions} Qs
                                    </span>
                                  </div>
                                </div>

                                <div className="mt-2 w-full h-1 bg-[#0c0c10] rounded-full overflow-hidden flex">
                                  <div style={{ width: `${successPct}%` }} className="h-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] transition-all"></div>
                                  <div style={{ width: `${emptyPct}%` }} className="h-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)] transition-all"></div>
                                  <div style={{ width: `${errorPct}%` }} className="h-full bg-rose-500 shadow-[0_0_8px_rgba(239,68,68,0.5)] transition-all"></div>
                                </div>

                                <div className="flex items-center justify-between mt-1.5 text-[10px] font-mono text-slate-400">
                                  <span className="text-slate-500">Done: {totalProcessed}/{db.total_questions}</span>
                                  <div className="flex items-center gap-2 font-bold">
                                    <span className="text-emerald-400">{successPct.toFixed(0)}%</span>
                                    <span className="text-amber-400">{emptyPct.toFixed(0)}%</span>
                                    <span className="text-rose-500">{errorPct.toFixed(0)}%</span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            <button
                              className={`p-2 shrink-0 rounded-md bg-[#1e1e26] border border-[#2a2a36] hover:bg-blue-600 hover:text-white hover:border-blue-500 transition-all ${runningDbs[db.name] ? 'animate-spin bg-blue-500 text-white' : 'text-slate-300'
                                }`}
                              onClick={(e) => { e.stopPropagation(); handleRunDb(db.name); }}
                              title="Execute Batch Run"
                            >
                              {runningDbs[db.name] ? <Activity className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </section>

                  {/* Recent Investigations High-Density Log */}
                  <section className="lg:col-span-5 bg-[#101014] border border-[#1f1f27] rounded-xl p-4 flex flex-col shadow-lg">
                    <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                      <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                        <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                        Live Investigation Feed
                      </h2>
                      <span className="text-[10px] font-mono text-slate-500 bg-[#16161c] px-2 py-0.5 rounded border border-white/5">
                        {recentRuns.length} RECENT
                      </span>
                    </div>

                    <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1 no-scrollbar">
                      {recentRuns.length > 0 ? recentRuns.map((run) => {
                        const runDbObj = databases.find(d => d.name === run.db) || {};
                        return (
                          <div
                            key={run.id}
                            className="p-2.5 rounded-lg bg-[#141419] border border-[#202029] hover:border-emerald-500/30 hover:bg-[#181820] transition-all flex items-center justify-between group"
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className={`p-1.5 rounded-md shrink-0 ${run.gold_status === 'gold_pass' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-500'
                                }`}>
                                {run.gold_status === 'gold_pass' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                              </div>

                              <div className="flex flex-col min-w-0 gap-1">
                                <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                                  <span className="font-mono font-bold text-xs text-white truncate">{run.id}</span>
                                  <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-[#1e1e26] text-blue-400 border border-[#2a2a36] truncate">
                                    {run.db}
                                  </span>
                                  {run.latency > 0 && (
                                    <>
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1 shrink-0" title="Execution Time (Latency)">
                                        <Zap className="w-2.5 h-2.5 shrink-0 text-amber-400" />
                                        {run.latency}s
                                      </span>
                                      {run.cost > 0 && (
                                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-violet-400 bg-violet-500/10 border border-violet-500/20 flex items-center gap-1 shrink-0" title={`Cost Incurred: ${run.total_tokens?.toLocaleString() || 0} tokens`}>
                                          <DollarSign className="w-2.5 h-2.5 shrink-0 text-violet-400" />
                                          ${run.cost.toFixed(4)}
                                        </span>
                                      )}
                                    </>
                                  )}
                                  {(run.status === 'success' || run.status === 'empty') && (
                                    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0 ${run.rows > 0 ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'
                                      }`} title="Result Set Row Count">
                                      <Database className="w-2.5 h-2.5 shrink-0" />
                                      {run.rows} {run.rows === 1 ? 'Row' : 'Rows'}
                                    </span>
                                  )}
                                  {run.corrections > 0 && (
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 flex items-center gap-1 shrink-0" title="Self-Correction Rounds Triggered">
                                      <RefreshCw className="w-2.5 h-2.5 shrink-0 text-cyan-400" />
                                      {run.corrections} {run.corrections === 1 ? 'Fix' : 'Fixes'}
                                    </span>
                                  )}
                                  {getComplexityBadge(run.complexity, run.complexity_type, run.complexity_score)}
                                </div>
                                <span className="text-[10px] font-mono text-slate-500 flex items-center gap-1 mt-0.5">
                                  <Clock className="w-2.5 h-2.5" />
                                  {new Date(run.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                </span>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {run.gold_status === 'gold_pass' && (
                                <span className="text-[9px] font-mono font-black text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                                  GOLD PASS
                                </span>
                              )}
                              {run.gold_status === 'gold_fail' && (
                                <span className="text-[9px] font-mono font-black text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded">
                                  GOLD FAIL
                                </span>
                              )}
                              {run.status !== 'pending' && (
                                <button
                                  onClick={() => handleDiagnose(run.db, run.id)}
                                  className="p-1.5 rounded bg-[#1c1c24] text-slate-400 hover:text-white hover:bg-indigo-600 transition-colors"
                                  title="Diagnose Probe"
                                >
                                  <ShieldAlert className="w-3.5 h-3.5" />
                                </button>
                              )}
                              <button
                                onClick={() => fetchResults(run.db)}
                                className="p-1.5 rounded bg-[#1c1c24] text-slate-400 hover:text-white hover:bg-blue-600 transition-colors"
                                title="Drill down"
                              >
                                <ChevronRight className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        );
                      }) : (
                        <div className="py-16 text-center text-slate-600 font-mono text-xs italic bg-[#141419] rounded-lg border border-[#202029]">
                          Waiting for forensic execution telemetry...
                        </div>
                      )}
                    </div>
                  </section>
                </div>
              </>
            ) : (
              <div className="space-y-6 animate-fadeIn">
                {/* Repo Check Banner */}
                {dabRepoOk && !dabRepoOk.exists && (
                  <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-xs">
                    <AlertTriangle className="w-5 h-5 shrink-0" />
                    <div>
                      <div className="font-bold mb-0.5">DataAgentBench repo not found at {dabRepoOk.repo_path}</div>
                      <div className="text-amber-400/70">Run: <code className="bg-black/40 px-1 rounded">git lfs install && git clone https://github.com/ucbepic/DataAgentBench.git C:\Users\VikasVijigiri\Documents\DataAgentBench</code></div>
                    </div>
                  </div>
                )}

                {/* Tab Selector */}
                <div className="flex border-b border-[#22222a] gap-2 mb-2">
                  <button
                    onClick={() => setDabActiveTab('pipeline')}
                    className={`px-4 py-2 font-mono font-bold text-xs tracking-wide transition-all border-b-2 ${dabActiveTab === 'pipeline'
                      ? 'border-violet-500 text-violet-400 font-extrabold bg-violet-500/5'
                      : 'border-transparent text-slate-500 hover:text-slate-300 bg-transparent'
                      }`}
                  >
                    âš™ï¸ PIPELINE RUNNER
                  </button>
                  <button
                    onClick={() => setDabActiveTab('leaderboard')}
                    className={`px-4 py-2 font-mono font-bold text-xs tracking-wide transition-all border-b-2 ${dabActiveTab === 'leaderboard'
                      ? 'border-violet-500 text-violet-400 font-extrabold bg-violet-500/5'
                      : 'border-transparent text-slate-500 hover:text-slate-300 bg-transparent'
                      }`}
                  >
                    ðŸ† LEADERBOARD SUBMISSIONS
                  </button>
                </div>

                {dabActiveTab === 'pipeline' ? (
                  <>
                    {/* Accuracy Scorecard */}
                    {dabMetrics && (
                      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3.5">
                        {[
                          { label: 'TOTAL QUERIES', value: dabMetrics.total_queries, color: 'blue', sub: 'QUERIES' },
                          { label: 'EVALUATED', value: dabMetrics.evaluated, color: 'indigo', sub: 'DONE' },
                          { label: 'PASSED âœ…', value: dabMetrics.passed, color: 'emerald', sub: 'PASS@1' },
                          { label: 'FAILED âœ—', value: dabMetrics.failed, color: 'rose', sub: 'FAIL' },
                          { label: 'PASS@1 ACCURACY', value: dabMetrics.pass_at_1_pct, color: 'violet', sub: 'ACCURACY' },
                          { label: 'AVG LATENCY', value: dabMetrics.avg_latency || '0.0s', color: 'cyan', sub: 'PER QUERY' },
                          { label: 'AVG TOKENS / QUERY', value: dabMetrics.avg_tokens_per_agent || '0', color: 'fuchsia', sub: 'TOKENS' },
                          { label: 'TOTAL / AVG COST', value: dabMetrics.total_cost || '$0.0000', color: 'violet', sub: `${dabMetrics.avg_cost_per_query || '$0.0000'} AVG` },
                        ].map(({ label, value, color, sub }) => {
                          const cls = colorClasses[color] || colorClasses.blue;
                          return (
                            <div key={label} className={`bg-[#101014] border border-[#1f1f27] ${cls.border} p-3.5 rounded-xl relative overflow-hidden group transition-all`}>
                              <div className={`absolute -right-4 -bottom-4 w-16 h-16 ${cls.bg} rounded-full blur-xl ${cls.bgHover} transition-colors`} />
                              <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 mb-2">{label}</div>
                              <div className="text-2xl font-mono font-extrabold text-white">{value}</div>
                              <div className={`text-[10px] font-mono font-bold ${cls.text} px-1.5 py-0.5 rounded mt-1 inline-block`}>{sub}</div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Daily Self-Improvement Audit Panel â€” same as Spider dashboard */}
                    <section className="bg-[#101014] border border-[#1f1f27] rounded-xl p-4 shadow-lg">
                      <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                        <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                          Daily Self-Improvement Audit
                          {improvementStatus?.saturated && (
                            <span className="ml-2 text-[10px] font-mono font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 normal-case tracking-normal">SATURATED</span>
                          )}
                        </h2>
                        <button
                          onClick={triggerImprovementRun}
                          disabled={improvementRunning || improvementStatus?.saturated}
                          className="flex items-center gap-1.5 text-[10px] font-mono font-bold px-2.5 py-1 rounded border transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                        >
                          <RefreshCw className={`w-3 h-3 ${improvementRunning ? 'animate-spin' : ''}`} />
                          {improvementRunning ? 'RUNNINGâ€¦' : 'RUN NOW'}
                        </button>
                      </div>
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        <div className="flex flex-col gap-2">
                          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1">Learned Rules</p>
                          <div className="grid grid-cols-2 gap-1.5">
                            {[
                              { label: 'ACTIVE', val: improvementStatus?.rule_counts?.ACTIVE ?? 0, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
                              { label: 'CANDIDATE', val: improvementStatus?.rule_counts?.CANDIDATE ?? 0, color: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
                              { label: 'REJECTED', val: improvementStatus?.rule_counts?.REJECTED ?? 0, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20' },
                              { label: 'INACTIVE', val: improvementStatus?.rule_counts?.INACTIVE ?? 0, color: 'text-slate-400 bg-slate-500/10 border-slate-500/20' },
                            ].map(({ label, val, color }) => (
                              <div key={label} className={`rounded-lg p-2 text-center border ${color}`}>
                                <div className="text-xl font-mono font-extrabold">{val}</div>
                                <div className="text-[9px] font-mono opacity-70">{label}</div>
                              </div>
                            ))}
                          </div>
                          {improvementStatus?.baseline_pass_rate != null && (
                            <p className="text-[10px] font-mono text-slate-500 mt-1">
                              Baseline: <span className="text-slate-300">{improvementStatus.baseline_pass_rate}%</span>
                              &nbsp;â†’&nbsp;Now: <span className="text-emerald-400 font-bold">
                                {improvementStatus.accuracy_trend?.at(-1)?.pass_rate ?? improvementStatus.baseline_pass_rate}%
                              </span>
                            </p>
                          )}
                          {improvementStatus?.last_run && (
                            <p className="text-[10px] font-mono text-slate-600 mt-1">
                              Last run: {new Date(improvementStatus.last_run).toLocaleString()}
                            </p>
                          )}
                        </div>
                        <div className="flex flex-col gap-2">
                          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1">Pass@1 Trend</p>
                          {improvementStatus?.accuracy_trend?.length > 1 ? (
                            <ResponsiveContainer width="100%" height={90}>
                              <LineChart data={improvementStatus.accuracy_trend} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                                <XAxis dataKey="date" tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#475569' }} tickLine={false} axisLine={false} />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#475569' }} tickLine={false} axisLine={false} />
                                <Tooltip contentStyle={{ background: '#101014', border: '1px solid #1f1f27', fontSize: 11, fontFamily: 'monospace', borderRadius: 6 }} formatter={(v) => [`${v}%`, 'Pass@1']} labelStyle={{ color: '#94a3b8' }} />
                                <Line type="monotone" dataKey="pass_rate" stroke="#10b981" strokeWidth={2} dot={{ r: 3, fill: '#10b981' }} />
                              </LineChart>
                            </ResponsiveContainer>
                          ) : (
                            <div className="flex items-center justify-center h-[90px] rounded-lg bg-[#141419] border border-[#202029]">
                              <p className="text-[10px] font-mono text-slate-600">No trend data yet</p>
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col gap-2">
                          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 mb-1">Round History <span className="normal-case font-normal text-slate-600">({improvementStatus?.total_rounds ?? 0} total)</span></p>
                          {improvementStatus?.recent_runs?.length > 0 ? (
                            <div className="space-y-1 max-h-[110px] overflow-y-auto no-scrollbar">
                              {[...(improvementStatus.recent_runs)].reverse().map((r, i) => (
                                <div key={i} className="flex items-center justify-between bg-[#141419] rounded px-2.5 py-1.5 gap-2">
                                  <span className="text-[9px] font-mono text-slate-500 shrink-0">{r.date} R{r.round}</span>
                                  <span className={`text-[10px] font-mono font-bold shrink-0 ${r.status === 'improved' ? 'text-emerald-400' : r.status === 'saturated' ? 'text-amber-400' : r.status === 'perfect' ? 'text-sky-400' : 'text-slate-500'}`}>
                                    {r.delta > 0 ? `+${r.delta}` : r.delta} queries
                                  </span>
                                  <span className="text-[9px] font-mono text-slate-400 shrink-0">{r.pass_rate > 0 ? `${r.pass_rate}%` : 'â€”'}</span>
                                  <span className="text-[9px] font-mono text-slate-600 shrink-0">{r.new_rules_added > 0 ? `${r.new_rules_added} rules` : ''}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="flex items-center justify-center h-[90px] rounded-lg bg-[#141419] border border-[#202029]">
                              <p className="text-[10px] font-mono text-slate-600 text-center px-2">No runs yet â€” click RUN NOW or waits daily 02:00 UTC</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </section>

                    {/* Target Repositories Matrix + Live Investigation Feed 2-column layout */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

                      {/* Repositories High-Density Table */}
                      <section className="lg:col-span-7 bg-[#101014] border border-[#1f1f27] rounded-xl p-4 flex flex-col shadow-lg">
                        <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                          <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                            <Database className="w-3.5 h-3.5 text-violet-400" />
                            Target Repositories Matrix
                          </h2>
                          <span className="text-[10px] font-mono font-bold text-slate-500 bg-[#16161c] px-2 py-0.5 rounded border border-white/5">
                            {dabDatabases.length} UNITS
                          </span>
                        </div>
    
                        <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1 no-scrollbar">
                          {dabDatabases.map((db) => {
                            const totalProcessed = db.results_count + db.empty_count + db.error_count;
                            const successPct = db.total_questions ? (db.results_count / db.total_questions) * 100 : 0;
                            const emptyPct = db.total_questions ? (db.empty_count / db.total_questions) * 100 : 0;
                            const errorPct = db.total_questions ? (db.error_count / db.total_questions) * 100 : 0;
    
                            return (
                              <div
                                key={db.name}
                                onClick={() => {
                                  setSelectedDb(db.name);
                                  setDabSearchQ('');
                                  setDabFilter('all');
                                  setCurrentView('database');
                                }}
                                className={`group p-3 rounded-lg bg-[#141419] border border-[#202029] hover:border-violet-500/40 hover:bg-[#181820] transition-all cursor-pointer flex items-center justify-between ${selectedDb === db.name ? 'border-violet-500 bg-violet-500/5 shadow-[0_0_15px_rgba(139,92,246,0.15)]' : ''
                                  }`}
                              >
                                <div className="flex items-center gap-3 w-full pr-4">
                                  <div className={`w-8 h-8 shrink-0 rounded-md flex items-center justify-center font-bold text-xs ${db.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400'
                                    }`}>
                                    {db.status === 'completed' ? <CheckCircle2 className="w-4 h-4" /> : <Database className="w-4 h-4" />}
                                  </div>
    
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between gap-2">
                                      <h3 className="font-mono font-bold text-xs truncate text-white group-hover:text-violet-400 transition-colors">
                                        {db.name}
                                      </h3>
                                      <div className="flex items-center gap-1.5 shrink-0">
                                        {db.tables_count > 0 && (
                                          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-purple-400 bg-purple-500/10 border border-purple-500/20 flex items-center gap-1">
                                            <Layers className="w-2.5 h-2.5 shrink-0" />
                                            {db.tables_count} Tbls
                                          </span>
                                        )}
                                        {db.tokens > 0 && (
                                          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1">
                                            <Zap className="w-2.5 h-2.5 shrink-0" />
                                            {db.tokens > 1000 ? `${(db.tokens / 1000).toFixed(1)}K` : db.tokens} Tokens
                                          </span>
                                        )}
                                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-violet-400 bg-violet-500/10 border border-violet-500/20">
                                          {db.total_questions} Qs
                                        </span>
                                      </div>
                                    </div>
    
                                    <div className="mt-2 w-full h-1 bg-[#0c0c10] rounded-full overflow-hidden flex">
                                      <div style={{ width: `${successPct}%` }} className="h-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] transition-all"></div>
                                      <div style={{ width: `${emptyPct}%` }} className="h-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)] transition-all"></div>
                                      <div style={{ width: `${errorPct}%` }} className="h-full bg-rose-500 shadow-[0_0_8px_rgba(239,68,68,0.5)] transition-all"></div>
                                    </div>
    
                                    <div className="flex items-center justify-between mt-1.5 text-[10px] font-mono text-slate-400">
                                      <span className="text-slate-500">Done: {totalProcessed}/{db.total_questions}</span>
                                      <div className="flex items-center gap-2 font-bold">
                                        <span className="text-emerald-400">{successPct.toFixed(0)}%</span>
                                        <span className="text-amber-400">{emptyPct.toFixed(0)}%</span>
                                        <span className="text-rose-500">{errorPct.toFixed(0)}%</span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </section>

                      {/* DAB Live Investigation Feed */}
                      <section className="lg:col-span-5 bg-[#101014] border border-[#1f1f27] rounded-xl p-4 flex flex-col shadow-lg">
                        <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1f1f27]">
                          <h2 className="text-xs font-mono font-bold flex items-center gap-2 uppercase tracking-wider text-slate-400">
                            <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                            Live Investigation Feed
                          </h2>
                          <span className="text-[10px] font-mono text-slate-500 bg-[#16161c] px-2 py-0.5 rounded border border-white/5">
                            {dabRecentRuns.length} RECENT
                          </span>
                        </div>
                        <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1 no-scrollbar">
                          {dabRecentRuns.length > 0 ? dabRecentRuns.map((run) => (
                            <div key={run.id} className="p-2.5 rounded-lg bg-[#141419] border border-[#202029] hover:border-violet-500/30 hover:bg-[#181820] transition-all flex items-center justify-between group">
                              <div className="flex items-center gap-2.5 min-w-0">
                                <div className={`p-1.5 rounded-md shrink-0 ${run.gold_status === 'gold_pass' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-500'}`}>
                                  {run.gold_status === 'gold_pass' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                                </div>
                                <div className="flex flex-col min-w-0 gap-1">
                                  <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                                    <span className="font-mono font-bold text-xs text-white truncate">{run.id}</span>
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-[#1e1e26] text-violet-400 border border-[#2a2a36] truncate">{run.db}</span>
                                    {run.latency > 0 && (
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1 shrink-0">
                                        <Zap className="w-2.5 h-2.5 shrink-0" />{run.latency}s
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                                      <Clock className="w-2.5 h-2.5" />
                                      {new Date(run.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                    </span>
                                    {run.reason && (
                                      <span className="text-[9px] font-mono text-slate-600 truncate max-w-[120px]" title={run.reason}>{run.reason}</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <div className="shrink-0">
                                {run.gold_status === 'gold_pass' ? (
                                  <span className="text-[9px] font-mono font-black text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">PASS</span>
                                ) : (
                                  <span className="text-[9px] font-mono font-black text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded">FAIL</span>
                                )}
                              </div>
                            </div>
                          )) : (
                            <div className="py-16 text-center text-slate-600 font-mono text-xs italic bg-[#141419] rounded-lg border border-[#202029]">
                              Waiting for DAB query evaluations...
                            </div>
                          )}
                        </div>
                      </section>

                    </div>{/* end 2-column grid */}
                  </>
                ) : (
                  <div className="bg-[#0e0e13] border border-[#1a1a22] rounded-xl p-5 font-mono text-xs text-slate-400">
                    Leaderboard and Submissions tab is under construction.
                  </div>
                )}
              </div>
            )
          )}

          {currentView === 'database' && (
            selectedProject === 'spider' ? (
              (() => {
                const currentDbObj = databases.find(d => d.name === selectedDb) || {};
                return (
                  /* Database Details View */
                  <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                    <header className="bg-[#101014] border border-[#1f1f27] p-4 rounded-xl flex items-center justify-between shadow-lg flex-wrap gap-3">
                      <div className="flex items-center gap-3 flex-wrap min-w-0">
                        <button
                          onClick={() => setCurrentView('dashboard')}
                          className="p-2 rounded-lg bg-[#181820] border border-[#262632] hover:bg-white/10 hover:text-white transition-all text-slate-400 font-mono text-xs flex items-center gap-1.5 font-bold shrink-0"
                        >
                          <ArrowLeft className="w-4 h-4" /> BACK
                        </button>
                        <div className="h-4 w-px bg-[#262632]" />
                        <Database className="w-5 h-5 text-blue-400 shrink-0" />
                        <h1 className="text-base font-mono font-black tracking-tight text-white flex items-center gap-2 flex-wrap min-w-0">
                          <span className="truncate">{selectedDb}</span>
                          {currentDbObj.tables_count > 0 && (
                            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded text-purple-400 bg-purple-500/10 border border-purple-500/20 flex items-center gap-1 ml-1 shrink-0">
                              <Layers className="w-3.5 h-3.5 shrink-0" />
                              {currentDbObj.tables_count} Tbls
                            </span>
                          )}
                          {currentDbObj.tokens > 0 && (
                            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1 shrink-0">
                              <Zap className="w-3.5 h-3.5 shrink-0" />
                              {currentDbObj.tokens > 1000 ? `${(currentDbObj.tokens / 1000).toFixed(1)}K` : currentDbObj.tokens} Tokens
                            </span>
                          )}
                        </h1>
                      </div>

                      <div className="flex items-center gap-2 font-mono text-xs shrink-0">
                        <span className="text-slate-500">Manifest Count:</span>
                        <span className="font-bold text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded">
                          {dbResults.length} INSTANCES
                        </span>
                      </div>
                    </header>

                    {loadingDetails ? (
                      <div className="flex flex-col items-center justify-center py-24 text-slate-500 gap-3 bg-[#101014] border border-[#1f1f27] rounded-xl font-mono">
                        <Activity className="w-6 h-6 animate-spin text-blue-400" />
                        <p className="text-xs font-bold">Loading execution probes...</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {dbResults.length > 0 ? dbResults.map(res => {
                          let statusColor = 'border-slate-800 text-slate-500';
                          if (res.status === 'success') statusColor = 'border-emerald-500 text-emerald-400';
                          else if (res.status === 'empty') statusColor = 'border-amber-500 text-amber-400';
                          else if (res.status === 'error') statusColor = 'border-rose-500 text-rose-500';

                          return (
                            <div
                              key={res.id}
                              className={`bg-[#101014] border border-[#1f1f27] rounded-xl p-3.5 flex flex-col justify-between group transition-all hover:border-blue-500/40 hover:bg-[#121217] shadow-md relative overflow-hidden ${runningInstances[res.id] ? 'border-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.2)]' : ''
                                }`}
                            >
                              <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#1b1b22]">
                                <div className="flex items-center gap-1.5 flex-wrap min-w-0 pr-1">
                                  {getStatusIcon(res.status)}
                                  <span className="font-mono font-black text-xs text-white truncate tracking-tight">{res.id}</span>
                                  {getComplexityBadge(res.complexity, res.complexity_type, res.complexity_score)}
                                  {res.latency > 0 ? (
                                    <>
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1 shrink-0" title="Execution Time (Latency)">
                                        <Zap className="w-2.5 h-2.5 shrink-0 text-amber-400" />
                                        {res.latency}s
                                      </span>
                                      {res.cost > 0 && (
                                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-violet-400 bg-violet-500/10 border border-violet-500/20 flex items-center gap-1 shrink-0" title={`Cost Incurred: ${res.total_tokens?.toLocaleString() || 0} tokens`}>
                                          <DollarSign className="w-2.5 h-2.5 shrink-0 text-violet-400" />
                                          ${res.cost.toFixed(4)}
                                        </span>
                                      )}
                                    </>
                                  ) : (
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-slate-400 bg-slate-500/10 border border-slate-500/20 flex items-center gap-1 shrink-0" title="Execution Time (Latency)">
                                      <Clock className="w-2.5 h-2.5 shrink-0 text-slate-400" />
                                      {res.status === 'running' ? 'Executing...' : 'Unrun'}
                                    </span>
                                  )}
                                  {res.status === 'success' || res.status === 'empty' ? (
                                    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0 ${res.rows > 0 ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'
                                      }`} title="Result Set Row Count">
                                      <Database className="w-2.5 h-2.5 shrink-0" />
                                      {res.rows} {res.rows === 1 ? 'Row' : 'Rows'}
                                    </span>
                                  ) : res.status === 'error' ? (
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-rose-400 bg-rose-500/10 border border-rose-500/20 flex items-center gap-1 shrink-0" title="Execution Failed">
                                      <AlertTriangle className="w-2.5 h-2.5 shrink-0 text-rose-400" />
                                      Failed
                                    </span>
                                  ) : null}
                                  {res.corrections > 0 && (
                                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 flex items-center gap-1 shrink-0" title="Self-Correction Rounds Triggered">
                                      <RefreshCw className={`w-2.5 h-2.5 shrink-0 text-cyan-400 ${res.status === 'running' ? 'animate-spin' : ''}`} />
                                      {res.corrections} {res.corrections === 1 ? 'Fix' : 'Fixes'}
                                    </span>
                                  )}
                                </div>

                                <div className="flex items-center gap-1.5 shrink-0">
                                  <button
                                    onClick={() => { setActiveLiveInstance(res.id); setShowLiveDrawer(true); }}
                                    className="p-1.5 rounded bg-[#181820] border border-[#262632] hover:bg-blue-600 hover:text-white transition-all text-slate-400"
                                    title="Live Execution Audit Drawer"
                                  >
                                    <Activity className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
                                  </button>
                                  <button
                                    className={`p-1.5 rounded bg-[#181820] border border-[#262632] hover:bg-emerald-600 hover:text-white transition-all ${runningInstances[res.id] ? 'animate-spin bg-blue-500 text-white' : 'text-slate-300'
                                      }`}
                                    onClick={() => handleRunInstance(res.id)}
                                    disabled={runningInstances[res.id]}
                                    title="Execute Single Instance"
                                  >
                                    {runningInstances[res.id] ? <Activity className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                                  </button>
                                </div>
                              </div>

                              <div className="bg-[#141419] p-2.5 rounded-lg border border-[#1c1c24] mb-3 flex-1">
                                <p className="text-[11px] text-slate-300 leading-normal font-sans line-clamp-3 hover:line-clamp-none transition-all">
                                  {res.question || <span className="italic text-slate-600 font-mono">Question data unavailable.</span>}
                                </p>
                              </div>

                              <div className="flex items-center justify-between pt-2 border-t border-[#1b1b22] font-mono text-[10px]">
                                <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider">
                                  <span className="text-slate-500">VERDICT:</span>
                                  <span className={statusColor.split(' ')[1]}>{res.status.toUpperCase()}</span>
                                  {res.gold_status === 'gold_pass' && (
                                    <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.2 rounded font-black ml-1">
                                      GOLD âœ“
                                    </span>
                                  )}
                                  {res.gold_status === 'gold_fail' && (
                                    <span className="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.2 rounded font-black ml-1">
                                      GOLD âœ—
                                    </span>
                                  )}
                                </div>

                                {res.status !== 'pending' && (
                                  <div className="flex items-center gap-1.5 shrink-0">
                                    <button
                                      className="font-bold flex items-center gap-1 text-indigo-400 hover:text-white bg-indigo-500/10 hover:bg-indigo-500 border border-indigo-500/20 hover:border-indigo-500 px-2 py-1 rounded transition-all"
                                      onClick={() => handleDiagnose(selectedDb, res.id)}
                                    >
                                      <ShieldAlert className="w-3 h-3 shrink-0" />
                                      DIAGNOSE
                                    </button>
                                    <button
                                      className="font-bold flex items-center gap-1 text-blue-400 hover:text-white bg-blue-500/10 hover:bg-blue-500 border border-blue-500/20 hover:border-blue-500 px-2 py-1 rounded transition-all"
                                      onClick={() => fetchInstanceDetails(res.id)}
                                    >
                                      <TerminalSquare className="w-3 h-3 shrink-0" />
                                      ARTIFACTS
                                    </button>
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        }) : (
                          <div className="col-span-full py-20 bg-[#101014] border border-[#1f1f27] rounded-xl text-center flex flex-col items-center justify-center font-mono text-xs text-slate-500 gap-2">
                            <Database className="w-8 h-8 text-slate-700 opacity-50" />
                            No instances mapped for this repository in configuration.
                          </div>
                        )}
                      </div>
                    )}
                  </motion.div>
                );
              })()
            ) : (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                <header className="bg-[#101014] border border-[#1f1f27] p-4 rounded-xl flex items-center justify-between shadow-lg flex-wrap gap-3">
                  <div className="flex items-center gap-3 flex-wrap min-w-0">
                    <button
                      onClick={() => setCurrentView('dashboard')}
                      className="p-2 rounded-lg bg-[#181820] border border-[#262632] hover:bg-white/10 hover:text-white transition-all text-slate-400 font-mono text-xs flex items-center gap-1.5 font-bold shrink-0"
                    >
                      <ArrowLeft className="w-4 h-4" /> BACK
                    </button>
                    <div className="h-4 w-px bg-[#262632]" />
                    <Database className="w-5 h-5 text-violet-400 shrink-0" />
                    <h1 className="text-base font-mono font-black tracking-tight text-white flex items-center gap-2 flex-wrap min-w-0">
                      <span>DataAgentBench Queries: {selectedDb || 'All Datasets'}</span>
                    </h1>
                  </div>

                  <div className="flex items-center gap-2 font-mono text-xs shrink-0">
                    <span className="text-slate-500">Query Count:</span>
                    <span className="font-bold text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded">
                      {dabQueries.length} INSTANCES
                    </span>
                  </div>
                </header>

                {/* Filter and Search Bar for DAB */}
                <div className="flex items-center gap-3 flex-wrap bg-[#101014] border border-[#1f1f27] p-4 rounded-xl shadow-lg">
                  <div className="relative flex-1 min-w-[200px]">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                    <input type="text" placeholder="Search queries..."
                      value={dabSearchQ} onChange={e => setDabSearchQ(e.target.value)}
                      className="bg-[#121216] border border-[#22222a] rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-violet-500/50 transition-all w-full font-mono"
                    />
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {['all', 'pending', 'passed', 'failed', 'running'].map(f => (
                      <button key={f} onClick={() => setDabFilter(f)}
                        className={`px-3 py-1.5 rounded-md font-mono text-[10px] font-bold uppercase tracking-wider transition-all border ${dabFilter === f ? 'bg-violet-500/20 text-violet-300 border-violet-500/40' : 'bg-transparent text-slate-500 border-transparent hover:text-slate-300'}`}
                      >{f}</button>
                    ))}
                  </div>
                </div>

                {/* Query Table + Detail Panel */}
                <div className="flex gap-4 min-h-[500px]">
                  {/* Query Table */}
                  <div className="flex-1 bg-[#0e0e13] border border-[#1a1a22] rounded-xl overflow-hidden flex flex-col">
                    <div className="px-5 py-3 border-b border-[#1a1a22] flex items-center justify-between">
                      <h2 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <Database className="w-4 h-4 text-violet-400" />
                        Query Index
                        <span className="ml-1 bg-violet-500/10 text-violet-400 border border-violet-500/20 px-1.5 py-0.5 rounded text-[10px]">
                          {dabQueries.filter(q => {
                            const matchDb = !selectedDb || q.dataset === selectedDb;
                            const matchFilter = dabFilter === 'all' || q.status === dabFilter;
                            const matchSearch = !dabSearchQ || q.question?.toLowerCase().includes(dabSearchQ.toLowerCase());
                            return matchDb && matchFilter && matchSearch;
                          }).length}
                        </span>
                      </h2>
                    </div>
                    <div className="flex-1 overflow-y-auto no-scrollbar divide-y divide-[#141419] max-h-[600px]">
                      {dabLoading ? (
                        <div className="py-16 text-center text-slate-600 font-mono text-xs animate-pulse">Loading queries...</div>
                      ) : dabQueries.length === 0 ? (
                        <div className="py-16 text-center text-slate-600 font-mono text-xs">
                          No queries loaded. Click Refresh on Dashboard or check the repo path.
                        </div>
                      ) : (
                        dabQueries.filter(q => {
                          const matchDb = !selectedDb || q.dataset === selectedDb;
                          const matchFilter = dabFilter === 'all' || q.status === dabFilter;
                          const matchSearch = !dabSearchQ || q.question?.toLowerCase().includes(dabSearchQ.toLowerCase());
                          return matchDb && matchFilter && matchSearch;
                        }).map(q => {
                          const isSelected = dabSelectedQuery?.instance_id === q.instance_id;
                          const statusColor = q.status === 'passed' ? 'text-emerald-400' : q.status === 'failed' ? 'text-rose-400' : q.status === 'running' ? 'text-blue-400' : 'text-slate-500';
                          const statusIcon = q.status === 'passed' ? 'âœ…' : q.status === 'failed' ? 'âœ—' : q.status === 'running' ? 'âŸ³' : 'â—‹';
                          return (
                            <div key={q.instance_id}
                              onClick={() => { setDabSelectedQuery(q); fetchDabDetail(q.dataset, q.query_id); }}
                              className={`px-4 py-3 cursor-pointer transition-all hover:bg-white/[0.02] ${isSelected ? 'bg-violet-500/5 border-l-2 border-violet-500' : 'border-l-2 border-transparent'}`}
                            >
                              <div className="flex items-start gap-3">
                                <span className={`text-base mt-0.5 ${statusColor} shrink-0`}>{statusIcon}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="text-[10px] font-mono font-black text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded">{q.dataset}</span>
                                    <span className="text-[10px] font-mono text-slate-500">Q{q.query_id}</span>
                                    {q.needs_docker && <span className="text-[9px] bg-blue-500/10 text-blue-400 px-1 rounded font-mono">ðŸ³</span>}
                                    {(q.db_types || []).map(t => (
                                      <span key={t} className="text-[9px] bg-slate-800 text-slate-400 px-1 rounded font-mono">{t}</span>
                                    ))}
                                  </div>
                                  <p className="text-xs text-slate-300 leading-snug line-clamp-2 font-sans">
                                    {q.question}
                                  </p>
                                </div>
                                <button
                                  onClick={e => { e.stopPropagation(); runDabSingle(q.dataset, q.query_id); }}
                                  className="shrink-0 p-1.5 rounded-md bg-violet-500/10 hover:bg-violet-500 text-violet-400 hover:text-white transition-all"
                                  title="Run this query"
                                >
                                  <Play className="w-3 h-3 fill-current" />
                                </button>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>

                  {/* Query Detail Panel */}
                  {dabSelectedQuery && (
                    <div className="w-[420px] shrink-0 bg-[#0e0e13] border border-[#1a1a22] rounded-xl overflow-hidden flex flex-col max-h-[660px]">
                      <div className="px-5 py-3 border-b border-[#1a1a22] flex items-center justify-between">
                        <div>
                          <span className="text-[10px] font-mono font-bold text-violet-400">{dabSelectedQuery.dataset} / Q{dabSelectedQuery.query_id}</span>
                          <div className={`text-[10px] font-mono mt-0.5 ${dabSelectedQuery.status === 'passed' ? 'text-emerald-400' : dabSelectedQuery.status === 'failed' ? 'text-rose-400' : 'text-slate-500'}`}>
                            {dabSelectedQuery.status?.toUpperCase() || 'PENDING'}
                          </div>
                        </div>
                        <button onClick={() => runDabSingle(dabSelectedQuery.dataset, dabSelectedQuery.query_id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg font-mono text-xs font-bold transition-all shadow-lg shadow-violet-500/20"
                        >
                          <Play className="w-3 h-3 fill-current" /> Run
                        </button>
                      </div>
                      <div className="flex-1 overflow-y-auto no-scrollbar p-4 space-y-4">
                        {/* Question */}
                        <div>
                          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5">Question</div>
                          <p className="text-sm text-slate-200 leading-relaxed font-sans bg-[#12121a] p-3 rounded-lg border border-[#1e1e28]">
                            {dabSelectedQuery.question}
                          </p>
                        </div>
                        {/* Ground Truth */}
                        <div>
                          <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5">Ground Truth</div>
                          <div className="font-mono text-sm text-amber-400 bg-amber-500/10 border border-amber-500/20 p-2 rounded-lg">
                            {dabSelectedQuery.ground_truth || 'â€”'}
                          </div>
                        </div>
                        {/* Detail panel content */}
                        {dabDetailLoading ? (
                          <div className="py-8 text-center text-slate-600 font-mono text-xs animate-pulse">Loading result details...</div>
                        ) : dabDetail ? (
                          <>
                            {/* Agent Answer */}
                            {dabDetail.agent_answer && (
                              <div>
                                <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5">Agent Answer</div>
                                <div className={`font-mono text-sm p-3 rounded-lg border ${dabDetail.passed ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300' : 'bg-rose-500/10 border-rose-500/20 text-rose-300'}`}>
                                  {dabDetail.agent_answer}
                                </div>
                              </div>
                            )}
                            {/* Validation Result */}
                            {dabDetail.reason && (
                              <div>
                                <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5">Validation</div>
                                <div className="text-xs font-mono text-slate-400 bg-[#121218] border border-[#1e1e28] p-2.5 rounded-lg leading-relaxed">
                                  {dabDetail.reason}
                                </div>
                              </div>
                            )}
                            {/* SQL */}
                            {dabDetail.sql_content && (
                              <div>
                                <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5">Generated SQL</div>
                                <pre className="text-[10px] font-mono text-cyan-300 bg-[#0d0d16] border border-[#1a1a28] rounded-lg p-3 overflow-x-auto leading-relaxed max-h-48 whitespace-pre-wrap">
                                  {dabDetail.sql_content}
                                </pre>
                              </div>
                            )}
                            {/* CSV Result */}
                            {dabDetail.csv_headers?.length > 0 && (
                              <div>
                                <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1.5">SQL Result</div>
                                <div className="overflow-x-auto rounded-lg border border-[#1e1e28]">
                                  <table className="text-[10px] font-mono w-full">
                                    <thead className="bg-[#121218]">
                                      <tr>{dabDetail.csv_headers.map(h => <th key={h} className="px-3 py-2 text-left text-slate-400 font-bold border-b border-[#1e1e28]">{h}</th>)}</tr>
                                    </thead>
                                    <tbody>
                                      {dabDetail.csv_data?.slice(0, 10).map((row, i) => (
                                        <tr key={i} className="border-b border-[#14141c] hover:bg-white/[0.02]">
                                          {dabDetail.csv_headers.map(h => <td key={h} className="px-3 py-1.5 text-slate-300">{String(row[h] ?? '')}</td>)}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="py-8 text-center text-slate-600 font-mono text-xs">
                            Click a query to view details, then run it to see results.
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}


          {/* ULTRA PREMIUM MODAL FOR PROBE ARTIFACTS */}
          <AnimatePresence>
            {selectedDetails && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 lg:p-8 font-mono"
              >
                <motion.div
                  initial={{ scale: 0.96, y: 15 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 15 }}
                  className="bg-[#0e0e12] border border-[#22222a] w-full max-w-5xl h-full max-h-[85vh] rounded-2xl flex flex-col overflow-hidden shadow-2xl"
                >
                  <header className="flex items-center justify-between p-4 px-6 border-b border-[#22222a] bg-[#121217]">
                    <div className="flex items-center gap-3">
                      <TerminalSquare className="w-5 h-5 text-blue-400" />
                      <h2 className="font-bold text-sm text-white flex items-center gap-2">
                        PROBE ARTIFACTS: <span className="text-blue-400 font-extrabold">{selectedDetails.id}</span>
                      </h2>
                      {selectedDetails.executed_at && (
                        <span className="text-[10px] text-slate-500 border border-white/5 bg-[#181820] px-2 py-0.5 rounded font-bold">
                          {new Date(selectedDetails.executed_at).toLocaleString()}
                        </span>
                      )}
                      {selectedDetails.total_tokens > 0 && (
                        <span className="text-[10px] text-slate-400 border border-white/5 bg-[#181820] px-2 py-0.5 rounded font-bold" title="Total Tokens Used">
                          Tokens: <span className="text-blue-400">{selectedDetails.total_tokens.toLocaleString()}</span>
                        </span>
                      )}
                      {selectedDetails.cost > 0 && (
                        <span className="text-[10px] text-violet-400 border border-violet-500/20 bg-violet-500/5 px-2 py-0.5 rounded font-bold" title="Total Bedrock Cost">
                          Cost: <span className="text-violet-300">${selectedDetails.cost.toFixed(4)}</span>
                        </span>
                      )}
                      {selectedDetails.complexity_type && (
                        getComplexityBadge(selectedDetails.complexity, selectedDetails.complexity_type, selectedDetails.complexity_score)
                      )}
                    </div>
                    <button
                      onClick={() => setSelectedDetails(null)}
                      className="text-slate-500 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </header>

                  <div className="flex border-b border-[#22222a] bg-[#14141a] text-xs font-bold overflow-x-auto no-scrollbar">
                    {[
                      { id: 'sql', label: 'Generated SQL', icon: Terminal },
                      { id: 'logs', label: 'Execution Logs', icon: Activity },
                      { id: 'csv', label: 'Result Data', icon: FileSpreadsheet },
                      { id: 'pipeline', label: 'Pipeline Trace', icon: Layers }
                    ].map(t => (
                      <button
                        key={t.id}
                        onClick={() => setDetailsTab(t.id)}
                        className={`flex items-center gap-2 px-6 py-3 transition-all border-b-2 uppercase tracking-wider ${detailsTab === t.id ? 'border-blue-500 text-blue-400 bg-blue-500/5' : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
                          }`}
                      >
                        <t.icon className="w-3.5 h-3.5" />
                        {t.label}
                      </button>
                    ))}
                  </div>

                  <div className="flex-1 overflow-auto p-6 bg-[#09090c] relative no-scrollbar font-mono text-xs">
                    {detailsTab === 'sql' && (
                      <div className="relative group h-full">
                        <button
                          onClick={() => copyToClipboard(selectedDetails.sql_content, 'sql')}
                          className="absolute top-3 right-3 p-2 bg-[#1c1c24] hover:bg-[#262632] text-slate-200 rounded-lg transition-all border border-[#2e2e3c] flex items-center gap-1.5 font-bold text-[10px] uppercase shadow-lg"
                        >
                          {copiedType === 'sql' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-blue-400" />}
                          {copiedType === 'sql' ? 'COPIED' : 'COPY'}
                        </button>
                        <pre className="text-blue-300 bg-[#0c0c10] p-5 rounded-xl border border-[#1f1f27] overflow-auto h-full whitespace-pre-wrap leading-relaxed shadow-inner">
                          {selectedDetails.sql_content}
                        </pre>
                      </div>
                    )}

                    {detailsTab === 'logs' && (
                      <div className="relative group h-full">
                        <button
                          onClick={() => copyToClipboard(selectedDetails.log_content, 'logs')}
                          className="absolute top-3 right-3 p-2 bg-[#1c1c24] hover:bg-[#262632] text-slate-200 rounded-lg transition-all border border-[#2e2e3c] flex items-center gap-1.5 font-bold text-[10px] uppercase shadow-lg"
                        >
                          {copiedType === 'logs' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-blue-400" />}
                          {copiedType === 'logs' ? 'COPIED' : 'COPY'}
                        </button>
                        <pre className="text-slate-300 bg-[#0c0c10] p-5 rounded-xl border border-[#1f1f27] overflow-auto h-full whitespace-pre-wrap leading-relaxed shadow-inner text-[11px]">
                          {selectedDetails.log_content}
                        </pre>
                      </div>
                    )}

                    {detailsTab === 'csv' && (
                      <div className="bg-[#0c0c10] rounded-xl border border-[#1f1f27] overflow-x-auto shadow-inner h-full">
                        {selectedDetails.csv_data && selectedDetails.csv_data.length > 0 ? (
                          <table className="w-full text-left border-collapse font-mono text-xs">
                            <thead>
                              <tr className="border-b border-[#22222a] bg-[#14141a]">
                                {selectedDetails.csv_headers.map((h, i) => (
                                  <th key={i} className="p-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider whitespace-nowrap sticky top-0 bg-[#14141a]">
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {selectedDetails.csv_data.map((row, i) => (
                                <tr key={i} className="border-b border-[#1b1b22] hover:bg-white/[0.02] transition-colors">
                                  {selectedDetails.csv_headers.map((h, j) => (
                                    <td key={j} className="p-3 text-slate-300 whitespace-nowrap">
                                      {row[h] !== null ? String(row[h]) : <span className="italic text-slate-600">NULL</span>}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <div className="h-full flex flex-col items-center justify-center gap-2 text-slate-600 italic">
                            <Activity className="w-8 h-8 opacity-40" />
                            No tabular CSV records returned by execution.
                          </div>
                        )}
                      </div>
                    )}

                    {detailsTab === 'pipeline' && (
                      <div className="h-full overflow-y-auto no-scrollbar -m-6 bg-[#07070a]">
                        <PipelinePulse instanceId={selectedDetails?.id} />
                      </div>
                    )}
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ULTRA PREMIUM METRIC BREAKDOWN MODAL */}
          <AnimatePresence>
            {showMetricModal && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 lg:p-8 font-mono"
              >
                <motion.div
                  initial={{ scale: 0.96, y: 15 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 15 }}
                  className="bg-[#0e0e12] border border-[#22222a] w-full max-w-5xl h-full max-h-[85vh] rounded-2xl flex flex-col overflow-hidden shadow-2xl"
                >
                  <header className="flex items-center justify-between p-4 px-6 border-b border-[#22222a] bg-[#121217]">
                    <div className="flex items-center gap-3">
                      <Database className="w-5 h-5 text-blue-400" />
                      <h2 className="font-bold text-sm text-white uppercase tracking-wider flex items-center gap-2">
                        METRIC BREAKDOWN: <span className="text-blue-400 font-extrabold">{activeMetricFilter.toUpperCase()}</span>
                      </h2>
                      <span className="text-[10px] text-slate-500 border border-white/5 bg-[#181820] px-2 py-0.5 rounded font-bold">
                        {filteredMetricInstances.length} INSTANCES
                      </span>
                    </div>
                    <button
                      onClick={() => setShowMetricModal(false)}
                      className="text-slate-500 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </header>

                  <div className="p-4 bg-[#14141a] border-b border-[#22222a] flex flex-wrap items-center justify-between gap-4">
                    <div className="flex bg-[#1a1a24] p-1 rounded-lg border border-[#2c2c3e] text-xs">
                      {[
                        { id: 'total', label: 'All Runs' },
                        { id: 'succeeded', label: 'Succeeded (CSV)' },
                        { id: 'errored', label: 'Errored' },
                        { id: 'gold', label: 'Gold Verified' }
                      ].map(t => (
                        <button
                          key={t.id}
                          onClick={() => setActiveMetricFilter(t.id)}
                          className={`px-3 py-1.5 rounded-md font-bold transition-all uppercase tracking-wider text-[11px] ${activeMetricFilter === t.id ? 'bg-blue-600 text-white shadow' : 'text-slate-400 hover:text-slate-200'
                            }`}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>

                    <div className="relative w-64">
                      <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-500" />
                      <input
                        type="text"
                        placeholder="Search ID or DB..."
                        value={metricSearchQuery}
                        onChange={(e) => setMetricSearchQuery(e.target.value)}
                        className="w-full pl-9 pr-4 py-1.5 bg-[#0e0e14] border border-[#282838] rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
                      />
                    </div>
                  </div>

                  <div className="flex-1 overflow-auto p-6 bg-[#09090c] relative no-scrollbar">
                    {loadingMetricInstances ? (
                      <div className="h-full flex flex-col items-center justify-center gap-3 text-blue-400 animate-pulse font-mono">
                        <Activity className="w-8 h-8 animate-spin" />
                        <p className="text-xs font-bold">Aggregating benchmark forensic execution logs...</p>
                      </div>
                    ) : filteredMetricInstances.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredMetricInstances.map(inst => {
                          const instDbObj = databases.find(d => d.name === inst.db) || {};
                          return (
                            <div
                              key={inst.id}
                              onClick={() => fetchInstanceDetailsFromModal(inst.db, inst.id)}
                              className="bg-[#121217] border border-[#22222c] hover:border-blue-500/50 p-4 rounded-xl cursor-pointer transition-all hover:scale-[1.02] shadow-lg group relative overflow-hidden flex flex-col justify-between font-mono"
                            >
                              <div className="absolute -right-6 -bottom-6 w-20 h-20 bg-blue-500/5 rounded-full blur-2xl group-hover:bg-blue-500/10 transition-colors" />

                              <div>
                                <div className="flex flex-col gap-1.5 mb-3">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-extrabold text-sm text-white group-hover:text-blue-400 transition-colors truncate">
                                      {inst.id}
                                    </span>
                                    <span className="text-[10px] px-2 py-0.5 bg-[#1a1a24] text-blue-400 rounded border border-blue-500/20 truncate font-bold">
                                      {inst.db}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                                    {inst.latency > 0 && (
                                      <>
                                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-amber-400 bg-amber-500/10 border border-amber-500/20 flex items-center gap-1 shrink-0" title="Execution Time (Latency)">
                                          <Zap className="w-2.5 h-2.5 shrink-0 text-amber-400" />
                                          {inst.latency}s
                                        </span>
                                        {inst.cost > 0 && (
                                          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-violet-400 bg-violet-500/10 border border-violet-500/20 flex items-center gap-1 shrink-0" title={`Cost Incurred: ${inst.total_tokens?.toLocaleString() || 0} tokens`}>
                                            <DollarSign className="w-2.5 h-2.5 shrink-0 text-violet-400" />
                                            ${inst.cost.toFixed(4)}
                                          </span>
                                        )}
                                      </>
                                    )}
                                    {(inst.status === 'success' || inst.status === 'empty') && (
                                      <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded flex items-center gap-1 shrink-0 ${inst.rows > 0 ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20' : 'text-amber-400 bg-amber-500/10 border border-amber-500/20'
                                        }`} title="Result Set Row Count">
                                        <Database className="w-2.5 h-2.5 shrink-0" />
                                        {inst.rows} {inst.rows === 1 ? 'Row' : 'Rows'}
                                      </span>
                                    )}
                                    {inst.corrections > 0 && (
                                      <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 flex items-center gap-1 shrink-0" title="Self-Correction Rounds Triggered">
                                        <RefreshCw className="w-2.5 h-2.5 shrink-0 text-cyan-400" />
                                        {inst.corrections} {inst.corrections === 1 ? 'Fix' : 'Fixes'}
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <div className="flex items-center justify-between text-[11px] text-slate-400 mt-3 pt-2 border-t border-[#1c1c24]">
                                  <div className="flex items-center gap-1.5 font-bold">
                                    {getStatusIcon(inst.status)}
                                    <span className="uppercase tracking-tight text-[10px]">{inst.status}</span>
                                  </div>
                                  <div className="flex items-center gap-1 text-slate-500">
                                    <Clock className="w-3 h-3 text-cyan-400" />
                                    <span>{inst.latency ? `${inst.latency}s` : 'N/A'}</span>
                                  </div>
                                </div>
                              </div>

                              {inst.gold_status === 'gold_pass' && (
                                <div className="mt-2.5 flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-2 py-1 rounded border border-amber-500/20 w-fit font-bold">
                                  <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
                                  <span>GOLD PARITY MATCH</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center gap-2 text-slate-600 italic font-mono text-xs">
                        <Database className="w-8 h-8 opacity-40" />
                        No instance records found matching criteria.
                      </div>
                    )}
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* GLOBAL RUN CONFIGURATION DIALOG */}
          <AnimatePresence>
            {showGlobalRunModal && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 font-mono"
              >
                <motion.div
                  initial={{ scale: 0.95, y: 20 }}
                  animate={{ scale: 1, y: 0 }}
                  exit={{ scale: 0.95, y: 20 }}
                  className="bg-[#121217] border border-[#262632] w-full max-w-xl max-h-[90vh] rounded-2xl shadow-2xl overflow-hidden flex flex-col relative"
                >
                  <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-blue-500 to-purple-500" />

                  <header className="p-6 pb-4 border-b border-[#1f1f27] flex items-center justify-between bg-[#16161e] shrink-0">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.2)] shrink-0">
                        <Play className="w-5 h-5 fill-current" />
                      </div>
                      <div>
                        <h2 className="text-sm font-extrabold text-white uppercase tracking-wider flex items-center gap-2">
                          Global Batch Execution Engine
                        </h2>
                        <p className="text-[11px] text-slate-400 mt-0.5 font-sans leading-snug">
                          Configure parallel threads, LLM stochasticity, and self-correction audit scope.
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowGlobalRunModal(false)}
                      className="text-slate-500 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors shrink-0"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </header>

                  <div className="p-6 space-y-6 bg-[#0c0c10] flex-1 overflow-y-auto">
                    {/* Execution Scope */}
                    <div>
                      <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2 mb-3">
                        <Filter className="w-3.5 h-3.5 text-blue-400" />
                        Execution Target Scope
                      </label>
                      <div className="grid grid-cols-1 gap-2.5 font-sans text-xs">
                        {[
                          { id: 'missing_only', title: 'Missing & Pending Runs Only', desc: 'Skips instances that already have successful non-empty CSV outputs.' },
                          { id: 'failed_only', title: 'Failed & Empty Runs Only', desc: 'Surgically targets only instances that failed compilation or returned 0 rows.' },
                          { id: 'all', title: 'Complete Benchmark Re-run', desc: 'Forces execution across all instances, overwriting existing artifacts.' }
                        ].map(s => (
                          <div
                            key={s.id}
                            onClick={() => setGlobalRunConfig({ ...globalRunConfig, scope: s.id })}
                            className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-start gap-3.5 ${globalRunConfig.scope === s.id
                              ? 'bg-blue-600/10 border-blue-500 text-white shadow-[0_0_20px_rgba(59,130,246,0.15)]'
                              : 'bg-[#141419] border-[#22222a] text-slate-400 hover:border-slate-700 hover:bg-[#16161e]'
                              }`}
                          >
                            <div className={`w-4 h-4 rounded-full border mt-0.5 flex items-center justify-center shrink-0 ${globalRunConfig.scope === s.id ? 'border-blue-400 bg-blue-500 text-white' : 'border-slate-600 bg-transparent'
                              }`}>
                              {globalRunConfig.scope === s.id && <span className="w-1.5 h-1.5 rounded-full bg-white" />}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="font-bold font-mono text-white text-xs tracking-tight">{s.title}</div>
                              <div className="text-[11px] text-slate-400 mt-0.5 leading-snug">{s.desc}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <hr className="border-[#1c1c24]" />

                    {/* Sliders Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Immersive Neural Screensaver Toggle */}
                      <div
                        onClick={() => setGlobalRunConfig({ ...globalRunConfig, screensaver: !globalRunConfig.screensaver })}
                        className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between font-mono sm:col-span-2 ${globalRunConfig.screensaver
                          ? 'bg-gradient-to-r from-emerald-500/10 via-blue-500/10 to-purple-500/10 border-blue-500 text-white shadow-[0_0_25px_rgba(59,130,246,0.2)]'
                          : 'bg-[#141419] border-[#22222a] text-slate-400 hover:border-slate-700 hover:bg-[#16161e]'
                          }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${globalRunConfig.screensaver ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30 animate-pulse' : 'bg-[#1c1c24] text-slate-500'
                            }`}>
                            <Sparkles className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="font-bold text-white text-xs flex items-center gap-2 tracking-tight">
                              <span>Immersive Neural Matrix Screensaver</span>
                              {globalRunConfig.screensaver && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                  ACTIVE
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-400 mt-0.5 font-sans leading-snug">
                              Replaces concurrency with an active holographic dataflow visualizer during batch runs.
                            </div>
                          </div>
                        </div>
                        <div className={`w-10 h-6 rounded-full p-1 transition-colors ${globalRunConfig.screensaver ? 'bg-blue-500' : 'bg-[#262632]'
                          }`}>
                          <div className={`w-4 h-4 rounded-full bg-white transition-transform ${globalRunConfig.screensaver ? 'translate-x-4 shadow' : 'translate-x-0'
                            }`} />
                        </div>
                      </div>

                      {/* LLM Temperature */}
                      <div>
                        <div className="flex justify-between items-center mb-2 font-mono">
                          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                            <Sliders className="w-3.5 h-3.5 text-amber-400" />
                            LLM Temperature
                          </label>
                          <span className="text-amber-400 font-extrabold text-xs px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 rounded">
                            {globalRunConfig.temperature.toFixed(2)}
                          </span>
                        </div>
                        <input
                          type="range" min="0.0" max="1.0" step="0.05"
                          value={globalRunConfig.temperature}
                          onChange={(e) => setGlobalRunConfig({ ...globalRunConfig, temperature: parseFloat(e.target.value) })}
                          className="w-full h-1.5 bg-[#20202a] rounded-full appearance-none accent-amber-500 cursor-pointer mb-1.5"
                        />
                        <span className="text-[10px] text-slate-500 block leading-tight font-sans">0.0 (Strictly Deterministic) to 1.0 (Creative).</span>
                      </div>

                      {/* Max Self-Correction Retries */}
                      <div>
                        <div className="flex justify-between items-center mb-2 font-mono">
                          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                            <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
                            Self-Correction Retries
                          </label>
                          <span className="text-cyan-400 font-extrabold text-xs px-2 py-0.5 bg-cyan-500/10 border border-cyan-500/20 rounded">
                            {globalRunConfig.maxRetries} LOOPS
                          </span>
                        </div>
                        <input
                          type="range" min="1" max="10" step="1"
                          value={globalRunConfig.maxRetries}
                          onChange={(e) => setGlobalRunConfig({ ...globalRunConfig, maxRetries: parseInt(e.target.value) })}
                          className="w-full h-1.5 bg-[#20202a] rounded-full appearance-none accent-cyan-500 cursor-pointer mb-1.5"
                        />
                        <span className="text-[10px] text-slate-500 block leading-tight font-sans">Iterative repair cycles on SQL compilation failure.</span>
                      </div>

                      {/* Reasoning Dialect */}
                      <div>
                        <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 mb-2 font-mono">
                          <Database className="w-3.5 h-3.5 text-purple-400" />
                          Database Dialect Protocol
                        </label>
                        <select
                          value={globalRunConfig.dialect}
                          onChange={(e) => setGlobalRunConfig({ ...globalRunConfig, dialect: e.target.value })}
                          className="w-full bg-[#16161e] border border-[#2a2a36] rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-purple-500/50 shadow-inner"
                        >
                          <option value="snowflake">Snowflake Analytical Engine</option>
                          <option value="sqlite">SQLite Standard SQL</option>
                          <option value="duckdb">DuckDB Columnar Processing</option>
                        </select>
                        <span className="text-[10px] text-slate-500 block mt-1.5 leading-tight font-sans">Target SQL dialect grammar rules.</span>
                      </div>
                    </div>
                  </div>

                  <footer className="p-6 border-t border-[#1f1f27] bg-[#16161e] flex items-center justify-between gap-4 shrink-0">
                    <span className="text-xs text-slate-400 font-sans flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
                      Ready to orchestrate background threads.
                    </span>
                    <div className="flex items-center gap-3 shrink-0">
                      <button
                        onClick={() => setShowGlobalRunModal(false)}
                        className="px-4 py-2 rounded-xl border border-[#2a2a36] text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition-all font-mono"
                      >
                        CANCEL
                      </button>
                      <button
                        onClick={handleGlobalRunAll}
                        disabled={isGlobalRunning}
                        className="px-6 py-2.5 rounded-xl font-mono font-bold text-xs bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/25 border border-emerald-400/30 flex items-center gap-2 transition-all"
                      >
                        <Play className="w-4 h-4 fill-current shrink-0" />
                        LAUNCH BATCH EXECUTION
                      </button>
                    </div>
                  </footer>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* FORENSIC DIAGNOSTIC SIDE DRAWER */}
          <AnimatePresence>
            {showDiagnoseDrawer && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end font-mono"
                onClick={() => setShowDiagnoseDrawer(false)}
              >
                <motion.div
                  initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
                  transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                  onClick={(e) => e.stopPropagation()}
                  className="bg-[#101014] border-l border-[#22222c] w-full max-w-xl h-full flex flex-col shadow-2xl relative"
                >
                  <div className="absolute top-0 left-0 bottom-0 w-1 bg-gradient-to-b from-indigo-500 via-purple-500 to-pink-500" />

                  {/* Header */}
                  <header className="p-6 border-b border-[#1c1c24] flex items-center justify-between bg-[#141419]">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.2)] shrink-0">
                        <ShieldAlert className="w-5 h-5 animate-pulse" />
                      </div>
                      <div>
                        <h2 className="text-sm font-black text-white tracking-tight uppercase">
                          Forensic Diagnosis
                        </h2>
                        <p className="text-[10px] text-slate-400 mt-0.5 font-sans">
                          {diagnoseData?.instance_id || 'Analyzing execution traces...'}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowDiagnoseDrawer(false)}
                      className="p-1 rounded-lg hover:bg-white/5 text-slate-500 hover:text-white transition-colors"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </header>

                  <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#0b0b0e] no-scrollbar">
                    {loadingDiagnose ? (
                      <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-3">
                        <Activity className="w-6 h-6 animate-spin text-indigo-400" />
                        <p className="text-xs font-bold font-mono">Scanning log sliding window...</p>
                        <p className="text-[10px] text-slate-600 font-mono">Running advanced structural heuristic analysis...</p>
                      </div>
                    ) : diagnoseData?.success === false ? (
                      <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 text-rose-400 text-xs leading-relaxed">
                        <AlertTriangle className="w-5 h-5 text-rose-500 mb-2 shrink-0" />
                        <p className="font-bold uppercase tracking-tight">Diagnosis Failed</p>
                        <p className="mt-1 text-slate-400">{diagnoseData.error}</p>
                      </div>
                    ) : diagnoseData ? (
                      <div className="space-y-6 text-xs text-slate-300">
                        {/* Overall Status Banner */}
                        <div className={`p-4 rounded-xl border flex items-start gap-3 ${diagnoseData.is_ok
                          ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-300'
                          : 'bg-rose-500/5 border-rose-500/20 text-rose-300'
                          }`}>
                          <div className={`p-2 rounded-lg ${diagnoseData.is_ok ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
                            {diagnoseData.is_ok ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertTriangle className="w-5 h-5 text-rose-400" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="font-bold text-xs text-white uppercase tracking-tight">
                              {diagnoseData.is_ok ? 'Parity Check Succeeded' : 'Diagnostic Alert Triggered'}
                            </h3>
                            <p className="text-[11px] mt-1 text-slate-400 leading-relaxed font-sans">{diagnoseData.diagnostics_summary}</p>
                          </div>
                        </div>

                        {/* Stage Culprit */}
                        <div className="bg-[#101015] border border-[#1f1f28] rounded-xl p-4">
                          <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold block mb-1">Problematic Stage / Stage Culprit</span>
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-black px-2 py-0.5 rounded border ${diagnoseData.problematic_agent === 'None'
                              ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                              : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                              }`}>
                              {diagnoseData.problematic_agent.toUpperCase()}
                            </span>
                            <span className="text-[10px] text-slate-500 font-sans">
                              {diagnoseData.problematic_agent === 'None' ? 'âœ“ Zero structural failures detected.' : 'âš  Needs architectural parameter adjustments.'}
                            </span>
                          </div>
                        </div>

                        {/* Scorecard Flow */}
                        <div className="space-y-3">
                          <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold block mb-1">Agent Operational Scorecard</span>
                          {Object.entries(diagnoseData.agent_scorecard || {}).map(([agent, info]) => {
                            let badgeColor = "text-slate-400 bg-slate-500/10 border-slate-500/20";
                            let icon = <CheckCircle2 className="w-3.5 h-3.5 text-slate-400" />;
                            if (info.status === 'success') {
                              badgeColor = "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
                              icon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />;
                            } else if (info.status === 'warning') {
                              badgeColor = "text-amber-400 bg-amber-500/10 border-amber-500/20";
                              icon = <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />;
                            } else if (info.status === 'error') {
                              badgeColor = "text-rose-400 bg-rose-500/10 border-rose-500/20";
                              icon = <XCircle className="w-3.5 h-3.5 text-rose-500 animate-pulse" />;
                            }

                            return (
                              <div key={agent} className="p-3.5 bg-[#101015] border border-[#1f1f28] rounded-xl flex items-start justify-between gap-3">
                                <div className="flex items-start gap-2.5 min-w-0">
                                  <div className="mt-0.5 shrink-0">{icon}</div>
                                  <div className="min-w-0">
                                    <h4 className="font-extrabold text-[11px] text-white tracking-tight">{agent}</h4>
                                    <p className="text-[10px] text-slate-400 leading-normal mt-0.5 font-sans">{info.message}</p>
                                  </div>
                                </div>
                                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${badgeColor}`}>
                                  {info.metrics}
                                </span>
                              </div>
                            );
                          })}
                        </div>

                        {/* Recommendations */}
                        <div className="bg-[#101015] border border-[#1f1f28] rounded-xl p-4 space-y-2.5">
                          <span className="text-[9px] uppercase tracking-wider text-slate-500 font-bold block mb-1">Recommended Forensic Actions</span>
                          {diagnoseData.recommendations.map((rec, i) => (
                            <div key={i} className="flex items-start gap-2">
                              <span className="text-indigo-400 font-bold mt-0.5">[{i + 1}]</span>
                              <p className="text-[11px] text-slate-300 leading-normal font-sans">{rec}</p>
                            </div>
                          ))}
                        </div>

                        {/* Autonomous Repair Loop Action */}
                        <div className="pt-2 border-t border-[#1f1f28] space-y-3">
                          {!diagnoseData?.is_ok && (
                            <button
                              onClick={() => handleFixIssues(diagnoseData.db_name, diagnoseData.instance_id)}
                              disabled={fixingIssues}
                              className="w-full py-3 px-4 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-black font-extrabold text-xs rounded-xl shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 transition-all transform active:scale-95"
                            >
                              {fixingIssues ? (
                                <>
                                  <RefreshCw className="w-4 h-4 animate-spin text-black" />
                                  <span>Executing Autonomous Reasoning-First Repair Loop (0% Hardcoding)...</span>
                                </>
                              ) : (
                                <>
                                  <Zap className="w-4 h-4 fill-current text-black" />
                                  <span>AUTONOMOUSLY FIX THESE ISSUES (REASONING ONLY)</span>
                                </>
                              )}
                            </button>
                          )}

                          {fixResult && (
                            <div className={`p-4 rounded-xl border text-xs space-y-3 font-sans ${fixResult.success ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-rose-500/10 border-rose-500/30 text-rose-300'}`}>
                              <div className="flex items-center justify-between gap-2 font-bold tracking-wide">
                                <div className="flex items-center gap-2">
                                  {fixResult.success ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" /> : <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />}
                                  <span>{fixResult.pending_acceptance ? 'Proposed Autonomous Repair Formulated' : fixResult.success ? 'Repair Accepted & Parity Verified' : 'Repair Attempt Failed & State Reverted'}</span>
                                </div>
                                {fixResult.pending_acceptance && (
                                  <span className="bg-amber-500 text-black px-2 py-0.5 rounded text-[10px] uppercase font-extrabold tracking-wider">Pending Review</span>
                                )}
                              </div>

                              <p className="text-[11px] text-slate-300 leading-relaxed font-mono bg-black/40 p-2.5 rounded-lg border border-white/5">{fixResult.message}</p>

                              {fixResult.pending_acceptance && (
                                <div className="space-y-2 pt-1">
                                  <div className="grid grid-cols-1 gap-2">
                                    <div className="bg-rose-950/20 border border-rose-500/20 rounded-lg p-2.5 space-y-1">
                                      <div className="text-[10px] font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                                        <XCircle className="w-3 h-3" /> Original Failing Query
                                      </div>
                                      <pre className="text-[11px] text-rose-200/90 font-mono whitespace-pre-wrap overflow-x-auto max-h-32 p-1.5 bg-black/30 rounded border border-rose-500/10">
                                        {fixResult.original_sql}
                                      </pre>
                                    </div>
                                    <div className="bg-emerald-950/20 border border-emerald-500/20 rounded-lg p-2.5 space-y-1">
                                      <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                                        <Check className="w-3 h-3" /> Proposed Corrected Query ({fixResult.row_count} rows retrieved)
                                      </div>
                                      <pre className="text-[11px] text-emerald-200/90 font-mono whitespace-pre-wrap overflow-x-auto max-h-32 p-1.5 bg-black/30 rounded border border-emerald-500/10">
                                        {fixResult.corrected_sql}
                                      </pre>
                                    </div>
                                  </div>
                                </div>
                              )}

                              {fixResult.success && fixResult.reasoning?.length > 0 && (
                                <div className="space-y-1 mt-2 pt-2 border-t border-emerald-500/20 text-[10px] text-emerald-400/90">
                                  <div className="font-bold uppercase tracking-wider text-[9px] text-emerald-400">Reasoning Audit & Verification:</div>
                                  {fixResult.reasoning.map((r, idx) => <div key={idx}>â€¢ {r}</div>)}
                                  <div className="font-mono text-amber-300 mt-1.5 pt-1 border-t border-emerald-500/20">âœ“ {fixResult.verification}</div>
                                </div>
                              )}

                              {fixResult.success && fixResult.modifications?.length > 0 && (
                                <div className="space-y-2 mt-3 pt-3 border-t border-emerald-500/20 font-sans">
                                  <div className="font-extrabold uppercase tracking-wider text-[10px] text-emerald-400 flex items-center gap-1.5">
                                    <FileCode className="w-3.5 h-3.5" /> Specific Structural Modifications Breakdown:
                                  </div>
                                  <div className="space-y-2">
                                    {fixResult.modifications.map((m, idx) => (
                                      <div key={idx} className="bg-black/60 border border-[#2a2a35] rounded-lg p-3 space-y-2 text-[11px]">
                                        <div className="flex items-center justify-between border-b border-[#2a2a35] pb-1.5">
                                          <span className="font-bold text-amber-400 text-[10px] uppercase tracking-wider">{m.location || 'Query Clause'}</span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 mt-1 font-mono text-[10px]">
                                          <div className="bg-rose-950/30 border border-rose-500/20 p-1.5 rounded">
                                            <div className="text-[9px] uppercase font-bold text-rose-400 mb-0.5">Original Snippet</div>
                                            <div className="text-rose-200/90 whitespace-pre-wrap">{m.original_text || '-'}</div>
                                          </div>
                                          <div className="bg-emerald-950/30 border border-emerald-500/20 p-1.5 rounded">
                                            <div className="text-[9px] uppercase font-bold text-emerald-400 mb-0.5">Modified Snippet</div>
                                            <div className="text-emerald-200/90 whitespace-pre-wrap">{m.modified_text || '-'}</div>
                                          </div>
                                        </div>
                                        <div className="text-slate-300 text-[10px] pt-1 leading-normal italic">
                                          <span className="text-indigo-400 font-bold not-italic">Rationale: </span>{m.explanation || 'Refined relational structure.'}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {fixResult.pending_acceptance && (
                                <div className="flex items-center gap-3 pt-2 border-t border-emerald-500/20">
                                  <button
                                    onClick={() => handleAcceptFix(diagnoseData.db_name, diagnoseData.instance_id)}
                                    className="flex-1 py-2 px-3 bg-emerald-500 hover:bg-emerald-400 text-black font-extrabold text-[11px] rounded-lg shadow flex items-center justify-center gap-1.5 transition-all transform active:scale-95"
                                  >
                                    <CheckCircle2 className="w-4 h-4 text-black" />
                                    <span>ACCEPT REPAIR & SAVE</span>
                                  </button>
                                  <button
                                    onClick={() => handleRejectFix(diagnoseData.db_name, diagnoseData.instance_id)}
                                    className="py-2 px-3 bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/30 text-rose-300 font-bold text-[11px] rounded-lg flex items-center justify-center gap-1.5 transition-all transform active:scale-95"
                                  >
                                    <XCircle className="w-4 h-4 text-rose-400" />
                                    <span>REJECT</span>
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-20 text-slate-500 text-xs">
                        No diagnostic telemetry available.
                      </div>
                    )}
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* SINGLE INSTANCE LIVE EXECUTION SIDEBAR DRAWER */}
          <AnimatePresence>
            {showLiveDrawer && (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end font-mono"
                onClick={() => setShowLiveDrawer(false)}
              >
                <motion.div
                  initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
                  transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                  onClick={(e) => e.stopPropagation()}
                  className="bg-[#101014] border-l border-[#22222c] w-full max-w-xl h-full flex flex-col shadow-2xl relative"
                >
                  <div className="absolute top-0 left-0 bottom-0 w-1 bg-gradient-to-b from-blue-500 via-cyan-500 to-purple-500" />

                  {/* Header */}
                  <header className="p-6 border-b border-[#1c1c24] flex items-center justify-between bg-[#141419]">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.2)] shrink-0">
                        <Activity className="w-5 h-5 animate-pulse" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h2 className="text-sm font-black text-white tracking-tight uppercase">
                            {activeLiveInstance}
                          </h2>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-[#1e1e28] text-blue-400 font-bold border border-blue-500/20">
                            {selectedDb}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5 font-sans">
                          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping inline-block" />
                          {liveExecutionData?.current_phase || (runningInstances[activeLiveInstance] ? 'Executing Agent Pipeline...' : 'Execution Stream Inactive')}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowLiveDrawer(false)}
                      className="p-1 rounded-lg hover:bg-white/5 text-slate-500 hover:text-white transition-colors"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                  </header>

                  <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#0b0b0e] no-scrollbar">
                    {/* Top Stats Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="bg-[#14141a] border border-[#202029] p-3 rounded-xl flex flex-col justify-between">
                        <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-between">
                          <span>Runtime</span>
                          <Clock className="w-3.5 h-3.5 text-amber-400" />
                        </div>
                        <div className="text-lg font-black text-white mt-1 font-mono">
                          {liveExecutionData ? liveTimer.toFixed(1) : '0.0'}s
                        </div>
                      </div>

                      <div className="bg-[#14141a] border border-[#202029] p-3 rounded-xl flex flex-col justify-between">
                        <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-between">
                          <span>Output Rows</span>
                          <Database className="w-3.5 h-3.5 text-emerald-400" />
                        </div>
                        <div className="text-lg font-black text-white mt-1">
                          {liveExecutionData?.metrics?.rows ?? 0}
                        </div>
                      </div>

                      <div className="bg-[#14141a] border border-[#202029] p-3 rounded-xl flex flex-col justify-between">
                        <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-between">
                          <span>Fix Loops</span>
                          <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
                        </div>
                        <div className="text-lg font-black text-white mt-1">
                          {liveExecutionData?.metrics?.corrections ?? 0}
                        </div>
                      </div>

                      <div className="bg-[#14141a] border border-[#202029] p-3 rounded-xl flex flex-col justify-between">
                        <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-between">
                          <span>Complexity</span>
                          <Zap className="w-3.5 h-3.5 text-purple-400" />
                        </div>
                        <div className="text-lg font-black text-white mt-1 truncate">
                          {liveExecutionData?.metrics?.tokens ? `${(liveExecutionData.metrics.tokens / 1000).toFixed(1)}K` : '0'} Tks
                        </div>
                      </div>
                    </div>

                    {/* Crisp Realtime Progress Feed */}
                    <div>
                      <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <Activity className="w-3.5 h-3.5 text-blue-400" />
                        Live Execution Audit Feed
                      </h3>
                      <div className="space-y-2.5">
                        {liveExecutionData?.steps?.length > 0 ? liveExecutionData.steps.map((st, i) => (
                          <div
                            key={i}
                            className="p-3 rounded-xl bg-[#141419] border border-[#22222c] flex items-start gap-3 transition-all hover:border-slate-700 font-sans text-xs"
                          >
                            <div className="mt-0.5 shrink-0 font-mono">
                              {st.type === 'start' && <span className="text-blue-400 font-bold">âš¡</span>}
                              {st.type === 'step' && <span className="text-cyan-400 font-bold">â–¶</span>}
                              {st.type === 'warn' && <span className="text-amber-400 font-bold">âš ï¸</span>}
                              {st.type === 'success' && <span className="text-emerald-400 font-bold">âœ”</span>}
                              {st.type === 'error' && <span className="text-rose-500 font-bold">âœ–</span>}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 mb-0.5">
                                <span className="uppercase font-bold tracking-tight text-slate-400">{st.type}</span>
                                <span>{st.time}</span>
                              </div>
                              <div className="text-slate-200 leading-snug line-clamp-2 font-mono text-[11px]">
                                {st.text}
                              </div>
                            </div>
                          </div>
                        )) : (
                          <div className="py-12 text-center text-slate-600 font-mono text-xs bg-[#121217] rounded-xl border border-[#1e1e26] italic">
                            Waiting for pipeline orchestration logs...
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Live Generated SQL Preview */}
                    {liveExecutionData?.latest_sql && (
                      <div>
                        <div className="flex items-center justify-between mb-2 font-mono">
                          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                            <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                            Live Candidate SQL
                          </h3>
                          <button
                            onClick={() => copyToClipboard(liveExecutionData.latest_sql, 'live_sql')}
                            className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-white px-2 py-1 rounded bg-[#1a1a22] border border-[#262632] transition-colors"
                          >
                            {copiedType === 'live_sql' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                            <span>{copiedType === 'live_sql' ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                        <div className="bg-[#141419] border border-[#22222c] rounded-xl p-3.5 overflow-x-auto font-mono text-xs text-emerald-400/90 leading-relaxed max-h-60 no-scrollbar shadow-inner">
                          <pre>{liveExecutionData.latest_sql}</pre>
                        </div>
                      </div>
                    )}
                  </div>

                  <footer className="p-6 border-t border-[#1c1c24] bg-[#141419] flex items-center justify-between">
                    <button
                      onClick={() => handleRunInstance(activeLiveInstance)}
                      disabled={runningInstances[activeLiveInstance]}
                      className="w-full py-2.5 rounded-xl font-mono font-bold text-xs bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white shadow-lg shadow-blue-500/20 border border-blue-400/30 flex items-center justify-center gap-2 transition-all"
                    >
                      {runningInstances[activeLiveInstance] ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                      {runningInstances[activeLiveInstance] ? 'PIPELINE EXECUTING...' : 'RE-RUN INSTANCE PIPELINE'}
                    </button>
                  </footer>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>        </div>
      </main>
    </div>
  );
};

export default App;
