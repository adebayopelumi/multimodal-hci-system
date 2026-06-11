import { useState } from "react";

import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Settings from "./pages/Settings";
import Tutorial from "./pages/Tutorial";

import Navbar from "./components/Navbar";
import { Activity, Cpu,BookOpen } from 'lucide-react';
import { History as HistoryIcon, Settings as SettingsIcon } from 'lucide-react';


// Main App Component
const App = () => {
  const [page, setPage] = useState('dashboard');

  const renderPage = () => {
    switch (page) {
      case 'dashboard': return <Dashboard />;
      case 'history': return <History />;
      case 'settings': return <Settings />;
      case 'tutorial': return <Tutorial />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="h-screen bg-linear-to-br from-[#13112b] via-[#1b1736] to-[#0e0c22] text-white flex flex-col overflow-hidden">
      {/* Header with Title and Navigation */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-[#3d3870]">
        <div className="flex items-center gap-3">
          <div className="bg-violet-500 p-2 rounded-lg">
            <Cpu className="w-5 h-5" />
          </div>
          <h1 className="text-xl font-bold">MHCI Assistant</h1>
        </div>

        {/* Navigation */}
        <Navbar page={page} setPage={setPage}/>
      </header>

      {/* Page Content */}
      {renderPage()}
    </div>
  );
};

export default App;