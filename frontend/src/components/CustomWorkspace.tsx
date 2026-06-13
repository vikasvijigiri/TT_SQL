import { useState } from 'react';
import { Database, MessageSquare, ArrowLeft, CheckCircle2 } from 'lucide-react';
import CustomProjectsScreen from './CustomProjectsScreen';
import CustomChatView from './CustomChatView';
import NQuireLogo from './NQuireLogo';

const CustomWorkspace = ({ onBack, onHome }) => {
  const [currentView, setCurrentView] = useState('projects');
  const [activeProject, setActiveProject] = useState(null);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#1b2738] text-slate-200 font-sans">
      {/* Sidebar */}
      <aside className="w-16 lg:w-56 border-r border-[#2c3e55] bg-[#162030] flex flex-col p-4 gap-6 shrink-0 z-20 shadow-2xl">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3 px-1">
            <NQuireLogo size={32} showName nameSize="text-xs hidden lg:block" onClick={onHome} />
          </div>

          <button
            onClick={onBack}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#181e28] border border-[#232d3a] hover:border-amber-500/40 hover:bg-[#1e2535] text-slate-400 hover:text-amber-400 transition-all font-bold text-[11px] font-mono justify-center w-full shadow-md shrink-0"
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

        <div className="hidden lg:flex flex-col gap-1 p-3 rounded-xl bg-[#161c24] border border-[#1e2530] text-[10px] font-mono text-center select-none">
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
