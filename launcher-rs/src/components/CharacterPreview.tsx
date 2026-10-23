import { useEffect, useId, useState } from "react";

/**
 * A stylised Vana'diel character model for the design page.
 *
 * The launcher cannot load the client's skinned DAT models, so this is an
 * original vector paper-doll built from the same four choices the game's
 * character creator uses: race, face (which carries the hairstyle), hair colour
 * A/B and body size.  Every control on the page changes it immediately.
 */

type EyeShape = "soft" | "sharp" | "round" | "narrow";
type BrowShape = "calm" | "up" | "down" | "flat";
type MouthShape = "smile" | "calm" | "smirk" | "grin";
type HairStyle = "crop" | "side" | "spiky" | "long" | "bob" | "pony" | "wave" | "topknot";

interface FaceArt {
  eyes: EyeShape;
  brow: BrowShape;
  mouth: MouthShape;
  hair: HairStyle;
  mark?: "scar" | "cheeks" | "chin" | "beauty";
}

const FACES: FaceArt[] = [
  { eyes: "soft", brow: "calm", mouth: "smile", hair: "crop" },
  { eyes: "sharp", brow: "up", mouth: "smirk", hair: "side" },
  { eyes: "narrow", brow: "flat", mouth: "calm", hair: "spiky" },
  { eyes: "round", brow: "down", mouth: "smile", hair: "long", mark: "scar" },
  { eyes: "soft", brow: "calm", mouth: "calm", hair: "bob", mark: "beauty" },
  { eyes: "sharp", brow: "up", mouth: "grin", hair: "pony" },
  { eyes: "round", brow: "flat", mouth: "smile", hair: "wave", mark: "cheeks" },
  { eyes: "narrow", brow: "down", mouth: "calm", hair: "topknot", mark: "chin" },
];

interface RaceArt {
  skin: string;
  skinShade: string;
  eye: string;
  hairA: string;
  hairB: string;
  cloth: string;
  clothDark: string;
  trim: string;
  boot: string;
  ear: "round" | "long" | "cat" | "galka";
  height: number;
  build: number;
  head: number;
  earScale: number;
}

const RACES: Record<number, RaceArt> = {
  1: {
    skin: "#e9b58c", skinShade: "#c98f68", eye: "#4b83a8",
    hairA: "#3c2a22", hairB: "#d9b36c", cloth: "#2e6d7d", clothDark: "#1d4854",
    trim: "#a7e0dd", boot: "#33241f", ear: "round", height: 1, build: 1, head: 1, earScale: 1,
  },
  2: {
    skin: "#f2c39c", skinShade: "#d39a74", eye: "#6a7fb8",
    hairA: "#5a3527", hairB: "#e8c17b", cloth: "#7a3e5b", clothDark: "#4e263b",
    trim: "#f0b7c8", boot: "#3b2924", ear: "round", height: 1.01, build: 0.9, head: 0.96, earScale: 1,
  },
  3: {
    skin: "#ead0b2", skinShade: "#c9a783", eye: "#5c8f6d",
    hairA: "#e6cd8e", hairB: "#8a5d3a", cloth: "#465d9e", clothDark: "#2b3c6c",
    trim: "#b9c9ff", boot: "#2c2b3c", ear: "long", height: 1.06, build: 1.02, head: 1, earScale: 1.25,
  },
  4: {
    skin: "#f4d8b9", skinShade: "#d4b38f", eye: "#6f9d84",
    hairA: "#f0d59a", hairB: "#755039", cloth: "#6a4b8c", clothDark: "#44305d",
    trim: "#d9c6ff", boot: "#33283a", ear: "long", height: 1.07, build: 0.91, head: 0.97, earScale: 1.25,
  },
  5: {
    skin: "#f1c69f", skinShade: "#cf9e74", eye: "#4f86a1",
    hairA: "#5c3b2a", hairB: "#e3c37e", cloth: "#7b5f38", clothDark: "#513e24",
    trim: "#e7cf93", boot: "#3a2c22", ear: "round", height: 0.72, build: 0.9, head: 1.52, earScale: 0.8,
  },
  6: {
    skin: "#f6cfa8", skinShade: "#d6a67c", eye: "#7d6cb0",
    hairA: "#8a4c32", hairB: "#f0cd88", cloth: "#3f7e69", clothDark: "#285446",
    trim: "#b9f0da", boot: "#33291f", ear: "round", height: 0.72, build: 0.84, head: 1.5, earScale: 0.8,
  },
  7: {
    skin: "#e6b17f", skinShade: "#c48d5d", eye: "#c99a3d",
    hairA: "#8b4c2e", hairB: "#ddb56a", cloth: "#5b4a7d", clothDark: "#3b2f56",
    trim: "#d7b6ff", boot: "#2f2735", ear: "cat", height: 1, build: 0.88, head: 0.98, earScale: 1,
  },
  8: {
    skin: "#a8bdcd", skinShade: "#849cae", eye: "#e0b64f",
    hairA: "#dbe7f2", hairB: "#5d6674", cloth: "#6e4b38", clothDark: "#4a3024",
    trim: "#e0b56d", boot: "#3d2d24", ear: "galka", height: 1.13, build: 1.3, head: 1.1, earScale: 1.1,
  },
};

const SIZES = [0.92, 1, 1.08];

/** The two hair-colour swatches the model uses for a race: [A, B]. */
export function hairSwatches(race: number): [string, string] {
  const art = RACES[race] ?? RACES[1];
  return [art.hairA, art.hairB];
}

function mix(a: string, b: string, amount: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ar = (pa >> 16) & 255;
  const ag = (pa >> 8) & 255;
  const ab = pa & 255;
  const br = (pb >> 16) & 255;
  const bg = (pb >> 8) & 255;
  const bb = pb & 255;
  const r = Math.round(ar + (br - ar) * amount);
  const g = Math.round(ag + (bg - ag) * amount);
  const bl = Math.round(ab + (bb - ab) * amount);
  return `rgb(${r}, ${g}, ${bl})`;
}

export interface CharacterPreviewProps {
  race: number;
  face: number;
  hair: number;
  size: number;
  className?: string;
}

export function CharacterPreview({ race, face, hair, size, className }: CharacterPreviewProps) {
  const uid = useId().replace(/[:]/g, "");
  // A real capture from the client's character-select screen, when the
  // preview generator has produced one.  Missing sizes fall back to medium,
  // then to the vector paper-doll.
  const [photoLevel, setPhotoLevel] = useState(0);
  useEffect(() => setPhotoLevel(0), [race, face, hair, size]);
  const photoSrc = photoLevel === 0
    ? `/design/${race}-${face}-${hair}-${size}.jpg`
    : photoLevel === 1 && size !== 1
      ? `/design/${race}-${face}-${hair}-1.jpg`
      : null;
  const photoScale = (size === 0 ? 0.94 : size === 2 ? 1.06 : 1) * 1.12;
  const art = RACES[race] ?? RACES[1];
  const features = FACES[Math.max(0, Math.min(7, face - 1))];
  const hairColor = hair === 1 ? art.hairB : art.hairA;
  const hairLight = mix(hairColor, "#ffffff", 0.28);
  const hairDark = mix(hairColor, "#000000", 0.35);
  const sizeScale = SIZES[Math.max(0, Math.min(2, size))] ?? 1;
  const raceScale = race === 5 || race === 6 ? 1.08 : race === 8 ? 1.02 : 1;
  const scale = 1.22 * sizeScale * raceScale;

  // Local units: feet at y=0, the figure rises into negative y.
  const headR = 34 * art.head;
  const legLen = 142 * art.height;
  const torsoLen = 104 * art.height;
  const hipY = -legLen;
  const shoulderY = hipY - torsoLen;
  const headCY = shoulderY - headR * 0.62;
  const shoulderW = 42 * art.build;
  const hipW = 28 * art.build;

  const backHair = renderBackHair(features.hair, hairColor, hairDark, headCY, headR, shoulderY);
  const frontHair = renderFrontHair(features.hair, hairColor, hairLight, headCY, headR);
  const ears = renderEars(art, headCY, headR);

  return (
    <div className={className ? `design-preview ${className}` : "design-preview"}>
      {photoSrc ? (
        <div className={`design-photo-frame size-${size}`}>
          <img
            key={photoSrc}
            className="design-photo"
            src={photoSrc}
            alt={`${["Hume", "Hume", "Elvaan", "Elvaan", "Tarutaru", "Tarutaru", "Mithra", "Galka"][race - 1] ?? "Character"} face ${face}, hair ${hair === 0 ? "A" : "B"}`}
            onError={() => setPhotoLevel((level) => level + 1)}
            style={{ transform: `scale(${photoScale})` }}
            draggable={false}
          />
          <div className="design-photo-shade" />
          <span className="design-photo-size">{["S", "M", "L"][size] ?? "M"}</span>
          <span className="design-photo-source">CLIENT PREVIEW</span>
        </div>
      ) : (
      <svg viewBox="0 0 420 560" role="img" aria-label={`Character preview, face ${face}, hair ${hair === 0 ? "A" : "B"}, ${["small", "medium", "large"][size]} size`}>
        <defs>
          <radialGradient id={`${uid}-stage`} cx="50%" cy="34%" r="72%">
            <stop offset="0%" stopColor="#1b4660" />
            <stop offset="55%" stopColor="#0d2538" />
            <stop offset="100%" stopColor="#07131f" />
          </radialGradient>
          <linearGradient id={`${uid}-skin`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={art.skin} />
            <stop offset="100%" stopColor={art.skinShade} />
          </linearGradient>
          <linearGradient id={`${uid}-hair`} x1="0" y1="0" x2="0.8" y2="1">
            <stop offset="0%" stopColor={hairLight} />
            <stop offset="55%" stopColor={hairColor} />
            <stop offset="100%" stopColor={hairDark} />
          </linearGradient>
          <linearGradient id={`${uid}-cloth`} x1="0" y1="0" x2="0.6" y2="1">
            <stop offset="0%" stopColor={mix(art.cloth, "#ffffff", 0.12)} />
            <stop offset="100%" stopColor={art.clothDark} />
          </linearGradient>
          <linearGradient id={`${uid}-metal`} x1="0" y1="0" x2="0.3" y2="1">
            <stop offset="0%" stopColor="#f4deb0" />
            <stop offset="55%" stopColor="#c7a463" />
            <stop offset="100%" stopColor="#806334" />
          </linearGradient>
          <radialGradient id={`${uid}-glow`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#7fe9ff" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#7fe9ff" stopOpacity="0" />
          </radialGradient>
          <filter id={`${uid}-soft`} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="7" />
          </filter>
        </defs>

        <rect width="420" height="560" rx="18" fill={`url(#${uid}-stage)`} />
        <circle cx="210" cy="221" r="148" fill={`url(#${uid}-glow)`} />
        <circle cx="210" cy="221" r="132" fill="none" stroke="#5b93ad" strokeOpacity="0.22" strokeWidth="1" />
        <circle cx="210" cy="221" r="166" fill="none" stroke="#5b93ad" strokeOpacity="0.12" strokeWidth="1" />
        <path d="M42 530 Q210 472 378 530" fill="none" stroke="#5b93ad" strokeOpacity="0.2" strokeWidth="2" />
        {[0, 1, 2, 3, 4, 5].map((index) => (
          <circle
            key={index}
            className="design-mote"
            cx={66 + index * 58}
            cy={150 + ((index * 43) % 150)}
            r={index % 2 === 0 ? 1.6 : 1}
            fill={index % 3 === 0 ? "#ffd166" : "#7fe9ff"}
            opacity="0.65"
            style={{ animationDelay: `${index * 0.7}s` }}
          />
        ))}
        <ellipse cx="210" cy="520" rx="122" ry="30" fill="#030a12" opacity="0.72" />
        <ellipse cx="210" cy="518" rx="96" ry="21" fill="#0e2a3d" opacity="0.9" />
        <ellipse cx="210" cy="514" rx="88" ry="15" fill="#25536d" opacity="0.3" />

        <g transform={`translate(210 518) scale(${scale})`}>
          <g className="design-figure">
          {race === 7 && (
            <path
              d={`M ${hipW * 0.4} ${hipY + 8} C ${hipW + 40} ${hipY - 6}, ${hipW + 56} ${hipY - 52}, ${hipW + 26} ${hipY - 74}
                  C ${hipW + 12} ${hipY - 84}, ${hipW + 2} ${hipY - 76}, ${hipW + 12} ${hipY - 66}
                  C ${hipW + 34} ${hipY - 48}, ${hipW + 22} ${hipY - 14}, ${hipW * 0.5} ${hipY - 4} Z`}
              fill={hairColor}
              opacity="0.95"
            />
          )}
          {backHair}
          {renderLegs(art, hipY, legLen, hipW)}
          {renderTorso(art, uid, shoulderY, hipY, shoulderW, hipW)}
          {renderArms(art, shoulderY, hipY, shoulderW)}
          <rect x={-7} y={headCY + headR * 0.6} width="14" height={Math.max(16, shoulderY - headCY - headR * 0.4)} rx="6" fill={`url(#${uid}-skin)`} />
          {ears}
          <ellipse cx="0" cy={headCY} rx={headR * 0.9} ry={headR * 1.03} fill={`url(#${uid}-skin)`} />
          <path
            d={`M ${-headR * 0.42} ${headCY + headR * 0.62} Q 0 ${headCY + headR * 1.08} ${headR * 0.42} ${headCY + headR * 0.62}
                Q ${headR * 0.22} ${headCY + headR * 0.82} 0 ${headCY + headR * 0.84}
                Q ${-headR * 0.22} ${headCY + headR * 0.82} ${-headR * 0.42} ${headCY + headR * 0.62} Z`}
            fill={art.skinShade}
            opacity="0.35"
          />
          {renderFace(features, art, headCY, headR)}
          {frontHair}
          {features.hair === "topknot" && (
            <g>
              <circle cx={headR * 0.08} cy={headCY - headR * 1.18} r={headR * 0.3} fill={`url(#${uid}-hair)`} />
              <path d={`M ${-headR * 0.34} ${headCY - headR * 0.98} Q 0 ${headCY - headR * 1.34} ${headR * 0.36} ${headCY - headR * 1.02}`}
                fill="none" stroke={hairDark} strokeWidth={headR * 0.09} strokeLinecap="round" />
            </g>
          )}
          {features.hair === "pony" && (
            <path
              d={`M ${headR * 0.72} ${headCY - headR * 0.5} C ${headR * 1.5} ${headCY - headR * 0.3}, ${headR * 1.6} ${headCY + headR * 1.2}, ${headR * 1.05} ${headCY + headR * 1.5}`}
              fill="none" stroke={hairColor} strokeWidth={headR * 0.34} strokeLinecap="round"
            />
          )}
          <path
            d={`M ${-hipW * 0.72} ${hipY + 14} L ${-hipW * 0.62} ${hipY - 6} L ${hipW * 0.62} ${hipY - 6} L ${hipW * 0.72} ${hipY + 14}`}
            fill={art.clothDark}
          />
          </g>
        </g>
        <rect x="16" y="16" width="56" height="26" rx="13" fill="#07131f" stroke="#2b536c" strokeOpacity="0.7" />
        <text x="44" y="34" textAnchor="middle" fill="#8fd8e9" fontSize="12" fontFamily="var(--mono)" letterSpacing="1">
          {["S", "M", "L"][size] ?? "M"}
        </text>
        <text x="404" y="34" textAnchor="end" fill="#4c7187" fontSize="10" fontFamily="var(--mono)" letterSpacing="1.5">
          VANADIEL
        </text>
      </svg>
      )}
    </div>
  );
}

function renderEyes(features: FaceArt, art: RaceArt, headCY: number, headR: number) {
  const y = headCY + headR * 0.06;
  const x = headR * 0.36;
  const eye = (side: number) => {
    const cx = side * x;
    if (features.eyes === "round") {
      return (
        <g key={side}>
          <ellipse cx={cx} cy={y} rx={headR * 0.15} ry={headR * 0.16} fill="#f8fbff" />
          <circle cx={cx} cy={y + 1} r={headR * 0.1} fill={art.eye} />
          <circle cx={cx} cy={y + 1} r={headR * 0.05} fill="#08131c" />
          <circle cx={cx - 1.5} cy={y - 1.5} r={1.5} fill="#ffffff" />
        </g>
      );
    }
    if (features.eyes === "narrow") {
      return (
        <g key={side}>
          <path d={`M ${cx - headR * 0.19} ${y} Q ${cx} ${y + headR * 0.05} ${cx + headR * 0.19} ${y - 1}`}
            fill="none" stroke="#1c2830" strokeWidth={headR * 0.06} strokeLinecap="round" />
          <circle cx={cx} cy={y} r={headR * 0.045} fill={art.eye} />
        </g>
      );
    }
    const sharp = features.eyes === "sharp";
    return (
      <g key={side}>
        <path
          d={sharp
            ? `M ${cx - headR * 0.2} ${y - 2} Q ${cx} ${y - headR * 0.12} ${cx + headR * 0.19} ${y + 1}
               Q ${cx} ${y + headR * 0.1} ${cx - headR * 0.2} ${y - 2} Z`
            : `M ${cx - headR * 0.18} ${y - 1} Q ${cx} ${y - headR * 0.09} ${cx + headR * 0.18} ${y}
               Q ${cx} ${y + headR * 0.1} ${cx - headR * 0.18} ${y - 1} Z`}
          fill="#f8fbff"
        />
        <circle cx={cx + (side > 0 ? 1 : -1)} cy={y} r={headR * 0.075} fill={art.eye} />
        <circle cx={cx + (side > 0 ? 1 : -1)} cy={y} r={headR * 0.035} fill="#08131c" />
        <path d={`M ${cx - headR * 0.2} ${y - 1} Q ${cx} ${y - headR * 0.11} ${cx + headR * 0.2} ${y + (sharp ? 1 : 0)}`}
          fill="none" stroke="#1c2830" strokeWidth={headR * 0.045} strokeLinecap="round" />
      </g>
    );
  };
  return <g>{eye(-1)}{eye(1)}</g>;
}

function renderFace(features: FaceArt, art: RaceArt, headCY: number, headR: number) {
  const mouthY = headCY + headR * 0.43;
  const browY = headCY - headR * 0.2;
  const browTilt = features.brow === "up" ? -headR * 0.06 : features.brow === "down" ? headR * 0.05 : 0;
  const brow = (side: number) => (
    <path
      key={side}
      d={`M ${side * headR * 0.52} ${browY} Q ${side * headR * 0.36} ${browY - headR * 0.06 + browTilt} ${side * headR * 0.18} ${browY + headR * 0.015}`}
      fill="none" stroke={mix(art.hairA, "#000000", 0.15)} strokeWidth={headR * 0.055} strokeLinecap="round"
    />
  );
  const mouth = () => {
    if (features.mouth === "grin") {
      return <path d={`M ${-headR * 0.16} ${mouthY} Q 0 ${mouthY + headR * 0.16} ${headR * 0.16} ${mouthY}`}
        fill="none" stroke="#6d3b38" strokeWidth={headR * 0.055} strokeLinecap="round" />;
    }
    if (features.mouth === "smirk") {
      return <path d={`M ${-headR * 0.1} ${mouthY + 1} Q ${headR * 0.06} ${mouthY + headR * 0.08} ${headR * 0.17} ${mouthY - 1}`}
        fill="none" stroke="#6d3b38" strokeWidth={headR * 0.05} strokeLinecap="round" />;
    }
    if (features.mouth === "calm") {
      return <path d={`M ${-headR * 0.1} ${mouthY} Q 0 ${mouthY + headR * 0.035} ${headR * 0.1} ${mouthY}`}
        fill="none" stroke="#6d3b38" strokeWidth={headR * 0.045} strokeLinecap="round" />;
    }
    return <path d={`M ${-headR * 0.13} ${mouthY - 1} Q 0 ${mouthY + headR * 0.1} ${headR * 0.13} ${mouthY - 1}`}
      fill="none" stroke="#6d3b38" strokeWidth={headR * 0.05} strokeLinecap="round" />;
  };
  return (
    <g>
      {brow(-1)}
      {brow(1)}
      {renderEyes(features, art, headCY, headR)}
      <path d={`M ${-headR * 0.02} ${headCY + headR * 0.17} Q ${-headR * 0.06} ${headCY + headR * 0.28} ${headR * 0.035} ${headCY + headR * 0.29}`}
        fill="none" stroke={art.skinShade} strokeWidth={headR * 0.045} strokeLinecap="round" />
      {mouth()}
      {features.mark === "scar" && (
        <path d={`M ${-headR * 0.62} ${headCY + headR * 0.02} l ${headR * 0.12} ${headR * 0.28}`}
          stroke="#8f5a4b" strokeWidth={headR * 0.035} strokeLinecap="round" opacity="0.8" />
      )}
      {features.mark === "beauty" && (
        <circle cx={headR * 0.43} cy={headCY + headR * 0.4} r={headR * 0.035} fill="#5c3b32" />
      )}
      {features.mark === "cheeks" && (
        <g stroke="#b06a55" strokeWidth={headR * 0.035} strokeLinecap="round" opacity="0.7">
          <path d={`M ${-headR * 0.55} ${headCY + headR * 0.28} l ${headR * 0.1} 0`} />
          <path d={`M ${-headR * 0.5} ${headCY + headR * 0.36} l ${headR * 0.09} 0`} />
          <path d={`M ${headR * 0.45} ${headCY + headR * 0.28} l ${headR * 0.1} 0`} />
        </g>
      )}
      {features.mark === "chin" && (
        <path d={`M ${-headR * 0.12} ${headCY + headR * 0.72} l ${headR * 0.24} 0`}
          stroke="#77899b" strokeWidth={headR * 0.045} strokeLinecap="round" opacity="0.6" />
      )}
      <ellipse cx={-headR * 0.55} cy={headCY + headR * 0.3} rx={headR * 0.12} ry={headR * 0.05} fill="#d9826d" opacity="0.2" />
      <ellipse cx={headR * 0.55} cy={headCY + headR * 0.3} rx={headR * 0.12} ry={headR * 0.05} fill="#d9826d" opacity="0.2" />
    </g>
  );
}

function renderEars(art: RaceArt, headCY: number, headR: number) {
  if (art.ear === "long") {
    return (
      <g fill={art.skinShade}>
        <path d={`M ${-headR * 0.82} ${headCY + headR * 0.12} L ${-headR * 1.55} ${headCY - headR * 0.42}
          L ${-headR * 0.86} ${headCY + headR * 0.4} Z`} />
        <path d={`M ${headR * 0.82} ${headCY + headR * 0.12} L ${headR * 1.55} ${headCY - headR * 0.42}
          L ${headR * 0.86} ${headCY + headR * 0.4} Z`} />
      </g>
    );
  }
  if (art.ear === "cat") {
    return (
      <g>
        <path d={`M ${-headR * 0.72} ${headCY - headR * 0.62} L ${-headR * 0.5} ${headCY - headR * 1.42}
          L ${-headR * 0.14} ${headCY - headR * 0.82} Z`} fill={art.skin} stroke={art.skinShade} strokeWidth="2" />
        <path d={`M ${headR * 0.72} ${headCY - headR * 0.62} L ${headR * 0.5} ${headCY - headR * 1.42}
          L ${headR * 0.14} ${headCY - headR * 0.82} Z`} fill={art.skin} stroke={art.skinShade} strokeWidth="2" />
        <path d={`M ${-headR * 0.6} ${headCY - headR * 0.78} L ${-headR * 0.51} ${headCY - headR * 1.2}
          L ${-headR * 0.32} ${headCY - headR * 0.86} Z`} fill="#d98f8b" opacity="0.75" />
        <path d={`M ${headR * 0.6} ${headCY - headR * 0.78} L ${headR * 0.51} ${headCY - headR * 1.2}
          L ${headR * 0.32} ${headCY - headR * 0.86} Z`} fill="#d98f8b" opacity="0.75" />
      </g>
    );
  }
  if (art.ear === "galka") {
    return (
      <g fill={art.skinShade}>
        <path d={`M ${-headR * 0.86} ${headCY - headR * 0.1} Q ${-headR * 1.5} ${headCY - headR * 0.7} ${-headR * 1.52} ${headCY + headR * 0.1}
          Q ${-headR * 1.3} ${headCY + headR * 0.55} ${-headR * 0.82} ${headCY + headR * 0.35} Z`} />
        <path d={`M ${headR * 0.86} ${headCY - headR * 0.1} Q ${headR * 1.5} ${headCY - headR * 0.7} ${headR * 1.52} ${headCY + headR * 0.1}
          Q ${headR * 1.3} ${headCY + headR * 0.55} ${headR * 0.82} ${headCY + headR * 0.35} Z`} />
      </g>
    );
  }
  return (
    <g fill={art.skinShade}>
      <ellipse cx={-headR * 0.9} cy={headCY + headR * 0.12} rx={headR * 0.14} ry={headR * 0.25} />
      <ellipse cx={headR * 0.9} cy={headCY + headR * 0.12} rx={headR * 0.14} ry={headR * 0.25} />
    </g>
  );
}

function renderBackHair(
  style: HairStyle,
  color: string,
  dark: string,
  headCY: number,
  headR: number,
  shoulderY: number,
) {
  const common = { fill: color };
  switch (style) {
    case "long":
      return (
        <path
          d={`M ${-headR * 0.95} ${headCY - headR * 0.1}
              C ${-headR * 1.3} ${headCY + headR * 0.8}, ${-headR * 1.2} ${shoulderY + headR * 0.8}, ${-headR * 1.35} ${shoulderY + headR * 1.7}
              L ${headR * 1.35} ${shoulderY + headR * 1.7}
              C ${headR * 1.2} ${shoulderY + headR * 0.8}, ${headR * 1.3} ${headCY + headR * 0.8}, ${headR * 0.95} ${headCY - headR * 0.1}
              Z`}
          {...common}
        />
      );
    case "bob":
      return (
        <path
          d={`M ${-headR} ${headCY - headR * 0.2} C ${-headR * 1.35} ${headCY + headR * 0.8}, ${-headR * 1.05} ${headCY + headR * 1.25}, ${-headR * 0.72} ${headCY + headR * 1.3}
              L ${headR * 0.72} ${headCY + headR * 1.3} C ${headR * 1.05} ${headCY + headR * 1.25}, ${headR * 1.35} ${headCY + headR * 0.8}, ${headR} ${headCY - headR * 0.2} Z`}
          {...common}
        />
      );
    case "pony":
      return (
        <g>
          <path d={`M ${-headR} ${headCY - headR * 0.1} C ${-headR * 1.2} ${headCY + headR * 0.7}, ${-headR * 0.8} ${headCY + headR * 1.1}, ${-headR * 0.55} ${headCY + headR * 1.15}
            L ${headR * 0.55} ${headCY + headR * 1.15} C ${headR * 0.8} ${headCY + headR * 1.1}, ${headR * 1.2} ${headCY + headR * 0.7}, ${headR} ${headCY - headR * 0.1} Z`}
            {...common} />
          <path d={`M ${headR * 0.8} ${headCY - headR * 0.3} C ${headR * 1.7} ${headCY - headR * 0.5}, ${headR * 1.7} ${headCY + headR * 1.2}, ${headR * 1.02} ${headCY + headR * 1.55}`}
            fill="none" stroke={dark} strokeWidth={headR * 0.4} strokeLinecap="round" />
        </g>
      );
    case "wave":
      return (
        <g>
          <path d={`M ${-headR} ${headCY - headR * 0.15} C ${-headR * 1.6} ${headCY + headR * 0.9}, ${-headR * 0.6} ${shoulderY + headR * 1.2}, ${-headR * 1.3} ${shoulderY + headR * 1.85}
            L ${headR * 1.3} ${shoulderY + headR * 1.85} C ${headR * 0.6} ${shoulderY + headR * 1.2}, ${headR * 1.6} ${headCY + headR * 0.9}, ${headR} ${headCY - headR * 0.15} Z`}
            {...common} />
          <path d={`M ${-headR * 1.1} ${headCY + headR * 0.7} Q ${-headR * 1.3} ${headCY + headR * 1.3} ${-headR * 1.05} ${headCY + headR * 1.8}`}
            fill="none" stroke={dark} strokeWidth={headR * 0.08} opacity="0.5" />
          <path d={`M ${headR * 1.1} ${headCY + headR * 0.7} Q ${headR * 1.3} ${headCY + headR * 1.3} ${headR * 1.05} ${headCY + headR * 1.8}`}
            fill="none" stroke={dark} strokeWidth={headR * 0.08} opacity="0.5" />
        </g>
      );
    case "spiky":
      return (
        <path d={`M ${-headR} ${headCY - headR * 0.1} L ${-headR * 1.25} ${headCY - headR * 0.9}
          L ${-headR * 0.55} ${headCY - headR * 0.95} L ${-headR * 0.9} ${headCY - headR * 1.7} L ${-headR * 0.2} ${headCY - headR * 1.2}
          L ${-headR * 0.1} ${headCY - headR * 1.85} L ${headR * 0.35} ${headCY - headR * 1.1}
          L ${headR * 0.8} ${headCY - headR * 1.55} L ${headR * 0.7} ${headCY - headR * 0.75}
          L ${headR * 1.2} ${headCY - headR * 0.55} L ${headR * 0.95} ${headCY + headR * 0.2} Z`}
          {...common} />
      );
    case "topknot":
      return <path d={`M ${-headR * 0.9} ${headCY} Q ${-headR * 0.8} ${headCY + headR * 0.8} 0 ${headCY + headR * 0.95} Q ${headR * 0.8} ${headCY + headR * 0.8} ${headR * 0.9} ${headCY} Z`} {...common} />;
    case "side":
      return <path d={`M ${-headR * 0.9} ${headCY} Q ${-headR * 1.15} ${headCY + headR * 0.75} ${-headR * 0.5} ${headCY + headR * 1.05} L ${headR * 0.7} ${headCY + headR * 0.9} Q ${headR * 1.1} ${headCY + headR * 0.5} ${headR * 0.9} ${headCY} Z`} {...common} />;
    case "crop":
    default:
      return <ellipse cx="0" cy={headCY - headR * 0.15} rx={headR * 0.94} ry={headR * 0.72} fill={color} />;
  }
}

function renderFrontHair(style: HairStyle, color: string, light: string, headCY: number, headR: number) {
  switch (style) {
    case "spiky":
      return (
        <path d={`M ${-headR * 0.95} ${headCY - headR * 0.55}
          L ${-headR * 0.7} ${headCY - headR * 1.05} L ${-headR * 0.38} ${headCY - headR * 0.7}
          L ${-headR * 0.08} ${headCY - headR * 1.15} L ${headR * 0.2} ${headCY - headR * 0.72}
          L ${headR * 0.58} ${headCY - headR * 1.08} L ${headR * 0.72} ${headCY - headR * 0.6}
          L ${headR * 0.98} ${headCY - headR * 0.35} L ${headR * 0.62} ${headCY - headR * 0.18}
          Q ${headR * 0.2} ${headCY - headR * 0.45} ${-headR * 0.62} ${headCY - headR * 0.22} Z`}
          fill={color} />
      );
    case "long":
      return (
        <g>
          <path d={`M ${-headR * 0.92} ${headCY - headR * 0.7} Q ${-headR * 0.3} ${headCY - headR * 1.35} ${headR * 0.92} ${headCY - headR * 0.55}
            L ${headR * 0.62} ${headCY - headR * 0.1} Q ${headR * 0.05} ${headCY - headR * 0.55} ${-headR * 0.45} ${headCY - headR * 0.18} Z`} fill={color} />
          <path d={`M ${-headR * 0.92} ${headCY - headR * 0.5} Q ${-headR * 1.06} ${headCY + headR * 0.8} ${-headR * 0.8} ${headCY + headR * 1.35}
            L ${-headR * 0.6} ${headCY + headR * 1.3} Q ${-headR * 0.78} ${headCY + headR * 0.75} ${-headR * 0.6} ${headCY - headR * 0.2} Z`} fill={color} />
          <path d={`M ${headR * 0.92} ${headCY - headR * 0.5} Q ${headR * 1.06} ${headCY + headR * 0.8} ${headR * 0.8} ${headCY + headR * 1.35}
            L ${headR * 0.6} ${headCY + headR * 1.3} Q ${headR * 0.78} ${headCY + headR * 0.75} ${headR * 0.6} ${headCY - headR * 0.2} Z`} fill={color} />
        </g>
      );
    case "bob":
      return (
        <g>
          <path d={`M ${-headR * 0.95} ${headCY - headR * 0.4} Q ${-headR * 0.55} ${headCY - headR * 1.3} ${headR * 0.2} ${headCY - headR * 1.15}
            Q ${headR * 0.85} ${headCY - headR * 1.0} ${headR * 0.95} ${headCY - headR * 0.35}
            Q ${headR * 0.5} ${headCY - headR * 0.55} ${headR * 0.12} ${headCY - headR * 0.38}
            Q ${-headR * 0.38} ${headCY - headR * 0.62} ${-headR * 0.78} ${headCY - headR * 0.18} Z`} fill={color} />
          <path d={`M ${-headR * 0.92} ${headCY - headR * 0.1} Q ${-headR * 1.0} ${headCY + headR * 0.6} ${-headR * 0.7} ${headCY + headR * 0.95} L ${-headR * 0.52} ${headCY + headR * 0.8} Q ${-headR * 0.7} ${headCY + headR * 0.35} ${-headR * 0.55} ${headCY - headR * 0.1} Z`} fill={color} />
          <path d={`M ${headR * 0.92} ${headCY - headR * 0.1} Q ${headR * 1.0} ${headCY + headR * 0.6} ${headR * 0.7} ${headCY + headR * 0.95} L ${headR * 0.52} ${headCY + headR * 0.8} Q ${headR * 0.7} ${headCY + headR * 0.35} ${headR * 0.55} ${headCY - headR * 0.1} Z`} fill={color} />
        </g>
      );
    case "pony":
      return (
        <path d={`M ${-headR * 0.95} ${headCY - headR * 0.45} Q ${-headR * 0.4} ${headCY - headR * 1.3} ${headR * 0.45} ${headCY - headR * 1.05}
          Q ${headR * 0.95} ${headCY - headR * 0.85} ${headR * 0.95} ${headCY - headR * 0.4}
          Q ${headR * 0.55} ${headCY - headR * 0.65} ${headR * 0.1} ${headCY - headR * 0.45}
          Q ${-headR * 0.45} ${headCY - headR * 0.75} ${-headR * 0.74} ${headCY - headR * 0.1} Z`} fill={color} />
      );
    case "wave":
      return (
        <g>
          <path d={`M ${-headR * 0.95} ${headCY - headR * 0.45} Q ${-headR * 0.7} ${headCY - headR * 1.25} ${headR * 0.1} ${headCY - headR * 1.15}
            Q ${headR * 0.85} ${headCY - headR * 1.0} ${headR * 0.95} ${headCY - headR * 0.4}
            Q ${headR * 0.6} ${headCY - headR * 0.3} ${headR * 0.4} ${headCY - headR * 0.45}
            Q ${headR * 0.1} ${headCY - headR * 0.2} ${-headR * 0.1} ${headCY - headR * 0.38}
            Q ${-headR * 0.45} ${headCY - headR * 0.2} ${-headR * 0.6} ${headCY - headR * 0.06} Z`} fill={color} />
          <path d={`M ${-headR * 0.95} ${headCY - headR * 0.2} Q ${-headR * 1.15} ${headCY + headR * 0.5} ${-headR * 0.75} ${headCY + headR * 0.95}
            L ${-headR * 0.6} ${headCY + headR * 0.8} Q ${-headR * 0.9} ${headCY + headR * 0.4} ${-headR * 0.7} ${headCY - headR * 0.1} Z`} fill={color} />
          <path d={`M ${headR * 0.95} ${headCY - headR * 0.2} Q ${headR * 1.15} ${headCY + headR * 0.5} ${headR * 0.75} ${headCY + headR * 0.95}
            L ${headR * 0.6} ${headCY + headR * 0.8} Q ${headR * 0.9} ${headCY + headR * 0.4} ${headR * 0.7} ${headCY - headR * 0.1} Z`} fill={color} />
        </g>
      );
    case "topknot":
      return (
        <path d={`M ${-headR * 0.92} ${headCY - headR * 0.45} Q ${-headR * 0.65} ${headCY - headR * 1.1} ${headR * 0.05} ${headCY - headR * 1.12}
          Q ${headR * 0.75} ${headCY - headR * 1.0} ${headR * 0.92} ${headCY - headR * 0.4}
          Q ${headR * 0.5} ${headCY - headR * 0.6} ${-headR * 0.2} ${headCY - headR * 0.55}
          Q ${-headR * 0.65} ${headCY - headR * 0.6} ${-headR * 0.82} ${headCY - headR * 0.12} Z`} fill={color} />
      );
    case "side":
      return (
        <path d={`M ${-headR * 0.95} ${headCY - headR * 0.5} Q ${-headR * 0.55} ${headCY - headR * 1.3} ${headR * 0.25} ${headCY - headR * 1.1}
          Q ${headR * 0.95} ${headCY - headR * 0.95} ${headR * 0.95} ${headCY - headR * 0.3}
          Q ${headR * 0.55} ${headCY - headR * 0.5} ${headR * 0.18} ${headCY - headR * 0.35}
          Q ${-headR * 0.22} ${headCY - headR * 0.15} ${-headR * 0.58} ${headCY - headR * 0.3} Z`} fill={color} />
      );
    case "crop":
    default:
      return (
        <g>
          <path d={`M ${-headR * 0.95} ${headCY - headR * 0.3} Q ${-headR * 0.6} ${headCY - headR * 1.15} ${headR * 0.15} ${headCY - headR * 1.12}
            Q ${headR * 0.85} ${headCY - headR * 1.0} ${headR * 0.95} ${headCY - headR * 0.3}
            Q ${headR * 0.4} ${headCY - headR * 0.55} ${-headR * 0.15} ${headCY - headR * 0.5}
            Q ${-headR * 0.55} ${headCY - headR * 0.48} ${-headR * 0.75} ${headCY - headR * 0.1} Z`} fill={color} />
          <path d={`M ${-headR * 0.7} ${headCY - headR * 0.55} Q ${-headR * 0.4} ${headCY - headR * 0.85} ${headR * 0.05} ${headCY - headR * 0.8}`} fill="none" stroke={light} strokeWidth={headR * 0.08} opacity="0.45" strokeLinecap="round" />
        </g>
      );
  }
}

function renderLegs(art: RaceArt, hipY: number, legLen: number, hipW: number) {
  const legW = hipW * 0.62;
  const bootTop = -Math.min(38, legLen * 0.28);
  return (
    <g>
      <path d={`M ${-hipW} ${hipY} L ${-hipW * 0.1} ${hipY} L ${-hipW * 0.14} ${bootTop} L ${-hipW * 1.0} ${bootTop} Z`} fill={mix(art.boot, art.cloth, 0.2)} />
      <path d={`M ${hipW} ${hipY} L ${hipW * 0.1} ${hipY} L ${hipW * 0.14} ${bootTop} L ${hipW * 1.0} ${bootTop} Z`} fill={mix(art.boot, art.cloth, 0.2)} />
      <rect x={-hipW * 1.02} y={bootTop} width={legW} height={-bootTop} rx={5} fill={art.boot} />
      <rect x={hipW * 1.02 - legW} y={bootTop} width={legW} height={-bootTop} rx={5} fill={art.boot} />
      <rect x={-hipW * 1.02} y={bootTop} width={legW} height={9} rx={3} fill={art.trim} opacity="0.55" />
      <rect x={hipW * 1.02 - legW} y={bootTop} width={legW} height={9} rx={3} fill={art.trim} opacity="0.55" />
      <ellipse cx={-hipW * 0.54} cy={-3} rx={legW * 0.62} ry={6} fill={art.boot} />
      <ellipse cx={hipW * 0.54} cy={-3} rx={legW * 0.62} ry={6} fill={art.boot} />
    </g>
  );
}

function renderTorso(
  art: RaceArt,
  uid: string,
  shoulderY: number,
  hipY: number,
  shoulderW: number,
  hipW: number,
) {
  return (
    <g>
      <path
        d={`M ${-shoulderW} ${shoulderY + 10} Q ${-shoulderW * 0.9} ${shoulderY - 8} ${-shoulderW * 0.45} ${shoulderY - 6}
            L ${shoulderW * 0.45} ${shoulderY - 6} Q ${shoulderW * 0.9} ${shoulderY - 8} ${shoulderW} ${shoulderY + 10}
            L ${hipW} ${hipY} L ${-hipW} ${hipY} Z`}
        fill={`url(#${uid}-cloth)`}
      />
      <path d={`M ${-shoulderW * 0.5} ${shoulderY - 4} Q 0 ${shoulderY + 30} ${shoulderW * 0.5} ${shoulderY - 4}
        L ${shoulderW * 0.35} ${shoulderY + 6} Q 0 ${shoulderY + 18} ${-shoulderW * 0.35} ${shoulderY + 6} Z`} fill={art.clothDark} opacity="0.6" />
      <path d={`M ${-hipW * 1.02} ${hipY - 12} L ${hipW * 1.02} ${hipY - 12} L ${hipW * 0.98} ${hipY + 4} L ${-hipW * 0.98} ${hipY + 4} Z`} fill={art.boot} />
      <rect x={-hipW * 0.7} y={hipY} width={hipW * 1.4} height={16} rx={5} fill={art.clothDark} />
      <circle cx="0" cy={hipY + 8} r={6} fill={`url(#${uid}-metal)`} />
      <path d={`M ${-hipW * 0.95} ${hipY} L ${-hipW * 1.15} ${hipY + 28} L ${-hipW * 0.45} ${hipY + 20} Z`} fill={art.cloth} opacity="0.8" />
      <path d={`M ${hipW * 0.95} ${hipY} L ${hipW * 1.15} ${hipY + 28} L ${hipW * 0.45} ${hipY + 20} Z`} fill={art.cloth} opacity="0.8" />
      <path d={`M ${-shoulderW * 0.9} ${shoulderY + 12} Q ${-shoulderW * 0.7} ${shoulderY + 50} ${-hipW * 0.95} ${hipY - 8}`}
        fill="none" stroke={art.trim} strokeWidth="2" opacity="0.4" />
      <path d={`M ${shoulderW * 0.9} ${shoulderY + 12} Q ${shoulderW * 0.7} ${shoulderY + 50} ${hipW * 0.95} ${hipY - 8}`}
        fill="none" stroke={art.trim} strokeWidth="2" opacity="0.4" />
      <circle cx="0" cy={shoulderY + 42} r={9} fill="none" stroke={`url(#${uid}-metal)`} strokeWidth="3" opacity="0.85" />
      <path d={`M ${-6} ${shoulderY + 42} L 0 ${shoulderY + 36} L 6 ${shoulderY + 42}`} fill="none" stroke={art.trim} strokeWidth="2" opacity="0.8" />
    </g>
  );
}

function renderArms(art: RaceArt, shoulderY: number, hipY: number, shoulderW: number) {
  const handY = hipY + 14;
  return (
    <g>
      <path d={`M ${-shoulderW * 0.8} ${shoulderY + 12} Q ${-shoulderW * 1.3} ${shoulderY + 60} ${-shoulderW * 1.15} ${handY}`}
        fill="none" stroke={art.clothDark} strokeWidth={12} strokeLinecap="round" />
      <path d={`M ${shoulderW * 0.8} ${shoulderY + 12} Q ${shoulderW * 1.3} ${shoulderY + 60} ${shoulderW * 1.15} ${handY}`}
        fill="none" stroke={art.clothDark} strokeWidth={12} strokeLinecap="round" />
      <circle cx={-shoulderW * 1.15} cy={handY + 4} r={7} fill={art.skin} />
      <circle cx={shoulderW * 1.15} cy={handY + 4} r={7} fill={art.skin} />
      <rect x={-shoulderW * 1.23} y={handY - 18} width={16} height={12} rx={4} fill={art.trim} opacity="0.5" />
      <rect x={shoulderW * 1.08} y={handY - 18} width={16} height={12} rx={4} fill={art.trim} opacity="0.5" />
      <path d={`M ${-shoulderW * 0.82} ${shoulderY + 10} Q ${-shoulderW * 1.1} ${shoulderY + 22} ${-shoulderW * 1.24} ${shoulderY + 28}`}
        fill="none" stroke={art.trim} strokeWidth="3" opacity="0.6" />
      <path d={`M ${shoulderW * 0.82} ${shoulderY + 10} Q ${shoulderW * 1.1} ${shoulderY + 22} ${shoulderW * 1.24} ${shoulderY + 28}`}
        fill="none" stroke={art.trim} strokeWidth="3" opacity="0.6" />
      <circle cx={-shoulderW * 0.95} cy={shoulderY + 102} r={3.5} fill={art.trim} opacity="0.4" />
      <circle cx={shoulderW * 0.95} cy={shoulderY + 102} r={3.5} fill={art.trim} opacity="0.4" />
    </g>
  );
}
