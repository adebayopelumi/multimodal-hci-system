export default function GestureSandbox({ children }) {
  return (
    <div className="relative h-40 overflow-hidden bg-canvas-soft">
      {children}
    </div>
  );
}
