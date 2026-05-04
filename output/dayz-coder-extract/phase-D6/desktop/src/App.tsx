import { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { StatusBar } from "./components/StatusBar";
import { ModSidebar } from "./components/ModSidebar";
import { Dashboard } from "./pages/Dashboard";
import { ModDetail } from "./pages/ModDetail";
import { DirectorPage } from "./pages/DirectorPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ProposalsPage } from "./pages/ProposalsPage";
import { SearchPalette } from "./components/SearchPalette";
import { OnboardingWizard, useShouldShowOnboarding } from "./components/OnboardingWizard";
import { AboutDialog } from "./components/AboutDialog";
import { useHotkey } from "./hooks/useHotkey";

export default function App() {
  const [searchOpen, setSearchOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);
  const shouldShowOnboarding = useShouldShowOnboarding();

  useHotkey({ key: "k", ctrl: true }, () => setSearchOpen((o) => !o));

  return (
    <div className="h-full flex flex-col">
      <StatusBar
        onOpenSearch={() => setSearchOpen(true)}
        onOpenAbout={() => setAboutOpen(true)}
      />
      <div className="flex-1 flex min-h-0">
        <ModSidebar />
        <main className="flex-1 flex flex-col min-w-0">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mod/:name" element={<ModDetail />} />
            <Route path="/director" element={<DirectorPage />} />
            <Route path="/proposals" element={<ProposalsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
      <AboutDialog open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <OnboardingWizard
        open={shouldShowOnboarding && !onboardingDismissed}
        onClose={() => setOnboardingDismissed(true)}
      />
    </div>
  );
}
