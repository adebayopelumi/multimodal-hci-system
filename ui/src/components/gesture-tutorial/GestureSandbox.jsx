export default function GestureSandbox({ children }) {
  return (
    <div className="relative h-40 bg-white rounded-lg overflow-hidden border border-slate-200">
      {children}
    </div>
  );
}
