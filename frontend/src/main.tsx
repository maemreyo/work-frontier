import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { ControlRoomApp } from "./control-room/app"
import "./control-room/tokens.css"

const root = document.getElementById("root")
if (root === null) throw new Error("Control Room root element is missing")

createRoot(root).render(
  <StrictMode>
    <ControlRoomApp />
  </StrictMode>,
)
