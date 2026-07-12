/**
 * Client-side hardware detection — reads the *visitor's own device* from browser
 * APIs, so the hardware readout is real per-device instead of reporting the
 * server that happens to host the API.
 *
 * Browser detection is necessarily coarser than the server-side probe
 * (auralynq/modelfit/hardware.py): there is no way to read an exact CPU model or
 * true total RAM from a web page. We surface what is reliably available —
 * logical cores, GPU (via WebGL), OS/arch — and mark the rest as approximate or
 * unavailable rather than guessing. Every field carries a `sources` flag so the
 * UI can be honest about what was actually measured.
 */

export interface ClientHardware {
  os: string; // "macOS" | "Windows" | "Linux" | "iOS" | "Android" | "unknown"
  arch: string; // "arm64" | "x86_64" | ""
  cpuCores: number | null; // navigator.hardwareConcurrency (logical)
  ramGb: number | null; // navigator.deviceMemory — coarse, Chromium-only
  ramIsLowerBound: boolean; // Chrome caps deviceMemory at 8 → "8 GB or more"
  gpu: string | null; // parsed WebGL UNMASKED_RENDERER
  gpuVendor: string | null; // "Apple" | "NVIDIA" | "AMD" | "Intel" | null
  mobile: boolean;
  browser: string;
  sources: { cores: boolean; ram: boolean; gpu: boolean; os: boolean };
}

function detectBrowser(ua: string): string {
  if (/Edg\//.test(ua)) return "Edge";
  if (/OPR\//.test(ua)) return "Opera";
  if (/Firefox\//.test(ua)) return "Firefox";
  if (/Chrome\//.test(ua)) return "Chrome";
  if (/Safari\//.test(ua)) return "Safari";
  return "browser";
}

function osFromUA(ua: string, platform: string): string {
  const s = `${ua} ${platform}`;
  if (/iPhone|iPad|iPod/i.test(s)) return "iOS";
  if (/Android/i.test(s)) return "Android";
  if (/Mac|Macintosh|Mac OS X/i.test(s)) return "macOS";
  if (/Win/i.test(s)) return "Windows";
  if (/CrOS/i.test(s)) return "ChromeOS";
  if (/Linux/i.test(s)) return "Linux";
  return "unknown";
}

function normalizeUadPlatform(p?: string): string {
  switch ((p || "").toLowerCase()) {
    case "macos":
      return "macOS";
    case "windows":
      return "Windows";
    case "linux":
      return "Linux";
    case "android":
      return "Android";
    case "chrome os":
    case "chromeos":
      return "ChromeOS";
    default:
      return p || "";
  }
}

function archFrom(architecture?: string, bitness?: string, ua?: string): string {
  const a = (architecture || "").toLowerCase();
  if (a.includes("arm")) return "arm64";
  if (a === "x86") return bitness === "64" ? "x86_64" : "x86";
  // Fallback: Apple Silicon Macs report Intel in UA, so we can't be sure here.
  if (ua && /aarch64|arm64/i.test(ua)) return "arm64";
  if (ua && /x86_64|Win64|WOW64|x64/i.test(ua)) return "x86_64";
  return "";
}

/** Parse a WebGL UNMASKED_RENDERER string down to a human GPU name + vendor. */
function parseGpu(raw: string): { name: string; vendor: string | null } {
  let s = raw.trim();
  // Chrome wraps everything in "ANGLE (vendor, <renderer>, <api>)".
  const angle = s.match(/^ANGLE \((.*)\)$/i);
  if (angle) {
    const parts = angle[1].split(",").map((p) => p.trim());
    // The middle segment holds the renderer; prefer the longest descriptive one.
    s = parts.sort((a, b) => b.length - a.length)[0] || s;
  }
  s = s
    .replace(/ANGLE Metal Renderer:\s*/i, "")
    .replace(/\s*\(0x[0-9a-f]+\)/i, "")
    .replace(/\s*Direct3D.*$/i, "")
    .replace(/\s*OpenGL.*$/i, "")
    .replace(/\s*Metal\s*-?\s*.*$/i, (m) => (/Apple/i.test(m) ? m : ""))
    .replace(/\s*vs_\d.*$/i, "")
    .replace(/\bMesa\b\s*/i, "")
    .replace(/\s+/g, " ")
    .trim();
  let vendor: string | null = null;
  if (/apple/i.test(s)) vendor = "Apple";
  else if (/nvidia|geforce|rtx|gtx/i.test(s)) vendor = "NVIDIA";
  else if (/amd|radeon/i.test(s)) vendor = "AMD";
  else if (/intel/i.test(s)) vendor = "Intel";
  return { name: s || raw, vendor };
}

function detectGpu(): { name: string; vendor: string | null } | null {
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    if (!gl) return null;
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const raw = ext
      ? (gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) as string)
      : (gl.getParameter(gl.RENDERER) as string);
    if (!raw) return null;
    return parseGpu(raw);
  } catch {
    return null;
  }
}

export async function detectClientHardware(): Promise<ClientHardware> {
  const nav = navigator as Navigator & {
    deviceMemory?: number;
    userAgentData?: {
      mobile?: boolean;
      platform?: string;
      getHighEntropyValues?: (hints: string[]) => Promise<Record<string, string>>;
    };
  };
  const ua = nav.userAgent || "";
  const platform = (nav as unknown as { platform?: string }).platform || "";

  let os = osFromUA(ua, platform);
  let arch = archFrom(undefined, undefined, ua);
  let osFromApi = false;

  const uad = nav.userAgentData;
  if (uad?.getHighEntropyValues) {
    try {
      const hev = await uad.getHighEntropyValues([
        "architecture",
        "bitness",
        "platform",
        "platformVersion",
        "model",
      ]);
      const p = normalizeUadPlatform(hev.platform || uad.platform);
      if (p) {
        os = p;
        osFromApi = true;
      }
      const a = archFrom(hev.architecture, hev.bitness, ua);
      if (a) arch = a;
    } catch {
      /* fall back to UA parsing */
    }
  }

  const cpuCores = typeof nav.hardwareConcurrency === "number" ? nav.hardwareConcurrency : null;
  const ramRaw = typeof nav.deviceMemory === "number" ? nav.deviceMemory : null;
  const gpu = detectGpu();

  return {
    os,
    arch,
    cpuCores,
    ramGb: ramRaw,
    ramIsLowerBound: ramRaw != null && ramRaw >= 8,
    gpu: gpu?.name ?? null,
    gpuVendor: gpu?.vendor ?? null,
    mobile: Boolean(uad?.mobile) || /Mobi|Android/i.test(ua),
    browser: detectBrowser(ua),
    sources: {
      cores: cpuCores != null,
      ram: ramRaw != null,
      gpu: gpu != null,
      os: osFromApi || os !== "unknown",
    },
  };
}

/**
 * Best-effort per-device fit for a model whose memory footprint is `needGb`
 * (a property of the model, not the host). Uses detected RAM when available;
 * returns `unknown` when the browser won't reveal enough to judge.
 */
export function clientFit(
  hw: ClientHardware,
  needGb: number | null | undefined,
): "runs" | "tight" | "too_big" | "unknown" {
  if (needGb == null || hw.ramGb == null) return "unknown";
  // Chrome caps deviceMemory at 8; if we only know "≥8" and the model fits in 8,
  // it's a safe "runs"; larger models are genuinely unknown at that ceiling.
  const cap = hw.ramGb;
  if (needGb <= cap * 0.7) return "runs";
  if (needGb <= cap) return hw.ramIsLowerBound ? "unknown" : "tight";
  return hw.ramIsLowerBound ? "unknown" : "too_big";
}
