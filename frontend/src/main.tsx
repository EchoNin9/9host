import "@/lib/amplify"
import { StrictMode } from "react"
import { createRoot } from 'react-dom/client'
import { TooltipProvider } from '@/components/ui/tooltip'
import { TenantProvider } from '@/contexts/tenant-provider'
import { TierProvider } from '@/contexts/tier-provider'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TenantProvider>
      <TierProvider>
        <TooltipProvider>
          <App />
        </TooltipProvider>
      </TierProvider>
    </TenantProvider>
  </StrictMode>,
)
