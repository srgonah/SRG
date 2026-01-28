export default function Spinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`inline-block w-5 h-5 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin ${className}`}
      role="status"
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
}
