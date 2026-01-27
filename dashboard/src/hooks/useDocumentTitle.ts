import { useEffect } from 'react';

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} | SRG Dashboard` : 'SRG Dashboard';
    return () => {
      document.title = 'SRG Dashboard';
    };
  }, [title]);
}
