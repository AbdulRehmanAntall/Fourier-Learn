// Inline SVG icons for the player controls (docs/frontend.md §9: no icon library).

type IconProps = { className?: string };

function Icon({ className = "size-6", children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      {children}
    </svg>
  );
}

export const PlayIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M8 5v14l11-7z" />
  </Icon>
);

export const PauseIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
  </Icon>
);

export const RewindIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M12 5V2L7 6l5 4V7a6 6 0 1 1-6 6H4a8 8 0 1 0 8-8z" />
    <text x="12" y="16" fontSize="6.5" fontWeight="700" textAnchor="middle">
      10
    </text>
  </Icon>
);

export const VolumeIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M4 9v6h4l5 5V4L8 9zm12.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4z" />
  </Icon>
);

export const MutedIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M4 9v6h4l5 5V4L8 9z" />
    <path
      d="M16 9.5l5 5m0-5-5 5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    />
  </Icon>
);

export const CaptionsIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M19 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1zm7 0h-1.5v-.5h-2v3h2V13H18v1a1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1z" />
  </Icon>
);

export const FullscreenIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M5 5h5v2H7v3H5zm9 0h5v5h-2V7h-3zM5 14h2v3h3v2H5zm12 0h2v5h-5v-2h3z" />
  </Icon>
);

export const ExitFullscreenIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M8 5h2v5H5V8h3zm6 0h2v3h3v2h-5zM5 14h5v5H8v-3H5zm9 0h5v2h-3v3h-2z" />
  </Icon>
);
