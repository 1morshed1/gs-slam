"""Concrete corruption generators (plan §6).

Three are implemented for real (rig-runnable today, no SLAM deps): gaussian-noise,
jpeg-compression, defocus-blur. The rest are declared stubs with their sev1→5
parameter ranges filled in so the filler only writes the kernel, not the design.

Deps: numpy (+ optional cv2/Pillow for a couple). Kept minimal so this module runs on
the office rig immediately for corrupted-dataset pre-generation.
"""

from __future__ import annotations

import io
import numpy as np

from .base import Corruption, register

# Optional imaging backends — degrade gracefully so import never hard-fails.
try:
    import cv2  # type: ignore
    _HAVE_CV2 = True
except Exception:  # pragma: no cover
    _HAVE_CV2 = False

try:
    from PIL import Image  # type: ignore
    _HAVE_PIL = True
except Exception:  # pragma: no cover
    _HAVE_PIL = False


def _clip8(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0, 255).astype(np.uint8)


# --- Implemented ------------------------------------------------------------
@register
class GaussianNoise(Corruption):
    name = "gaussian-noise"
    _SIGMA = {1: 5, 2: 12, 3: 22, 4: 38, 5: 60}  # per-channel std, 0..255 scale

    def params(self, severity: int) -> dict:
        return {"sigma": self._SIGMA[severity]}

    def apply(self, image, severity, rng):
        sigma = self._SIGMA[severity]
        noise = rng.normal(0.0, sigma, size=image.shape)
        return _clip8(image.astype(np.float32) + noise)


@register
class JpegCompression(Corruption):
    name = "jpeg-compression"
    _QUALITY = {1: 80, 2: 60, 3: 40, 4: 22, 5: 10}  # JPEG quality, lower = worse

    def params(self, severity: int) -> dict:
        return {"quality": self._QUALITY[severity]}

    def apply(self, image, severity, rng):
        q = self._QUALITY[severity]
        if _HAVE_CV2:
            ok, buf = cv2.imencode(".jpg", image[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, q])
            if not ok:
                raise RuntimeError("cv2 jpeg encode failed")
            dec = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            return np.ascontiguousarray(dec[..., ::-1])
        if _HAVE_PIL:
            b = io.BytesIO()
            Image.fromarray(image).save(b, format="JPEG", quality=q)
            b.seek(0)
            return np.asarray(Image.open(b).convert("RGB"))
        raise RuntimeError("jpeg-compression needs cv2 or Pillow installed")


@register
class DefocusBlur(Corruption):
    name = "defocus-blur"
    _RADIUS = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8}  # gaussian sigma px

    def params(self, severity: int) -> dict:
        return {"sigma_px": self._RADIUS[severity]}

    def apply(self, image, severity, rng):
        sigma = self._RADIUS[severity]
        if _HAVE_CV2:
            k = 2 * (3 * sigma) + 1
            return cv2.GaussianBlur(image, (k, k), sigmaX=sigma)
        # numpy separable fallback (no cv2): 1D gaussian along each axis.
        r = 3 * sigma
        xs = np.arange(-r, r + 1)
        g = np.exp(-(xs**2) / (2 * sigma**2))
        g /= g.sum()
        out = image.astype(np.float32)
        out = np.apply_along_axis(lambda m: np.convolve(m, g, mode="same"), 0, out)
        out = np.apply_along_axis(lambda m: np.convolve(m, g, mode="same"), 1, out)
        return _clip8(out)


# --- Declared stubs: ranges set, kernel TODO --------------------------------
class _Stub(Corruption):
    _RANGES: dict[int, dict] = {}

    def params(self, severity: int) -> dict:
        return self._RANGES.get(severity, {})

    def apply(self, image, severity, rng):
        raise NotImplementedError(f"{self.name}: params fixed, kernel TODO (plan §6)")


@register
class MotionBlur(_Stub):
    name = "motion-blur"
    # Fixed-kernel variant, px length. Physically-motivated variant scales by GT pose velocity.
    _RANGES = {1: {"kernel_px": 3}, 2: {"kernel_px": 7}, 3: {"kernel_px": 13},
               4: {"kernel_px": 21}, 5: {"kernel_px": 31}}


@register
class LowLight(_Stub):
    name = "low-light"
    # gain/gamma reduction + Poisson-Gaussian sensor noise (pair darkening with realistic noise).
    _RANGES = {1: {"gain": 0.8}, 2: {"gain": 0.6}, 3: {"gain": 0.4},
               4: {"gain": 0.25}, 5: {"gain": 0.12}}


@register
class ExposureChange(_Stub):
    name = "exposure-change"
    # sudden gain step / over-under ramp / clipping — tests photometric front-ends.
    _RANGES = {1: {"step": 0.2}, 2: {"step": 0.4}, 3: {"step": 0.7},
               4: {"step": 1.2}, 5: {"step": 2.0}}


@register
class DynamicObjects(_Stub):
    name = "dynamic-objects"
    # synthetic moving-patch insertion for controlled severity; native dynamic splits used separately.
    _RANGES = {s: {"patches": s, "area_frac": 0.05 * s} for s in (1, 2, 3, 4, 5)}


@register
class FrameDrop(_Stub):
    name = "frame-drop"
    # drop k% of frames — stresses tracking continuity. Applied at stream level, not per-image.
    _RANGES = {1: {"drop_frac": 0.02}, 2: {"drop_frac": 0.05}, 3: {"drop_frac": 0.10},
               4: {"drop_frac": 0.20}, 5: {"drop_frac": 0.35}}
