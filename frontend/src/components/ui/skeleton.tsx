import * as React from "react";

import { cn } from "@/lib/utils";

/** Shimmering placeholder block (see .skeleton in globals.css; static under prefers-reduced-motion). */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="skeleton" aria-hidden="true" className={cn("skeleton", className)} {...props} />;
}

export { Skeleton };
