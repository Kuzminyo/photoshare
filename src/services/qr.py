"""QR code generation."""
import io

import qrcode


def make_qr_png(data: str) -> bytes:
    """Render a QR code with the given text (usually a URL) as a PNG image.

    :param data: The text to encode.
    :return: The PNG bytes.
    """
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()
