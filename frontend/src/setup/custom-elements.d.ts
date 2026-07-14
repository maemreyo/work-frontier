import type { DetailedHTMLProps, HTMLAttributes } from "react"

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "work-frontier-setup-center": DetailedHTMLProps<
        HTMLAttributes<HTMLElement> & {
          "base-path"?: string
          mode?: "bootstrap" | "persistent" | "manual"
        },
        HTMLElement
      >
    }
  }
}
