import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { DesignSystemRoot } from "./DesignSystemRoot";
import { IconButton } from "./IconButton";

export type ToastTone = "info" | "success" | "warning" | "error";

export type ToastMessage = {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
};

type ToastContextValue = {
  toast: (message: Omit<ToastMessage, "id">) => void;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);
  const dismiss = useCallback((id: string) => {
    setMessages((current) => current.filter((item) => item.id !== id));
  }, []);
  const toast = useCallback(
    (message: Omit<ToastMessage, "id">) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setMessages((current) => [...current, { ...message, id }]);
      window.setTimeout(() => dismiss(id), 5000);
    },
    [dismiss],
  );
  const value = useMemo(() => ({ toast, dismiss }), [dismiss, toast]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <DesignSystemRoot>
          <div
            className="ds-toast-region"
            aria-live="polite"
            aria-label="Notifications"
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={cx(
                  "ds-toast",
                  `ds-toast--${message.tone ?? "info"}`,
                )}
                role="status"
              >
                <div>
                  <strong>{message.title}</strong>
                  {message.description ? <p>{message.description}</p> : null}
                </div>
                <IconButton
                  label="Dismiss notification"
                  variant="ghost"
                  size="compact"
                  onClick={() => dismiss(message.id)}
                >
                  <DsIcon name="close" size={16} />
                </IconButton>
              </div>
            ))}
          </div>
        </DesignSystemRoot>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
