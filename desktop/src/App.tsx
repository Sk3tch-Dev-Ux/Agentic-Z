import { Routes, Route, Navigate } from "react-router-dom";
import { StatusBar } from "./components/StatusBar";
import { ModSidebar } from "./components/ModSidebar";
import { Dashboard } from "./pages/Dashboard";
import { ModDetail } from "./pages/ModDetail";

export default function App() {
  return (
    <div className="h-full flex flex-col">
      <StatusBar />
      <div className="flex-1 flex min-h-0">
        <ModSidebar />
        <main className="flex-1 flex flex-col min-w-0">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mod/:name" element={<ModDetail />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
