import { useState, useEffect } from "react";
import Shell from "./core/Shell";
import Logo from "./core/Logo";
import Setup from "./pages/Setup";
import Settings from "./pages/Settings";
import LocationPicker from "./pages/LocationPicker";
import { authApi } from "./api/auth";
import { setupApi } from "./api/setup";
import { providersApi } from "./api/providers";
import { MODULES, getModule, moduleNavItems } from "./modules/registry";

/**
 * App — top-level router. Knows NOTHING about specific modules.
 * It reads the registry to know what modules exist and which to render.
 */
export default function App() {
  const [page, setPage] = useState("loading");
  const [activeModule, setActiveModule] = useState(MODULES[0]?.manifest.id || "");
  const [activeProvider, setActiveProvider] = useState(null);

  useEffect(() => {
    const timeout = setTimeout(() => setPage("setup"), 3000);
    setupApi.status()
      .then(s => {
        if (s.first_run) {
          clearTimeout(timeout);
          setPage("location");
          return;
        }
        return authApi.status().then(data => {
          clearTimeout(timeout);
          setPage(data.authenticated ? "shell" : "setup");
        });
      })
      .catch(() => {
        clearTimeout(timeout);
        setPage("setup");
      });
  }, []);

  const refreshProvider = () => {
    providersApi.list()
      .then(data => {
        const active = data.providers.find(p => p.active);
        if (active) setActiveProvider(active);
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (page === "shell") refreshProvider();
  }, [page, activeModule]);

  const handleSignOut = async () => {
    await authApi.signOut().catch(() => {});
    setPage("setup");
    setActiveModule(MODULES[0]?.manifest.id || "");
  };

  if (page === "loading") {
    return (
      <div style={{
        height: "100vh", display: "flex",
        alignItems: "center", justifyContent: "center",
        background: "var(--bg-0)", flexDirection: "column", gap: 16,
      }}>
        <Logo size={28} />
        <div style={{
          fontFamily: "var(--font-mono)", fontSize: 10,
          color: "var(--text-3)", letterSpacing: "0.1em",
        }}>STARTING…</div>
      </div>
    );
  }

  if (page === "location") {
    return <LocationPicker onConfirmed={() => setPage("setup")} />;
  }

  if (page === "setup") {
    return <Setup onComplete={() => setPage("shell")} />;
  }

  // Render active module's component, or Settings
  const currentModule = getModule(activeModule);

  return (
    <Shell
      modules={moduleNavItems()}
      activeModule={activeModule}
      onModuleSelect={setActiveModule}
      onOpenSettings={() => setActiveModule("settings")}
      activeProvider={activeProvider}
      onSignOut={handleSignOut}
    >
      {activeModule === "settings" ? (
        <Settings />
      ) : currentModule ? (
        <currentModule.Component />
      ) : (
        <div style={{
          height: "100%", display: "flex",
          alignItems: "center", justifyContent: "center",
          color: "var(--text-3)", fontSize: 13,
        }}>
          Module not found
        </div>
      )}
    </Shell>
  );
}
