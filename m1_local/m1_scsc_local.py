"""Морфометрия рельефа (in-memory) и ядро SCS+C."""
import numpy as np
import rasterio
from scipy.stats import pearsonr
from rasterio.warp import reproject, Resampling


def reproject_to_target_grid(src_path: str, ref_profile: dict,
                             resampling_method: Resampling) -> np.ndarray:
    """Жесткое приведение растра к референсной геометрии B04."""
    dst = np.zeros((ref_profile['height'], ref_profile['width']), dtype=np.float32)
    with rasterio.open(src_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_profile['transform'],
            dst_crs=ref_profile['crs'],
            resampling=resampling_method,
        )
    return dst


def compute_slope_aspect(dem: np.ndarray,
                         transform: rasterio.transform.Affine
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Уклон и экспозиция через центральные разности (учет знака dy)."""
    dx = abs(float(transform.a))
    dy = abs(float(transform.e))

    gx = (dem[1:-1, 2:] - dem[1:-1, :-2]) / (2.0 * dx)
    gy = -(dem[2:, 1:-1] - dem[:-2, 1:-1]) / (2.0 * dy)

    slope_inner = np.arctan(np.sqrt(np.square(gx, dtype=np.float64) + np.square(gy, dtype=np.float64))).astype(np.float32)
    aspect_inner = np.mod(np.arctan2(gx, gy), 2 * np.pi)

    slope = np.pad(slope_inner, pad_width=1, mode='edge')
    aspect = np.pad(aspect_inner, pad_width=1, mode='edge')
    return slope, aspect


def compute_cos_i(sun_zenith_rad: float, sun_azimuth_rad: float,
                  slope_rad: np.ndarray, aspect_rad: np.ndarray) -> np.ndarray:
    """cos(i) по сферической тригонометрии."""
    cos_i = (np.cos(sun_zenith_rad) * np.cos(slope_rad)
             + np.sin(sun_zenith_rad) * np.sin(slope_rad)
             * np.cos(sun_azimuth_rad - aspect_rad))
    return np.clip(cos_i, 0.0, 1.0)


def calibrate_c(dn: np.ndarray, cos_i: np.ndarray, mask: np.ndarray, params: dict, boa_offset: int = 0) -> tuple[float, float, float, int]:
    # Вычитаем радиометрическое смещение ESA (BOA_ADD_OFFSET = -1000)
    if boa_offset != 0:
        dn = dn.astype(np.float32) + float(boa_offset)
    valid = mask & np.isfinite(dn) & np.isfinite(cos_i) & (cos_i > 0.0)
    n = int(valid.sum())
    
    if n < params['min_valid_pixels']:
        print(f"  ❌ FAIL: мало пикселей (n={n} < {params['min_valid_pixels']})")
        return params['c_default'], -999.0, -999.0, 0
    
    try:
        a, b = np.polyfit(cos_i[valid], dn[valid], 1)
    except (np.linalg.LinAlgError, ValueError) as e:
        print(f"  ❌ FAIL: ошибка регрессии ({e})")
        return params['c_default'], -999.0, -999.0, 0
    
    print(f"  🔍 Регрессия: a={a:.6f}, b={b:.4f}, n={n}")
    
    if abs(a) < 1e-6:
        print(f"  ❌ FAIL: наклон a={a:.8f} слишком мал (< 1e-6)")
        return params['c_default'], -999.0, -999.0, 0
    
    c = b / a
    print(f"  🔍 Расчет C: {b:.4f} / {a:.6f} = {c:.4f}")
    
    if not (params['c_min'] < c < params['c_max']):
        print(f"  ❌ FAIL: C={c:.4f} вне диапазона ({params['c_min']}, {params['c_max']})")
        return params['c_default'], -999.0, -999.0, 0
        
    print(f"  ✅ SUCCESS: C={c:.4f}")
    return float(c), float(a), float(b), 1



def apply_scsc(dn: np.ndarray, cos_i: np.ndarray, sun_zenith_rad: float,
               slope_rad: np.ndarray, C: float, mask: np.ndarray) -> np.ndarray:
    """Применение SCS+C с защитой от деления на 0 (без in-place)."""
    num = np.cos(sun_zenith_rad) * np.cos(slope_rad) + C
    den = cos_i + C
    safe_den = np.where(den == 0.0, 1e-6, den)
    return np.where(mask, dn * (num / safe_den), dn)


def gate_pearson(dn_corr: np.ndarray, cos_i: np.ndarray,
                 mask: np.ndarray) -> tuple[float, float]:
    """Остаточная корреляция Пирсона (валидные dn_corr и cos_i)."""
    valid = mask & (dn_corr > 0) & np.isfinite(dn_corr) & np.isfinite(cos_i)
    if valid.sum() < 10:
        return -999.0, -999.0
    try:
        r, p = pearsonr(dn_corr[valid], cos_i[valid])
        return float(r), float(p)
    except Exception:
        return -999.0, -999.0