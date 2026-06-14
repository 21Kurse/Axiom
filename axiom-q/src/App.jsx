import { useEffect, lazy, Suspense } from "react";
import Header from "./components/Header/Header";
import PanelCard from "./components/ui/PanelCard";
import ErrorBoundary from "./components/ui/ErrorBoundary";
import { SkeletonPanel } from "./components/ui/Skeleton";
import useQuantumStore from "./store/useQuantumStore";

// Lazy-load heavy panels for code splitting
const HardwarePanel = lazy(() => import("./components/HardwarePanel/HardwarePanel"));
const TelemetryPanel = lazy(() => import("./components/TelemetryPanel/TelemetryPanel"));
const AgentPanel = lazy(() => import("./components/AgentPanel/AgentPanel"));

export default function App() {
  const initWebSocket = useQuantumStore((s) => s.initWebSocket);
  const fetchQubits = useQuantumStore((s) => s.fetchQubits);
  const fetchHealth = useQuantumStore((s) => s.fetchHealth);

  useEffect(() => {
    fetchHealth();
    fetchQubits();
    initWebSocket();

    const healthInterval = setInterval(fetchHealth, 30000);
    const qubitsInterval = setInterval(fetchQubits, 10000);
    return () => {
      clearInterval(healthInterval);
      clearInterval(qubitsInterval);
    };
  }, [initWebSocket, fetchQubits, fetchHealth]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen overflow-hidden">
        <Header />

        <main className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-5">
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-3 sm:gap-4 lg:gap-5 h-full">
            {/* PANEL 1: Hardware Controls */}
            <PanelCard className="min-h-0">
              <Suspense fallback={<SkeletonPanel />}>
                <HardwarePanel />
             </Suspense>
           </PanelCard>

            {/* PANEL 2: Live Telemetry */}
            <PanelCard className="min-h-0">
              <Suspense fallback={<SkeletonPanel />}>
                <TelemetryPanel />
             </Suspense>
           </PanelCard>

            {/* PANEL 3: NVIDIA Ising Agent Console */}
            <PanelCard className="min-h-0">
              <Suspense fallback={<SkeletonPanel />}>
                <AgentPanel />
             </Suspense>
           </PanelCard>
        </div>
       </main>

        <footer className="flex items-center justify-between px-4 sm:px-6 py-1.5 border-t border-border-subtle bg-surface-card/40 text-[9px] font-mono text-slate-600 uppercase tracking-wider">
          <span className="text-slate-500/40">AXIOM.Q v0.2.8</span>
          <span>NVIDIA Ising Agent + Quantum Telemetry</span>
          <span className="text-slate-500/40">JAMHacks 2026</span>
       </footer>
     </div>
   </ErrorBoundary>
  );
}
