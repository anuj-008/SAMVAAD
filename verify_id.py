# verify_id.py
from pyzbar.pyzbar import decode
from PIL import Image
import io
import base64
import google.generativeai as genai

# Configure Gemini API
genai.configure(api_key="AIzaSyBKV1TrzEu6JjKqhqwn-SuKylZTiI9yrQc")

def verify_with_barcode(image_bytes, entered_code):
    """Try reading barcode first."""
    img = Image.open(io.BytesIO(image_bytes))
    decoded = decode(img)
    if decoded:
        scanned = decoded[0].data.decode("utf-8")
        return scanned == entered_code
    return None  # no barcode found

def verify_with_gemini(image_bytes, entered_code):
    """Fallback: OCR with Gemini AI."""
    b64_img = base64.b64encode(image_bytes).decode("utf-8")

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content([
        {"mime_type": "image/png", "data": b64_img},
        "Extract the digits visible on the ID card (especially below barcode)."
    ])

    text = response.text.strip()
    return entered_code in text

def verify_id(image_bytes, entered_code):
    """Main verification logic: barcode first, fallback to Gemini OCR."""
    barcode_result = verify_with_barcode(image_bytes, entered_code)
    if barcode_result is True:
        return True, "✅ Verified (barcode matched)"
    elif barcode_result is False:
        return False, "❌ Rejected (barcode mismatch)"
    else:
        ocr_result = verify_with_gemini(image_bytes, entered_code)
        return (True, "✅ Verified (OCR matched)") if ocr_result else (False, "❌ Rejected (OCR failed)")
