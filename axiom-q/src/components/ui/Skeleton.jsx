/**
 * Skeleton / shimmer placeholders for lazy-loaded panels.
 */

export function SkeletonPanel() {
  return (
    <div className="animate-pulse space-y-4 p-2">
      <div className="h-4 w-32 rounded bg-slate-700/60" />
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-12 rounded-lg bg-slate-700/40" />
        ))}
     </div>
      <div className="space-y-3">
        <div className="h-3 w-full rounded bg-slate-700/30" />
        <div className="h-3 w-full rounded bg-slate-700/30" />
     </div>
      <div className="h-10 w-full rounded-xl bg-slate-700/40" />
   </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="animate-pulse flex flex-col gap-2 p-2 w-full">
      <div className="h-4 w-48 rounded bg-slate-700/60" />
      <div className="h-[220px] w-full rounded-xl bg-slate-700/20" />
      <div className="flex justify-between">
        <div className="h-3 w-12 rounded bg-slate-700/30" />
        <div className="h-3 w-24 rounded bg-slate-700/30" />
        <div className="h-3 w-12 rounded bg-slate-700/30" />
     </div>
   </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="animate-pulse flex items-center gap-3 py-2">
      <div className="h-3 w-3 rounded-full bg-slate-700/40" />
      <div className="h-3 flex-1 rounded bg-slate-700/30" />
   </div>
  );
}
