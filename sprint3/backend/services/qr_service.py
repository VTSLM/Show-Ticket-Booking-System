import qrcode
import io
import base64

def generate_qr_bytes(data: str) -> str:
    """Generate QR code and return as base64 string."""
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def generate_qr_base64(data: str) -> str:
    return generate_qr_bytes(data)
