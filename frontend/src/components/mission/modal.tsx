"use client";

import { useEffect, useRef, type ReactNode } from "react";
import "./mission-tools.css";

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.showModal();
    return () => { dialog?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} className="dialog mission-modal" aria-label={title}
    onCancel={(event) => { event.preventDefault(); close.current(); }}
    onClick={(event) => { if (event.target === event.currentTarget) close.current(); }}>
    <div className="mission-modal__head"><h2>{title}</h2>
      <button type="button" className="btn btn--quiet btn--sm" aria-label={`Close ${title}`} onClick={onClose}>×</button>
    </div>
    {children}
  </dialog>;
}
