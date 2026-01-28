interface Props {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorBanner({ message, onDismiss }: Props) {
  return (
    <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded px-4 py-3 text-sm flex items-start gap-3">
      <span className="flex-1 break-words">{message}</span>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-red-400 hover:text-red-300 font-bold shrink-0"
        >
          &times;
        </button>
      )}
    </div>
  );
}
