import Chip from "@mui/material/Chip";

/**
 * Map legacy color strings (used by existing pages) to MUI Chip colors.
 */
const COLOR_MAP: Record<string, "default" | "primary" | "secondary" | "error" | "warning" | "info" | "success"> = {
  green: "success",
  red: "error",
  yellow: "warning",
  blue: "info",
  slate: "default",
};

interface BadgeProps {
  /** Legacy color name or MUI Chip color */
  color?: string;
  /** Label text (new API) */
  label?: string;
  /** Children content (legacy API - rendered as label) */
  children?: React.ReactNode;
}

export default function Badge({ color = "default", label, children }: BadgeProps) {
  const chipColor = COLOR_MAP[color] ?? (color as "default" | "primary" | "secondary" | "error" | "warning" | "info" | "success");
  const chipLabel = label ?? children;

  return (
    <Chip
      label={chipLabel}
      color={chipColor}
      size="small"
      variant="outlined"
    />
  );
}
