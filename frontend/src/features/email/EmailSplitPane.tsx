import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

const MIN_LIST = 280;
const MIN_READER = 320;
const DIVIDER = 8;

/** Local layout state only; resizing never reads or changes mailbox content. */
export function EmailSplitPane({
  children,
}: {
  children: [ReactNode, ReactNode];
}) {
  const panels = useRef<HTMLDivElement>(null);
  const [available, setAvailable] = useState(0);
  const [preferred, setPreferred] = useState<number | null>(null);
  const [resizing, setResizing] = useState(false);
  const maximum = Math.max(MIN_LIST, available - MIN_READER - DIVIDER);
  const defaultWidth = Math.min(360, available * 0.24);
  const width = Math.round(
    Math.max(MIN_LIST, Math.min(maximum, preferred ?? defaultWidth)),
  );

  useEffect(() => {
    const element = panels.current;
    if (!element) return;
    const measure = () => setAvailable(element.getBoundingClientRect().width);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const resizeTo = (clientX: number) => {
    const bounds = panels.current?.getBoundingClientRect();
    if (!bounds || bounds.width <= 700) return;
    setPreferred(
      Math.max(
        MIN_LIST,
        Math.min(
          bounds.width - MIN_READER - DIVIDER,
          clientX - bounds.left - DIVIDER / 2,
        ),
      ),
    );
  };

  return (
    <div
      ref={panels}
      className="email-panes"
      data-resizing={resizing || undefined}
      style={
        available
          ? ({ "--email-list-width": `${width}px` } as CSSProperties)
          : undefined
      }
    >
      {children[0]}
      <div
        className="email-divider"
        role="separator"
        aria-label="Resize message list and email"
        aria-orientation="vertical"
        aria-controls="email-message-list-panel"
        aria-valuemin={available ? Math.round((MIN_LIST / available) * 100) : 0}
        aria-valuemax={
          available ? Math.round((maximum / available) * 100) : 100
        }
        aria-valuenow={available ? Math.round((width / available) * 100) : 24}
        aria-valuetext={`Message list ${width} pixels wide`}
        tabIndex={0}
        title="Drag to resize · Arrow keys to adjust · Double-click to reset"
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          event.currentTarget.focus();
          event.currentTarget.setPointerCapture(event.pointerId);
          setResizing(true);
          resizeTo(event.clientX);
        }}
        onPointerMove={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            resizeTo(event.clientX);
        }}
        onPointerUp={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId);
          }
          setResizing(false);
        }}
        onPointerCancel={() => setResizing(false)}
        onLostPointerCapture={() => setResizing(false)}
        onDoubleClick={() => setPreferred(null)}
        onKeyDown={(event) => {
          const step = event.shiftKey ? 50 : 10;
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            setPreferred(
              Math.max(
                MIN_LIST,
                Math.min(
                  maximum,
                  width + (event.key === "ArrowLeft" ? -step : step),
                ),
              ),
            );
          } else if (event.key === "Home") {
            event.preventDefault();
            setPreferred(MIN_LIST);
          } else if (event.key === "End") {
            event.preventDefault();
            setPreferred(maximum);
          } else if (event.key === "Enter") {
            event.preventDefault();
            setPreferred(null);
          }
        }}
      />
      {children[1]}
    </div>
  );
}
