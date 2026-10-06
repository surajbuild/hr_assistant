import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", {
  variants: {
    tone: {
      neutral: "bg-status-neutral-bg text-status-neutral-fg",
      brand: "bg-brand-subtle text-brand-subtle-foreground",
      present: "bg-status-present-bg text-status-present-fg",
      absent: "bg-status-absent-bg text-status-absent-fg",
      late: "bg-status-late-bg text-status-late-fg",
      half: "bg-status-half-bg text-status-half-fg",
      leave: "bg-status-leave-bg text-status-leave-fg",
    },
  },
  defaultVariants: { tone: "neutral" },
});

function Badge({ className, tone, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { Badge, badgeVariants };
