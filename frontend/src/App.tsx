import { useEffect, useState } from "react";
import { SessionProvider } from "./app/session/SessionProvider";
import { GlobalBannerProvider } from "./app/branding/GlobalBannerProvider";
import { ApplicationShell } from "./app/shell/ApplicationShell";
import { isDesignSystemPath } from "./app/router/routes";
import { DesignSystemShowcase } from "./design-system/showcase/DesignSystemShowcase";

export function App() {
  return (
    <SessionProvider>
      <GlobalBannerProvider>
        <AppShellGate />
      </GlobalBannerProvider>
    </SessionProvider>
  );
}

function AppShellGate() {
  const [designSystemOpen, setDesignSystemOpen] = useState(() =>
    isDesignSystemPath(window.location.pathname),
  );
  useEffect(() => {
    const sync = () =>
      setDesignSystemOpen(isDesignSystemPath(window.location.pathname));
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  if (designSystemOpen) return <DesignSystemShowcase />;
  return <ApplicationShell />;
}

export default App;
