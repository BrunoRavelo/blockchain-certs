"""
Generación de PDF de Certificado Total de Estudios.

El PDF es informativo — su hash no se almacena en la cadena.
Paleta Anáhuac: naranja (#E87722) + café oscuro (#5C2D0E)
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


# ── Paletas ──────────────────────────────────────────────────────────────────

def _paleta(institucion: str) -> dict:
    return {
        'primario':      colors.HexColor('#5C2D0E'),  # café oscuro
        'secundario':    colors.HexColor('#E87722'),  # naranja Anáhuac
        'acento':        colors.HexColor('#F4A460'),  # naranja claro
        'acento_claro':  colors.HexColor('#FDDCB5'),  # crema
        'fondo_caja':    colors.HexColor('#FEF4E8'),  # crema suave
    }


# ── Función principal ─────────────────────────────────────────────────────────

def generar_pdf_certificado(datos: dict) -> bytes:
    buf  = BytesIO()
    W, H = A4
    c    = canvas.Canvas(buf, pagesize=A4)
    p    = _paleta(datos.get('institucion', ''))

    _draw_background(c, W, H, p)
    _draw_borders(c, W, H, p)
    _draw_header(c, W, H, datos, p)
    _draw_body(c, W, H, datos, p)
    _draw_footer(c, W, H, datos, p)

    c.save()
    return buf.getvalue()


# ── Secciones ─────────────────────────────────────────────────────────────────

def _draw_background(c, W, H, p):
    c.setFillColor(colors.white)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.setFillColor(p['primario'])
    c.rect(0, H - 1.6*cm, W, 1.6*cm, fill=1, stroke=0)
    c.rect(0, 0, W, 1.6*cm, fill=1, stroke=0)


def _draw_borders(c, W, H, p):
    m = 0.9*cm

    c.setStrokeColor(p['secundario'])
    c.setLineWidth(3)
    c.rect(m, m + 1.6*cm, W - 2*m, H - 2*m - 3.2*cm)

    c.setStrokeColor(p['acento'])
    c.setLineWidth(1)
    o = m + 0.35*cm
    c.rect(o, o + 1.6*cm, W - 2*o, H - 2*o - 3.2*cm)

    sz = 0.7*cm
    for x, y in [
        (m, m + 1.6*cm),
        (W - m - sz, m + 1.6*cm),
        (m, H - m - sz),
        (W - m - sz, H - m - sz),
    ]:
        c.setFillColor(p['secundario'])
        c.setStrokeColor(p['acento'])
        c.setLineWidth(0.5)
        c.rect(x, y, sz, sz, fill=1, stroke=1)
        c.setFillColor(p['primario'])
        c.circle(x + sz/2, y + sz/2, sz * 0.28, fill=1, stroke=0)


def _draw_header(c, W, H, datos, p):
    institucion = datos.get('institucion', 'Institución Universitaria')

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(W/2, H - 1.1*cm, institucion.upper())

    c.setStrokeColor(p['secundario'])
    c.setLineWidth(1.5)
    c.line(2.5*cm, H - 2.4*cm, W - 2.5*cm, H - 2.4*cm)

    c.setFillColor(p['primario'])
    c.setFont('Helvetica', 10)
    c.drawCentredString(W/2, H - 3.2*cm, 'HACE CONSTAR Y CERTIFICA QUE')

    c.setFillColor(p['secundario'])
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 3.9*cm, '— CERTIFICADO TOTAL DE ESTUDIOS —')


def _draw_body(c, W, H, datos, p):
    nombre  = datos.get('nombre', '')
    carrera = datos.get('carrera', '')
    fecha   = datos.get('fecha', '')
    bloque  = datos.get('bloque', '-')
    nfirmas = len(datos.get('firmas_validadores', []))

    # Nombre grande
    c.setFillColor(p['primario'])
    c.setFont('Helvetica-Bold', 26)
    c.drawCentredString(W/2, H - 5.4*cm, nombre)

    nom_w = c.stringWidth(nombre, 'Helvetica-Bold', 26)
    x0    = W/2 - nom_w/2 - 0.5*cm
    x1    = W/2 + nom_w/2 + 0.5*cm
    c.setStrokeColor(p['secundario'])
    c.setLineWidth(1.2)
    c.line(x0, H - 5.7*cm, x1, H - 5.7*cm)

    c.setFillColor(colors.HexColor('#333333'))
    c.setFont('Helvetica', 10)
    c.drawCentredString(W/2, H - 6.5*cm,
        'ha concluido satisfactoriamente los estudios correspondientes a la licenciatura en')

    # Nombre de la carrera
    c.setFillColor(p['primario'])
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(W/2, H - 7.3*cm, carrera)

    # Caja de fecha
    col   = W/2
    y_box = H - 8.7*cm
    bw    = 5*cm

    c.setFillColor(p['fondo_caja'])
    c.setStrokeColor(p['acento'])
    c.setLineWidth(0.5)
    c.roundRect(col - bw/2, y_box - 0.6*cm, bw, 1.3*cm, 4, fill=1, stroke=1)

    c.setFillColor(p['primario'])
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(col, y_box + 0.38*cm, 'FECHA DE EGRESO')

    c.setFillColor(colors.HexColor('#1A1A1A'))
    c.setFont('Helvetica', 10)
    c.drawCentredString(col, y_box - 0.17*cm, fecha)

    # Info blockchain
    c.setFillColor(p['primario'])
    c.setFont('Helvetica-Bold', 8.5)
    c.drawCentredString(W/2, H - 10.2*cm,
        f'Registrado en blockchain · Bloque #{bloque} · {nfirmas} firma(s) de validador(es)')


def _draw_footer(c, W, H, datos, p):
    tx_hash = datos.get('tx_hash', '')

    y_box = 2.8*cm
    box_h = 1.6*cm
    pad   = 1.4*cm

    c.setFillColor(p['fondo_caja'])
    c.setStrokeColor(p['acento'])
    c.setLineWidth(0.5)
    c.roundRect(pad, y_box, W - 2*pad, box_h, 5, fill=1, stroke=1)

    c.setFillColor(p['primario'])
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(W/2, y_box + box_h - 0.5*cm, 'HASH DE VERIFICACIÓN BLOCKCHAIN (TX HASH)')

    c.setFillColor(colors.HexColor('#1A1A1A'))
    c.setFont('Courier', 7.5)
    c.drawCentredString(W/2, y_box + 0.3*cm, tx_hash)

    c.setFillColor(colors.white)
    c.setFont('Helvetica', 7)
    c.drawCentredString(W/2, 0.95*cm,
        'Este documento es informativo. La validez legal reside en el registro inmutable de la blockchain.')
    c.drawCentredString(W/2, 0.55*cm,
        'Para verificar autenticidad, consulte el TX Hash en el explorador público.')
