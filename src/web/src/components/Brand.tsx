type BrandProps = {
  onHome?: () => void;
};

/**
 * Официальный знак Альфа-Банка — «литера» и «фундамент» (см. брендбук).
 * Контуры взяты из фирменного вектора (alfa-main-logo_red.pdf, позитивная версия),
 * а не нарисованы приближённо: клипы формы совпадают с оригиналом.
 */
function AlfaMark() {
  return (
    <svg className="brand__mark" viewBox="0 0 370 370" aria-hidden="true" focusable="false">
      <path transform="matrix(1,0,0,-1,0,370)" d="M255.722 81.858H114.27901V111.249H255.722Z" fill="#ef3124" />
      <path
        transform="matrix(1,0,0,-1,164.9778,164.2646)"
        d="M0 0 19.839 58.965H20.573L39.311 0ZM45.915 69.85C41.883 81.877 37.235 91.377 21.308 91.377 5.381 91.377 .435 81.916-3.811 69.85L-47.576-54.557H-18.553L-8.45-24.981H47.393L56.761-54.557H87.621Z"
        fill="#ef3124"
      />
    </svg>
  );
}

export function Brand({ onHome }: BrandProps) {
  return (
    <button className="brand" type="button" onClick={onHome} aria-label="На главную">
      <AlfaMark />
      <span className="brand__name">АЛЬФА-БАНК</span>
    </button>
  );
}
