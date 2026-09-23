"""Concrete corruption generators (plan §6).

Implemented: gaussian-noise, jpeg-compression, defocus-blur, motion-blur, low-light,
exposure-change, dynamic-objects. frame-drop is stream-level (see pregenerate).

Deps: numpy (+ optional cv2/Pillow). Import never hard-fails without imaging backends.
"""

from __future__ import annotations

import io
import numpy as np

from .base import Corruption, register

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


# --- Photometric / blur -----------------------------------------------------
@register
class GaussianNoise(Corruption):
    name = "gaussian-noise"
    _SIGMA = {1: 5, 2: 12, 3: 22, 4: 38, 5: 60}

    def params(self, severity: int) -> dict:
        return {"sigma": self._SIGMA[severity]}

    def apply(self, image, severity, rng):
        sigma = self._SIGMA[severity]
        noise = rng.normal(0.0, sigma, size=image.shape)
        return _clip8(image.astype(np.float32) + noise)


@register
class JpegCompression(Corruption):
    name = "jpeg-compression"
    _QUALITY = {1: 80, 2: 60, 3: 40, 4: 22, 5: 10}

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
    _RADIUS = {1: 1, 2: 2, 3: 3, 4: 5, 5: 8}

    def params(self, severity: int) -> dict:
        return {"sigma_px": self._RADIUS[severity]}

    def apply(self, image, severity, rng):
        sigma = self._RADIUS[severity]
        if _HAVE_CV2:
            k = 2 * (3 * sigma) + 1
            return cv2.GaussianBlur(image, (k, k), sigmaX=sigma)
        r = 3 * sigma
        xs = np.arange(-r, r + 1)
        g = np.exp(-(xs**2) / (2 * sigma**2))
        g /= g.sum()
        out = image.astype(np.float32)
        out = np.apply_along_axis(lambda m: np.convolve(m, g, mode="same"), 0, out)
        out = np.apply_along_axis(lambda m: np.convolve(m, g, mode="same"), 1, out)
        return _clip8(out)


@register
class MotionBlur(Corruption):
    name = "motion-blur"
    _KERNEL = {1: 3, 2: 7, 3: 13, 4: 21, 5: 31}

    def params(self, severity: int) -> dict:
        return {"kernel_px": self._KERNEL[severity]}

    def apply(self, image, severity, rng):
        k = self._KERNEL[severity]
        kernel = np.zeros((k, k), dtype=np.float32)
        kernel[k // 2, :] = 1.0 / k
        if _HAVE_CV2:
            return cv2.filter2D(image, -1, kernel)
        # numpy fallback: horizontal box blur via separable convolve
        out = image.astype(np.float32)
        box = np.ones(k, dtype=np.float32) / k
        for c in range(out.shape[2] if out.ndim == 3 else 1):
            plane = out[..., c] if out.ndim == 3 else out
            blurred = np.apply_along_axis(lambda m: np.convolve(m, box, mode="same"), 1, plane)
            if out.ndim == 3:
                out[..., c] = blurred
            else:
                out = blurred
        return _clip8(out)


@register
class LowLight(Corruption):
    name = "low-light"
    _GAIN = {1: 0.8, 2: 0.6, 3: 0.4, 4: 0.25, 5: 0.12}

    def params(self, severity: int) -> dict:
        return {"gain": self._GAIN[severity]}

    def apply(self, image, severity, rng):
        gain = self._GAIN[severity]
        # Darken then add Poisson-Gaussian read/shot noise (approximate).
        dark = image.astype(np.float32) * gain
        # shot: scale so mean ≈ photon count proxy; read noise grows as scene darkens
        lam = np.clip(dark, 0, 255)
        shot = rng.poisson(lam).astype(np.float32)
        read_sigma = 2.0 + 6.0 * (1.0 - gain)
        read = rng.normal(0.0, read_sigma, size=image.shape)
        return _clip8(shot + read)


@register
class ExposureChange(Corruption):
    name = "exposure-change"
    _STEP = {1: 0.2, 2: 0.4, 3: 0.7, 4: 1.2, 5: 2.0}

    def params(self, severity: int) -> dict:
        return {"step": self._STEP[severity]}

    def apply(self, image, severity, rng):
        step = self._STEP[severity]
        # Random direction: over- or under-expose, with hard clipping.
        sign = 1.0 if rng.random() < 0.5 else -1.0
        factor = (1.0 + sign * step) if sign > 0 else max(1.0 / (1.0 + step), 0.05)
        return _clip8(image.astype(np.float32) * factor)


@register
class DynamicObjects(Corruption):
    name = "dynamic-objects"
    _RANGES = {s: {"patches": s, "area_frac": 0.05 * s} for s in (1, 2, 3, 4, 5)}

    def params(self, severity: int) -> dict:
        return dict(self._RANGES[severity])

    def apply(self, image, severity, rng):
        out = image.copy()
        h, w = out.shape[:2]
        n = self._RANGES[severity]["patches"]
        area = self._RANGES[severity]["area_frac"]
        for _ in range(n):
            ph = max(2, int(round(np.sqrt(area) * h * rng.uniform(0.6, 1.4))))
            pw = max(2, int(round(np.sqrt(area) * w * rng.uniform(0.6, 1.4))))
            ph = min(ph, h)
            pw = min(pw, w)
            y0 = int(rng.integers(0, max(h - ph, 1)))
            x0 = int(rng.integers(0, max(w - pw, 1)))
            color = rng.integers(0, 256, size=(3,), dtype=np.int64)
            out[y0:y0 + ph, x0:x0 + pw] = color.astype(np.uint8)
        return out


@register
class FrameDrop(Corruption):
    """Stream-level only — apply() is a no-op passthrough for image pipelines."""

    name = "frame-drop"
    _DROP = {1: 0.02, 2: 0.05, 3: 0.10, 4: 0.20, 5: 0.35}

    def params(self, severity: int) -> dict:
        return {"drop_frac": self._DROP[severity]}

    def apply(self, image, severity, rng):
        return image

    def drop_mask(self, n_frames: int, severity: int, rng: np.random.Generator) -> np.ndarray:
        """True = keep frame. Always keeps first and last frame."""
        frac = self._DROP[severity]
        keep = np.ones(n_frames, dtype=bool)
        if n_frames <= 2:
            return keep
        n_drop = int(round(frac * n_frames))
        candidates = np.arange(1, n_frames - 1)
        if n_drop <= 0 or len(candidates) == 0:
            return keep
        n_drop = min(n_drop, len(candidates))
        drop_idx = rng.choice(candidates, size=n_drop, replace=False)
        keep[drop_idx] = False
        return keep
