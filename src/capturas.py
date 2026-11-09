"""Genera las evidencias (figuras) del artículo en docs/capturas/.

- Gráficos plotly            -> PNG con kaleido              (docs/capturas/figura_NN_clave.png)
- Tablas de la app            -> captura del elemento con Playwright
- Páginas y secciones de la app -> capturas con Playwright    (docs/capturas/app/)
- Fragmentos de código y SQL  -> imagen legible renderizada con Playwright
- Lo que no se puede capturar automáticamente (Neon, Power BI) queda como pendiente en resultados.md.

La numeración sale de src.utils.FIGURAS, la misma que usan la app y docs/resultados.md.
Ninguna captura muestra credenciales: la app nunca imprime DATABASE_URL, y por defecto se ejecuta
con FUENTE_DATOS=local (el original desde la copia CSV), sin conectarse a Neon.

Uso:
    python -m src.capturas            # todas las figuras disponibles
    python -m src.capturas --neon     # la app lee desde Neon (requiere .env)
"""
from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

from src import diagnostico
from src.utils import DOCS, FIGURAS, ROOT, SQL_DIR, figura

CAPTURAS = DOCS / "capturas"
CAPTURAS_APP = CAPTURAS / "app"
PUERTO = 8599

# Cómo se produce cada figura del catálogo
APP = {  # clave -> página de la app donde está el contenedor "figura_<clave>"
    "estructura": "Diagnostico",
    "duplicados_muestra": "Diagnostico",
    "inconsistencias": "Diagnostico",
    "informe": "Diagnostico",
}
PLOTLY = {  # clave -> función que construye la figura a partir de los resultados
    **{k: ("diagnostico", f) for k, f in diagnostico.FIGURAS_PLOTLY.items()},
}
PENDIENTES = {"neon_proyecto", "neon_verificacion"}  # capturas manuales (Neon, Power BI)
PAGINAS = ["", "Diagnostico"]  # páginas que se capturan completas y por secciones


def ruta_figura(clave: str) -> Path:
    n, _ = figura(clave)
    return CAPTURAS / f"figura_{n:02d}_{clave}.png"


# =============================================================================
# Código y SQL
# =============================================================================
def _bloque_sql(archivo: str, inicio: str) -> str:
    """Extrae del archivo SQL la sentencia que empieza con `inicio` (hasta el ';' que la cierra),
    junto con los comentarios que la preceden."""
    lineas = (SQL_DIR / archivo).read_text(encoding="utf-8").splitlines()
    i = next(n for n, l in enumerate(lineas) if l.startswith(inicio))
    j = i
    while not lineas[j].rstrip().endswith(";"):
        j += 1
    k = i
    while k > 0 and lineas[k - 1].startswith("--"):
        k -= 1
    return "\n".join(lineas[k:j + 1])


def _funcion_python(ruta: Path, nombre: str) -> str:
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    i = next(n for n, l in enumerate(lineas) if l.startswith(f"def {nombre}("))
    j = i + 1
    while j < len(lineas) and (not lineas[j] or lineas[j].startswith((" ", "\t"))):
        j += 1
    return "\n".join(lineas[i:j]).rstrip()


CODIGO = {
    "sql_create_raw": ("sql/01_schema.sql", "sql",
                       lambda: _bloque_sql("01_schema.sql", "CREATE TABLE IF NOT EXISTS delitos_raw")),
}

_SQL_CLAVE = r"\b(CREATE|TABLE|IF|NOT|EXISTS|PRIMARY|KEY|REFERENCES|NULL|CHECK|IN|BETWEEN|AND|OR|DEFAULT|SELECT|FROM|WHERE|GROUP|BY|ORDER|JOIN|LEFT|ON|AS|CASE|WHEN|THEN|ELSE|END|INDEX|COMMENT|IS|CONSTRAINT|DROP|CASCADE|VIEW|COUNT|USING)\b"
_SQL_TIPO = r"\b(INTEGER|TEXT|SMALLINT|NUMERIC|VARCHAR|DATE|BOOLEAN|TIMESTAMPTZ)\b"
_PY_CLAVE = r"\b(def|return|if|else|elif|for|in|not|and|or|None|True|False|import|from|as|with|lambda|is)\b"


def _resaltar(codigo: str, lenguaje: str) -> str:
    """Resaltado simple: comentarios, cadenas, palabras clave y tipos (sin dependencias extra)."""
    salida = []
    for linea in codigo.splitlines():
        marca = "--" if lenguaje == "sql" else "#"
        pos = linea.find(marca)
        cuerpo, comentario = (linea[:pos], linea[pos:]) if pos >= 0 else (linea, "")
        if lenguaje == "python" and cuerpo.strip().startswith(('"""', "'")):
            salida.append(f'<span class="c">{html.escape(linea)}</span>')
            continue
        partes = re.split(r"('[^']*'|\"[^\"]*\")", cuerpo)
        cuerpo_html = ""
        for p in partes:
            if p[:1] in ("'", '"'):
                cuerpo_html += f'<span class="s">{html.escape(p)}</span>'
            else:
                e = html.escape(p)
                if lenguaje == "sql":
                    e = re.sub(_SQL_TIPO, r'<span class="t">\1</span>', e)
                    e = re.sub(_SQL_CLAVE, r'<span class="k">\1</span>', e)
                else:
                    e = re.sub(_PY_CLAVE, r'<span class="k">\1</span>', e)
                cuerpo_html += e
        if comentario:
            cuerpo_html += f'<span class="c">{html.escape(comentario)}</span>'
        salida.append(cuerpo_html)
    filas = "".join(f"<tr><td class='n'>{i}</td><td>{l or ' '}</td></tr>" for i, l in enumerate(salida, 1))
    return filas


def html_codigo(archivo: str, lenguaje: str, codigo: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      body {{margin:0; background:#fcfcfb; font-family: system-ui, 'Segoe UI', sans-serif;}}
      #codigo {{display:inline-block; margin:16px; border:1px solid #e1e0d9; border-radius:8px; overflow:hidden; background:#fff;}}
      .cab {{background:#f3f2ee; color:#52514e; font-size:13px; padding:8px 14px; border-bottom:1px solid #e1e0d9;}}
      table {{border-collapse:collapse; font-family: Consolas, 'Cascadia Mono', monospace; font-size:14px; line-height:1.45; margin:8px 0;}}
      td {{padding:0 14px 0 0; white-space:pre; color:#0b0b0b; vertical-align:top;}}
      td.n {{color:#b5b3ab; text-align:right; padding:0 12px 0 14px; user-select:none;}}
      .k {{color:#184f95; font-weight:600;}} .t {{color:#8a3ffc;}} .s {{color:#a8481c;}} .c {{color:#6f6e69; font-style:italic;}}
    </style></head><body><div id="codigo"><div class="cab">{html.escape(archivo)}</div>
    <table>{_resaltar(codigo, lenguaje)}</table></div></body></html>"""


# =============================================================================
# App de Streamlit
# =============================================================================
def _iniciar_app(neon: bool) -> subprocess.Popen:
    env = {**os.environ, "FUENTE_DATOS": "auto" if neon else "local"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "Home.py"),
         "--server.port", str(PUERTO), "--server.headless", "true"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(90):
        try:
            if urllib.request.urlopen(f"http://localhost:{PUERTO}/_stcore/health", timeout=2).status == 200:
                return proc
        except Exception:  # noqa: BLE001 - el servidor aún no responde
            time.sleep(1)
    proc.terminate()
    raise RuntimeError("La aplicación de Streamlit no arrancó.")


def _esperar_app(page) -> None:
    """Espera a que Streamlit termine de ejecutar el script y a que plotly dibuje los gráficos."""
    page.wait_for_selector('[data-testid="stAppViewContainer"]', timeout=60_000)
    page.wait_for_timeout(1500)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=120_000)
    page.wait_for_timeout(2500)


_CSS_CAPTURA = """
  header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
  [data-testid="stStatusWidget"] {display: none !important;}
"""


def _ajustar_alto(page) -> None:
    """Agranda el viewport hasta el alto del contenido: Streamlit desplaza un contenedor interno,
    por lo que una captura de página completa solo mostraría la parte visible."""
    alto = page.evaluate(
        "() => document.querySelector('[data-testid=\"stMainBlockContainer\"]').scrollHeight")
    page.set_viewport_size({"width": 1440, "height": int(alto) + 120})
    page.wait_for_timeout(1500)


def capturar_app(claves_app: list[str], neon: bool) -> list[Path]:
    from playwright.sync_api import sync_playwright

    generadas = []
    CAPTURAS_APP.mkdir(parents=True, exist_ok=True)
    for viejo in CAPTURAS_APP.glob("*.png"):  # evita que queden capturas de secciones que ya no existen
        viejo.unlink()
    proc = _iniciar_app(neon)
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            page = nav.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2, locale="es-CO")
            for pagina in PAGINAS:
                page.goto(f"http://localhost:{PUERTO}/{pagina}")
                _esperar_app(page)
                page.add_style_tag(content=_CSS_CAPTURA)
                _ajustar_alto(page)
                nombre = pagina.lower() or "inicio"
                main = page.locator('[data-testid="stMain"]')
                destino = CAPTURAS_APP / f"{nombre}_completa.png"
                main.screenshot(path=str(destino))
                generadas.append(destino)

                # Una captura por sección: se recorta la captura completa desde cada encabezado h2
                # hasta el siguiente (posiciones relativas al área principal, en píxeles de la imagen).
                from PIL import Image

                caja_main = main.bounding_box()
                escala = 2  # device_scale_factor
                completa = Image.open(destino)
                hs = [(h.inner_text().split("\n")[0], h.bounding_box())
                      for h in main.locator('[data-testid="stHeading"] h2').all() if h.is_visible()]
                hs = sorted([h for h in hs if h[1] and h[1]["height"] > 0], key=lambda h: h[1]["y"])
                for i, (texto, caja) in enumerate(hs):
                    y0 = max(caja["y"] - caja_main["y"] - 12, 0) * escala
                    y1 = ((hs[i + 1][1]["y"] - caja_main["y"] - 12) * escala) if i + 1 < len(hs) else completa.height
                    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
                    slug = re.sub(r"[^a-z0-9]+", "_", sin_tildes.lower())[:40].strip("_")
                    seccion = CAPTURAS_APP / f"{nombre}_{i + 1:02d}_{slug}.png"
                    completa.crop((0, int(y0), completa.width, int(y1))).save(seccion)
                    generadas.append(seccion)

                # Tablas presentadas como figuras numeradas
                for clave in [k for k in claves_app if APP[k] == pagina]:
                    destino = ruta_figura(clave)
                    page.locator(f".st-key-figura_{clave}").screenshot(path=str(destino))
                    generadas.append(destino)
                page.set_viewport_size({"width": 1440, "height": 1000})
            nav.close()
    finally:
        proc.terminate()
    return generadas


def capturar_codigo(claves: list[str]) -> list[Path]:
    from playwright.sync_api import sync_playwright

    generadas = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(device_scale_factor=2)
        for clave in claves:
            archivo, lenguaje, extraer = CODIGO[clave]
            page.set_content(html_codigo(archivo, lenguaje, extraer()))
            destino = ruta_figura(clave)
            page.locator("#codigo").screenshot(path=str(destino))
            generadas.append(destino)
        nav.close()
    return generadas


def exportar_plotly(claves: list[str]) -> list[Path]:
    resultados = {"diagnostico": diagnostico.cargar_resultados() or diagnostico.diagnosticar()}
    generadas = []
    for clave in claves:
        modulo, construir = PLOTLY[clave]
        fig = construir(resultados[modulo])
        destino = ruta_figura(clave)
        fig.write_image(destino, width=1100, height=fig.layout.height or 450, scale=2)
        generadas.append(destino)
    return generadas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--neon", action="store_true", help="la app lee los datos desde Neon")
    a = ap.parse_args()
    CAPTURAS.mkdir(parents=True, exist_ok=True)

    claves = [k for k, _ in FIGURAS]
    hechas = []
    hechas += exportar_plotly([k for k in claves if k in PLOTLY])
    hechas += capturar_codigo([k for k in claves if k in CODIGO])
    hechas += capturar_app([k for k in claves if k in APP], a.neon)
    for ruta in hechas:
        print(ruta.relative_to(ROOT))
    pendientes = [k for k in claves if k in PENDIENTES]
    if pendientes:
        print("\nCapturas manuales pendientes:")
        for k in pendientes:
            n, t = figura(k)
            print(f"  Figura {n}. {t}  ->  {ruta_figura(k).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
