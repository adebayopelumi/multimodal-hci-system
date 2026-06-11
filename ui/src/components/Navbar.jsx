import React from 'react'
import { Activity, Cpu,BookOpen,HelpCircle } from 'lucide-react';
import { History as HistoryIcon, Settings as SettingsIcon } from 'lucide-react';

const Navbar = ({page,setPage}) => {
  return (
    <nav className="flex gap-2">
          <button
            onClick={() => setPage('dashboard')}
            className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
              page === 'dashboard'
                ? 'bg-violet-600 text-white'
                : 'bg-[#2e2a5a] text-violet-200 hover:bg-[#3d3870]'
            }`}
          >
            <Activity className="w-4 h-4" />
            Dashboard
          </button>
          <button
            onClick={() => setPage('history')}
            className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
              page === 'history'
                ? 'bg-violet-600 text-white'
                : 'bg-[#2e2a5a] text-violet-200 hover:bg-[#3d3870]'
            }`}
          >
            <HistoryIcon className="w-4 h-4" />
            History
          </button>
          <button
            onClick={() => setPage('settings')}
            className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
              page === 'settings'
                ? 'bg-violet-600 text-white'
                : 'bg-[#2e2a5a] text-violet-200 hover:bg-[#3d3870]'
            }`}
          >
            <SettingsIcon className="w-4 h-4" />
            Settings
          </button>
          <button
            onClick={() => setPage('tutorial')}
            className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
              page === 'tutorial'
                ? 'bg-violet-600 text-white'
                : 'bg-[#2e2a5a] text-violet-200 hover:bg-[#3d3870]'
            }`}
          >
            <HelpCircle className="w-4 h-4" />
            
            Help
          </button>
        </nav>
  )
}

export default Navbar