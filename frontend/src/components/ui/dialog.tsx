"use client";

/**
 * Dialog + Drawer on Radix Dialog (focus trap, Escape, scroll lock, aria-modal for free).
 * - <DialogContent> is a centred panel on ≥sm and a bottom sheet on phones.
 * - <DrawerContent side="left|right"> is a full-height slide-over (mobile nav, apply-leave form, …).
 */
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogClose = DialogPrimitive.Close;
const DialogTitle = DialogPrimitive.Title;
const DialogDescription = DialogPrimitive.Description;

/**
 * Radix only restores focus to a <Trigger>. Our dialogs are state-controlled (opened from any button, menu item or
 * shortcut), so remember whatever had focus at the moment the dialog opens (onOpenAutoFocus fires before focus moves
 * into the content) and give it back on close. NB: the content component renders even while closed, so the opener
 * must be captured at open time, not at mount.
 */
function useRestoreFocus(onOpen?: (e: Event) => void, onClose?: (e: Event) => void) {
  const opener = React.useRef<HTMLElement | null>(null);
  return {
    onOpenAutoFocus: (e: Event) => {
      opener.current = document.activeElement as HTMLElement | null;
      onOpen?.(e);
    },
    onCloseAutoFocus: (e: Event) => {
      onClose?.(e);
      if (e.defaultPrevented) return;
      const el = opener.current;
      if (el && el !== document.body && el.isConnected) {
        e.preventDefault();
        el.focus();
      }
    },
  };
}

const DIALOG_SIZES = { sm: "sm:max-w-sm", md: "sm:max-w-lg", lg: "sm:max-w-2xl", xl: "sm:max-w-4xl" } as const;

function CloseButton({ className }: { className?: string }) {
  return (
    <DialogPrimitive.Close
      data-close
      aria-label="Close dialog"
      className={cn(
        "no-print inline-flex size-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        className,
      )}
    >
      <X className="size-4" />
    </DialogPrimitive.Close>
  );
}

function DialogContent({
  className,
  children,
  size = "md",
  onOpenAutoFocus,
  onCloseAutoFocus,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & { size?: keyof typeof DIALOG_SIZES }) {
  const focus = useRestoreFocus(onOpenAutoFocus, onCloseAutoFocus);
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 flex animate-overlay-in items-end justify-center overflow-y-auto bg-[var(--overlay)] p-0 sm:items-center sm:p-4">
        <DialogPrimitive.Content
          data-slot="dialog-content"
          onOpenAutoFocus={focus.onOpenAutoFocus}
          onCloseAutoFocus={focus.onCloseAutoFocus}
          className={cn(
            "relative flex max-h-[92dvh] w-full animate-sheet-up flex-col rounded-t-2xl border border-border bg-popover text-foreground shadow-float outline-none sm:animate-dialog-in sm:rounded-2xl",
            DIALOG_SIZES[size],
            className,
          )}
          {...props}
        >
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Overlay>
    </DialogPrimitive.Portal>
  );
}

function DrawerContent({
  className,
  children,
  side = "right",
  onOpenAutoFocus,
  onCloseAutoFocus,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & { side?: "left" | "right" }) {
  const focus = useRestoreFocus(onOpenAutoFocus, onCloseAutoFocus);
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 animate-overlay-in bg-[var(--overlay)]">
        <DialogPrimitive.Content
          data-slot="drawer-content"
          onOpenAutoFocus={focus.onOpenAutoFocus}
          onCloseAutoFocus={focus.onCloseAutoFocus}
          className={cn(
            "absolute inset-y-0 flex w-[min(22rem,88vw)] flex-col bg-popover text-foreground shadow-float outline-none",
            side === "left" ? "left-0 animate-drawer-left border-r border-border" : "right-0 w-[min(28rem,100vw)] animate-drawer-right border-l border-border",
            className,
          )}
          {...props}
        >
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Overlay>
    </DialogPrimitive.Portal>
  );
}

function DialogHeader({ title, description, hideClose, className }: { title: React.ReactNode; description?: React.ReactNode; hideClose?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-border px-5 py-4", className)}>
      <div className="min-w-0">
        <DialogPrimitive.Title className="text-base font-semibold text-foreground">{title}</DialogPrimitive.Title>
        {description && <DialogPrimitive.Description className="mt-0.5 text-sm text-muted-foreground">{description}</DialogPrimitive.Description>}
      </div>
      {!hideClose && <CloseButton className="-mt-1 -mr-1" />}
    </div>
  );
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("no-print flex flex-wrap justify-end gap-2 border-t border-border px-5 py-3", className)} {...props} />;
}

export { CloseButton, Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger, DrawerContent };
