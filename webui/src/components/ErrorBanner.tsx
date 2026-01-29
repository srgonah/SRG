import { useState } from "react";
import Alert from "@mui/material/Alert";
import Collapse from "@mui/material/Collapse";

interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  const [open, setOpen] = useState(true);

  const handleClose = () => {
    setOpen(false);
    onDismiss?.();
  };

  return (
    <Collapse in={open}>
      <Alert
        severity="error"
        onClose={onDismiss ? handleClose : undefined}
        sx={{ mb: 2 }}
      >
        {message}
      </Alert>
    </Collapse>
  );
}
