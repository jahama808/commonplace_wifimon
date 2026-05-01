export function DashboardSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[200px] rounded-l border border-line bg-bg-1 animate-pulse" />
        ))}
      </div>
      <div className="h-[420px] rounded-[20px] border border-line bg-bg-1 animate-pulse" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-[420px] rounded-l border border-line bg-bg-1 animate-pulse" />
        <div className="h-[420px] rounded-l border border-line bg-bg-1 animate-pulse" />
        <div className="h-[420px] rounded-l border border-line bg-bg-1 animate-pulse" />
        <div className="h-[420px] rounded-l border border-line bg-bg-1 animate-pulse" />
      </div>
    </div>
  );
}
