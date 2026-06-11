import { useState } from 'react';
import { Database, MessageSquare, ArrowLeft, Layers, CheckCircle2 } from 'lucide-react';
import CustomProjectsScreen from './CustomProjectsScreen';
import CustomChatView from './CustomChatView';

const CustomWorkspace = ({ onBack }) => {
  const [currentView, setCurrentView] = useState('projects');
  const [activeProject, setActiveProject] = useState(null);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#070709] text-slate-200 font-sans">
      {/* Sidebar */}
      <aside className="w-16 lg:w-56 border-r border-[#1a1a22] bg-[#0c0c10] flex flex-col p-4 gap-6 shrink-0 z-20 shadow-2xl">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 px-1">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-emerald-600 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 shrink-0 border border-white/10">
              <Layers className="w-4 h-4 text-white" />
            </div>
            <span className="hidden lg:block font-black text-sm tracking-tighter">
              <span className="bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">Custom</span>
              <span className="text-emerald-400 font-extrabold">SQL</span>
            </span>
          </div>

          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#14141d] border border-[#262638] hover:border-amber-500/50 hover:bg-[#1a1a26] text-slate-400 hover:text-amber-400 transition-all font-bold text-[11px] font-mono justify-center w-full shadow-md shrink-0"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">Back to Hub</span>
          </button>
        </div>

        {activeProject && (
          <div className="hidden lg:flex items-center gap-2 px-2.5 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span className="text-xs font-bold text-emerald-400 truncate">{activeProject.name}</span>
          </div>
        )}

        <nav className="flex flex-col gap-1 flex-1">
          {[
            { view: 'projects', icon: Database, label: 'Data Sources' },
            { view: 'chat', icon: MessageSquare, label: 'Ask Data' },
          ].map(({ view, icon: Icon, label }) => (
            <button
              key={view}
              onClick={() => setCurrentView(view)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all font-bold text-xs tracking-tight ${
                currentView === view
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-inner'
                  : 'hover:bg-white/[0.04] text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="hidden lg:block truncate">{label}</span>
            </button>
          ))}
        </nav>

        <div className="hidden lg:flex flex-col gap-1 p-3 rounded-xl bg-[#0e0e14] border border-[#20202a] text-[10px] font-mono text-center select-none">
          <span className="text-slate-500">CustomSQL Engine</span>
          <span className="text-emerald-500/60">v1.0 · NL-to-SQL</span>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        {currentView === 'projects' && (
          <CustomProjectsScreen
            externalActiveProject={activeProject}
            onProjectActivated={(project) => setActiveProject(project)}
            onProjectDeactivated={() => setActiveProject(null)}
            onStartChat={() => setCurrentView('chat')}
          />
        )}
        {currentView === 'chat' && (
          <CustomChatView
            activeProject={activeProject}
            onGoToProjects={() => setCurrentView('projects')}
          />
        )}
      </div>
    </div>
  );
};

export default CustomWorkspace;
