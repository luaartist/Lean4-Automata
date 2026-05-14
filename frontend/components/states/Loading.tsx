export function Loading() {
  return (
    <div className="flex items-center justify-center py-48">
      <div className="flex flex-col items-center gap-16">
        <div className="w-48 h-48 border-4 border-accent-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-text-secondary">Loading...</p>
      </div>
    </div>
  );
}
