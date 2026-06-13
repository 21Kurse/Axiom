/**
 * Card — reusable panel wrapper with standard Axiom.Q styling.
 * Covers the <section>-level chrome so individual panels stay decluttered.
 */
export default function PanelCard({ children, className = "" }) {
  return (
    <section
      className={`
        rounded-2xl border border-border-subtle bg-surface-card/70
        backdrop-blur-sm p-4 sm:p-5
        flex flex-col
        ${className}
      `}
    >
      {children}
    </section>
  );
}
