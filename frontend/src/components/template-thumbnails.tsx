/**
 * SVG template thumbnail previews (Task 1.7).
 *
 * Inline SVGs that visually represent each template's layout style.
 * Used in the template picker during site creation/editing.
 */

const THUMB_W = 200
const THUMB_H = 140

function Frame({ children, bg = "#f8f9fa" }: { children: React.ReactNode; bg?: string }) {
  return (
    <svg
      viewBox={`0 0 ${THUMB_W} ${THUMB_H}`}
      className="h-full w-full"
      aria-hidden
    >
      <rect width={THUMB_W} height={THUMB_H} rx={4} fill={bg} />
      {children}
    </svg>
  )
}

/** Musician / Band — dark theme, hero banner, tour dates grid */
export function MusicianBandThumb() {
  return (
    <Frame bg="#1a1a2e">
      {/* nav bar */}
      <rect x={0} y={0} width={200} height={16} fill="#16213e" />
      <rect x={8} y={5} width={30} height={6} rx={1} fill="#e94560" />
      <rect x={120} y={5} width={15} height={4} rx={1} fill="#555" />
      <rect x={140} y={5} width={15} height={4} rx={1} fill="#555" />
      <rect x={160} y={5} width={15} height={4} rx={1} fill="#555" />
      {/* hero banner */}
      <rect x={0} y={16} width={200} height={50} fill="#0f3460" />
      <rect x={60} y={30} width={80} height={8} rx={2} fill="#e94560" />
      <rect x={70} y={42} width={60} height={5} rx={1} fill="#aaa" />
      <rect x={80} y={51} width={40} height={8} rx={2} fill="#e94560" opacity={0.8} />
      {/* tour dates grid */}
      <rect x={10} y={72} width={85} height={12} rx={2} fill="#16213e" />
      <rect x={105} y={72} width={85} height={12} rx={2} fill="#16213e" />
      <rect x={10} y={88} width={85} height={12} rx={2} fill="#16213e" />
      <rect x={105} y={88} width={85} height={12} rx={2} fill="#16213e" />
      {/* gallery row */}
      <rect x={10} y={106} width={40} height={26} rx={2} fill="#0f3460" />
      <rect x={56} y={106} width={40} height={26} rx={2} fill="#0f3460" />
      <rect x={102} y={106} width={40} height={26} rx={2} fill="#0f3460" />
      <rect x={148} y={106} width={40} height={26} rx={2} fill="#0f3460" />
    </Frame>
  )
}

/** Business Generic — professional light theme, hero CTA, service cards */
export function BusinessGenericThumb() {
  return (
    <Frame bg="#ffffff">
      {/* nav */}
      <rect x={0} y={0} width={200} height={16} fill="#f0f4f8" />
      <rect x={8} y={5} width={30} height={6} rx={1} fill="#2563eb" />
      <rect x={120} y={5} width={15} height={4} rx={1} fill="#94a3b8" />
      <rect x={140} y={5} width={15} height={4} rx={1} fill="#94a3b8" />
      <rect x={160} y={5} width={15} height={4} rx={1} fill="#94a3b8" />
      {/* hero */}
      <rect x={0} y={16} width={200} height={44} fill="#eff6ff" />
      <rect x={20} y={26} width={90} height={7} rx={2} fill="#1e40af" />
      <rect x={20} y={36} width={70} height={4} rx={1} fill="#64748b" />
      <rect x={20} y={44} width={45} height={10} rx={3} fill="#2563eb" />
      {/* service cards */}
      <rect x={10} y={66} width={55} height={34} rx={3} fill="#f0f4f8" />
      <rect x={72} y={66} width={55} height={34} rx={3} fill="#f0f4f8" />
      <rect x={134} y={66} width={55} height={34} rx={3} fill="#f0f4f8" />
      <circle cx={37} cy={76} r={5} fill="#bfdbfe" />
      <circle cx={99} cy={76} r={5} fill="#bfdbfe" />
      <circle cx={161} cy={76} r={5} fill="#bfdbfe" />
      <rect x={20} y={85} width={35} height={3} rx={1} fill="#334155" />
      <rect x={82} y={85} width={35} height={3} rx={1} fill="#334155" />
      <rect x={144} y={85} width={35} height={3} rx={1} fill="#334155" />
      {/* footer */}
      <rect x={0} y={108} width={200} height={32} fill="#1e293b" />
      <rect x={10} y={116} width={40} height={3} rx={1} fill="#64748b" />
      <rect x={10} y={122} width={30} height={3} rx={1} fill="#64748b" />
    </Frame>
  )
}

/** Personal Tech — clean minimal, code-style, project grid */
export function PersonalTechThumb() {
  return (
    <Frame bg="#fafafa">
      {/* nav */}
      <rect x={0} y={0} width={200} height={16} fill="#18181b" />
      <rect x={8} y={5} width={24} height={6} rx={1} fill="#a3e635" />
      <rect x={130} y={5} width={12} height={4} rx={1} fill="#71717a" />
      <rect x={148} y={5} width={12} height={4} rx={1} fill="#71717a" />
      <rect x={166} y={5} width={12} height={4} rx={1} fill="#71717a" />
      {/* hero with terminal-style */}
      <rect x={15} y={24} width={170} height={36} rx={4} fill="#18181b" />
      <rect x={22} y={30} width={6} height={4} rx={1} fill="#a3e635" />
      <rect x={30} y={30} width={50} height={4} rx={1} fill="#d4d4d8" />
      <rect x={22} y={38} width={6} height={4} rx={1} fill="#a3e635" />
      <rect x={30} y={38} width={70} height={4} rx={1} fill="#d4d4d8" />
      <rect x={22} y={46} width={6} height={4} rx={1} fill="#a3e635" />
      <rect x={30} y={46} width={40} height={4} rx={1} fill="#d4d4d8" />
      {/* project cards */}
      <rect x={10} y={68} width={57} height={30} rx={3} fill="#f4f4f5" stroke="#e4e4e7" strokeWidth={0.5} />
      <rect x={72} y={68} width={57} height={30} rx={3} fill="#f4f4f5" stroke="#e4e4e7" strokeWidth={0.5} />
      <rect x={134} y={68} width={57} height={30} rx={3} fill="#f4f4f5" stroke="#e4e4e7" strokeWidth={0.5} />
      <rect x={16} y={74} width={30} height={4} rx={1} fill="#27272a" />
      <rect x={78} y={74} width={30} height={4} rx={1} fill="#27272a" />
      <rect x={140} y={74} width={30} height={4} rx={1} fill="#27272a" />
      <rect x={16} y={82} width={40} height={3} rx={1} fill="#a1a1aa" />
      <rect x={78} y={82} width={40} height={3} rx={1} fill="#a1a1aa" />
      <rect x={140} y={82} width={40} height={3} rx={1} fill="#a1a1aa" />
      {/* blog preview */}
      <rect x={10} y={104} width={180} height={28} rx={3} fill="#f4f4f5" />
      <rect x={16} y={110} width={60} height={4} rx={1} fill="#27272a" />
      <rect x={16} y={118} width={120} height={3} rx={1} fill="#a1a1aa" />
      <rect x={16} y={124} width={100} height={3} rx={1} fill="#a1a1aa" />
    </Frame>
  )
}

/** Personal Resume — print-friendly, timeline, skills grid */
export function PersonalResumeThumb() {
  return (
    <Frame bg="#ffffff">
      {/* sidebar */}
      <rect x={0} y={0} width={60} height={140} fill="#1e293b" />
      {/* avatar circle */}
      <circle cx={30} cy={24} r={12} fill="#334155" />
      <rect x={12} y={40} width={36} height={4} rx={1} fill="#e2e8f0" />
      <rect x={16} y={48} width={28} height={3} rx={1} fill="#64748b" />
      {/* sidebar skills */}
      <rect x={8} y={60} width={44} height={4} rx={1} fill="#94a3b8" />
      <rect x={8} y={68} width={38} height={3} rx={1} fill="#475569" />
      <rect x={8} y={74} width={42} height={3} rx={1} fill="#475569" />
      <rect x={8} y={80} width={35} height={3} rx={1} fill="#475569" />
      <rect x={8} y={86} width={40} height={3} rx={1} fill="#475569" />
      {/* contact */}
      <rect x={8} y={98} width={44} height={4} rx={1} fill="#94a3b8" />
      <rect x={8} y={106} width={36} height={3} rx={1} fill="#475569" />
      <rect x={8} y={112} width={40} height={3} rx={1} fill="#475569" />
      {/* main content - experience timeline */}
      <rect x={70} y={8} width={80} height={6} rx={1} fill="#0f172a" />
      <rect x={70} y={18} width={50} height={4} rx={1} fill="#64748b" />
      {/* timeline dots + lines */}
      <circle cx={75} cy={32} r={2.5} fill="#2563eb" />
      <rect x={75} y={34} width={0.8} height={18} fill="#cbd5e1" />
      <rect x={82} y={29} width={60} height={4} rx={1} fill="#334155" />
      <rect x={82} y={36} width={90} height={3} rx={1} fill="#94a3b8" />
      <rect x={82} y={42} width={80} height={3} rx={1} fill="#94a3b8" />
      <circle cx={75} cy={56} r={2.5} fill="#2563eb" />
      <rect x={75} y={58} width={0.8} height={18} fill="#cbd5e1" />
      <rect x={82} y={53} width={55} height={4} rx={1} fill="#334155" />
      <rect x={82} y={60} width={85} height={3} rx={1} fill="#94a3b8" />
      <rect x={82} y={66} width={75} height={3} rx={1} fill="#94a3b8" />
      <circle cx={75} cy={80} r={2.5} fill="#2563eb" />
      <rect x={82} y={77} width={65} height={4} rx={1} fill="#334155" />
      <rect x={82} y={84} width={80} height={3} rx={1} fill="#94a3b8" />
      <rect x={82} y={90} width={70} height={3} rx={1} fill="#94a3b8" />
      {/* skills grid */}
      <rect x={70} y={102} width={50} height={5} rx={1} fill="#0f172a" />
      <rect x={70} y={112} width={30} height={10} rx={2} fill="#eff6ff" />
      <rect x={104} y={112} width={30} height={10} rx={2} fill="#eff6ff" />
      <rect x={138} y={112} width={30} height={10} rx={2} fill="#eff6ff" />
      <rect x={70} y={126} width={30} height={10} rx={2} fill="#eff6ff" />
      <rect x={104} y={126} width={30} height={10} rx={2} fill="#eff6ff" />
    </Frame>
  )
}

/** Professional Services — corporate, service listing, CTA */
export function ProfessionalServicesThumb() {
  return (
    <Frame bg="#fafaf9">
      {/* nav */}
      <rect x={0} y={0} width={200} height={16} fill="#1c1917" />
      <rect x={8} y={5} width={32} height={6} rx={1} fill="#d97706" />
      <rect x={120} y={5} width={15} height={4} rx={1} fill="#78716c" />
      <rect x={140} y={5} width={15} height={4} rx={1} fill="#78716c" />
      <rect x={160} y={5} width={30} height={6} rx={2} fill="#d97706" />
      {/* hero with overlay */}
      <rect x={0} y={16} width={200} height={44} fill="#292524" />
      <rect x={15} y={26} width={100} height={7} rx={2} fill="#fafaf9" />
      <rect x={15} y={36} width={80} height={4} rx={1} fill="#a8a29e" />
      <rect x={15} y={44} width={50} height={10} rx={3} fill="#d97706" />
      {/* service listing */}
      <rect x={10} y={66} width={85} height={30} rx={3} fill="#ffffff" stroke="#e7e5e4" strokeWidth={0.5} />
      <rect x={105} y={66} width={85} height={30} rx={3} fill="#ffffff" stroke="#e7e5e4" strokeWidth={0.5} />
      <rect x={16} y={72} width={10} height={10} rx={2} fill="#fef3c7" />
      <rect x={111} y={72} width={10} height={10} rx={2} fill="#fef3c7" />
      <rect x={30} y={72} width={50} height={4} rx={1} fill="#292524" />
      <rect x={125} y={72} width={50} height={4} rx={1} fill="#292524" />
      <rect x={30} y={80} width={60} height={3} rx={1} fill="#a8a29e" />
      <rect x={125} y={80} width={55} height={3} rx={1} fill="#a8a29e" />
      <rect x={30} y={86} width={45} height={3} rx={1} fill="#a8a29e" />
      <rect x={125} y={86} width={50} height={3} rx={1} fill="#a8a29e" />
      {/* CTA banner */}
      <rect x={10} y={102} width={180} height={30} rx={3} fill="#292524" />
      <rect x={20} y={110} width={80} height={5} rx={1} fill="#fafaf9" />
      <rect x={20} y={118} width={60} height={3} rx={1} fill="#a8a29e" />
      <rect x={140} y={111} width={40} height={12} rx={3} fill="#d97706" />
    </Frame>
  )
}

/** Blank site placeholder */
export function BlankSiteThumb() {
  return (
    <Frame bg="#f8fafc">
      <rect x={70} y={50} width={60} height={6} rx={2} fill="#cbd5e1" />
      <rect x={80} y={62} width={40} height={4} rx={1} fill="#e2e8f0" />
      <rect x={85} y={74} width={30} height={8} rx={3} fill="#e2e8f0" stroke="#cbd5e1" strokeWidth={0.5} />
    </Frame>
  )
}

/** Map template slug → thumbnail component */
export const TEMPLATE_THUMBS: Record<string, () => React.JSX.Element> = {
  "musician-band": MusicianBandThumb,
  "business-generic": BusinessGenericThumb,
  "personal-tech": PersonalTechThumb,
  "personal-resume": PersonalResumeThumb,
  "professional-services": ProfessionalServicesThumb,
}

export function getTemplateThumbnail(slug: string): React.JSX.Element {
  const Component = TEMPLATE_THUMBS[slug]
  return Component ? <Component /> : <BlankSiteThumb />
}
