import useQuantumStore from "../../store/useQuantumStore";

function StatusDot({ ok, label }) {
  return (
    <span
      className={`flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-wider ${
        ok ? "text-neon-green" : "text-red-400"
      }`}
      title={label}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          ok ? "bg-neon-green" : "bg-red-400 animate-pulse"
        }`}
      />
      {label}
   </span>
  );
}

export default function StatusBar() {
  const health = useQuantumStore((s) => s.backend_health);
  const healthError = useQuantumStore((s) => s.backend_health_error);

  if (healthError) {
    return <StatusDot ok={false} label={`Backend: ${healthError.slice(0, 30)}`} />;
  }

  if (!health) {
    return <StatusDot ok={false} label="Backend: checking..." />;
  }

  return (
    <div className="flex items-center gap-3">
      <StatusDot
        ok={health.mongo_available}
        label={health.mongo_available ? "MongoDB" : "Mongo Down"}
      />
      <StatusDot
        ok={health.litellm_reachable}
        label={health.litellm_reachable ? "LiteLLM" : "LiteLLM Down"}
      />
   </div>
  );
}
