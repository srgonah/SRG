import CircularProgress from "@mui/material/CircularProgress";
import Box from "@mui/material/Box";

interface SpinnerProps {
  /** Size in pixels */
  size?: number;
  /**
   * Legacy className prop.
   * Accepted for backward compatibility with existing pages.
   * Width classes like "w-8" are parsed to extract size.
   */
  className?: string;
}

/**
 * Extract a size from legacy Tailwind class names like "w-8 h-8".
 * Tailwind w-8 = 2rem = 32px, w-5 = 1.25rem = 20px.
 */
function parseLegacySize(className: string): number | undefined {
  const match = /w-(\d+)/.exec(className);
  if (match?.[1]) {
    return parseInt(match[1], 10) * 4; // Tailwind spacing scale: 1 unit = 4px
  }
  return undefined;
}

export default function Spinner({ size, className }: SpinnerProps) {
  const resolvedSize = size ?? (className ? parseLegacySize(className) : undefined) ?? 20;

  return (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      role="status"
      aria-label="Loading"
    >
      <CircularProgress size={resolvedSize} />
    </Box>
  );
}
