const COLORS: Record<string, string> = {
  green: "bg-green-500/15 text-green-400 border-green-500/30",
  red: "bg-red-500/15 text-red-400 border-red-500/30",
  yellow: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  blue: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  slate: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

interface Props {
  color?: keyof typeof COLORS;
  children: React.ReactNode;
}

export default function Badge({ color = "slate", children }: Props) {
  return (
    <span className={`inline-block text-xs px-2 py-0.5 rounded border ${COLORS[color] ?? COLORS.slate}`}>
      {children}
    </span>
  );
}
