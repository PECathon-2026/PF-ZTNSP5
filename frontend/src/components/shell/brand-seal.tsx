export function BrandSeal({ size = 34, className = "brand-seal" }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 40 40"
      role="img"
      aria-label="KAGE AI seal"
      fill="none"
    >
      <circle cx="20" cy="20" r="18.4" fill="#0C0D10" stroke="rgba(201,154,58,0.85)" strokeWidth="1.4" />
      <circle cx="20" cy="20" r="15.4" stroke="rgba(239,228,205,0.16)" strokeWidth="0.8" />
      <path d="M14.6 11.6v16.8" stroke="#EFE4CD" strokeWidth="2.1" strokeLinecap="round" />
      <path d="M14.6 20.2 25.4 11.6" stroke="#C99A3A" strokeWidth="2.1" strokeLinecap="round" />
      <path d="M14.6 20.2 25.4 28.6" stroke="rgba(239,228,205,0.55)" strokeWidth="2.1" strokeLinecap="round" />
      <path d="M25.4 28.6c-2.6 1.6-5.7 2-8.6 1.2" stroke="rgba(201,154,58,0.5)" strokeWidth="1.2" strokeLinecap="round" />
      <circle cx="27.6" cy="14.4" r="1.5" fill="#E8C66A" />
    </svg>
  );
}
