import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { StatusBar } from "./components/StatusBar";
import { ModSidebar } from "./components/ModSidebar";
import { Dashboard } from "./pages/Dashboard";
import { ModDetail } from "./pages/ModDetail";
import { DirectorPage } from "./pages/DirectorPage";
import { SearchPalette } from "./components/SearchPalette";
import { useHotkey } from "./hooks/useHotkey";

export default function App() {
  const [searchOpen, setSearchOpen] = useState(false);

  // Cmd+K / Ctrl+K — toggle the search palette.
  useHotkey({ key: "k", ctrl: true }, () => setSearchOpen((o) => !o));

  return (
    <div className="h-full flex flex-col">
      <StatusBar onOpenSearch={() => setSearchOpen(true)} />
      <div className="flex-1 flex min-h-0">
        <ModSidebar />
        <main className="flex-1 flex flex-col min-w-0">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mod/:name" element={<ModDetail />} />
            <Route path="/director" element={<DirectorPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
