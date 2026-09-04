type BrandProps = {
  onHome?: () => void;
};

function AlfaLogo() {
  return (
    // TODO: подставить официальный логотип, когда появится разрешённый бренд-ассет.
    <span className="brand__mark" aria-hidden="true">А</span>
  );
}

export function Brand({ onHome }: BrandProps) {
  return (
    <button className="brand" type="button" onClick={onHome} aria-label="На главную">
      <AlfaLogo />
      <span className="brand__name">АЛЬФА-БАНК</span>
    </button>
  );
}
