"""
Bilingual SMS message catalog (EN/ES).

All user-facing SMS messages live here. Every key has an English
and Spanish variant. Use msg(key, lang, **kwargs) to get the
localized string with format substitutions.
"""

MESSAGES = {
    # ── Language prompt (sent in both languages) ──────────
    "language_prompt": (
        "Welcome to CrewOS! Would you like to receive messages in English or Espanol?\n"
        "Bienvenido a CrewOS! Quieres recibir mensajes en English o Espanol?"
    ),

    # ── Welcome after language selection ──────────────────
    "welcome_en": "Thanks, {name}! You're all set. Send a photo of any receipt or document anytime.",
    "welcome_es": "Gracias, {name}! Estas listo. Envia una foto de cualquier recibo o documento en cualquier momento.",

    # ── Receipt saved ─────────────────────────────────────
    "receipt_saved_en": "Got it, {name}! Receipt{total_str} at {vendor} has been logged.",
    "receipt_saved_es": "Listo, {name}! Recibo{total_str} en {vendor} ha sido registrado.",

    # ── Invoice saved ─────────────────────────────────────
    "invoice_saved_en": "Got it, {name}! Invoice from {vendor} has been logged.",
    "invoice_saved_es": "Listo, {name}! Factura de {vendor} ha sido registrada.",

    # ── Packing slip saved ────────────────────────────────
    "packing_slip_saved_en": "Got it, {name}! Packing slip from {vendor} has been logged.",
    "packing_slip_saved_es": "Listo, {name}! Guia de empaque de {vendor} ha sido registrada.",

    # ── Image download failed ─────────────────────────────
    "image_download_failed_en": "Sorry {name}, I had trouble downloading that image. Could you try sending it again?",
    "image_download_failed_es": "Lo siento {name}, tuve problemas descargando esa imagen. Puedes intentar enviarla de nuevo?",

    # ── OCR failed ────────────────────────────────────────
    "ocr_failed_en": (
        "Sorry {name}, I couldn't read that receipt clearly. "
        "Could you try taking another photo with better lighting? "
        "Make sure the whole receipt is visible and flat."
    ),
    "ocr_failed_es": (
        "Lo siento {name}, no pude leer ese recibo claramente. "
        "Puedes intentar tomar otra foto con mejor luz? "
        "Asegurate de que todo el recibo este visible y plano."
    ),

    # ── Image quality warning ─────────────────────────────
    "image_quality_warning_en": "Heads up — that image looks very small. I'll still process it, but a clearer photo would help.",
    "image_quality_warning_es": "Aviso — esa imagen se ve muy pequena. La procesare, pero una foto mas clara ayudaria.",

    # ── Confirmation reply ────────────────────────────────
    "confirmed_en": "Saved! Thanks, {name}.",
    "confirmed_es": "Guardado! Gracias, {name}.",

    "rejected_en": (
        "No problem, {name}. You can:\n"
        "1. Send a clearer photo of the receipt\n"
        "2. Text me the details: vendor, amount, date, and project name\n\n"
        "What would you like to do?"
    ),
    "rejected_es": (
        "No hay problema, {name}. Puedes:\n"
        "1. Enviar una foto mas clara del recibo\n"
        "2. Escribirme los detalles: proveedor, monto, fecha y nombre del proyecto\n\n"
        "Que prefieres hacer?"
    ),

    "confirm_prompt_en": "{name}, just reply YES to save or NO if something looks wrong.",
    "confirm_prompt_es": "{name}, responde SI para guardar o NO si algo no esta bien.",

    # ── Manual entry ──────────────────────────────────────
    "manual_entry_saved_en": (
        "Got it, {name}. I've saved your notes and flagged this receipt "
        "for management review. Thanks!"
    ),
    "manual_entry_saved_es": (
        "Entendido, {name}. He guardado tus notas y marcado este recibo "
        "para revision. Gracias!"
    ),

    # ── Missed receipt ────────────────────────────────────
    "missed_receipt_prompt_en": (
        "No worries, {name}. Let's log it anyway.\n"
        "Please text me:\n"
        "- Store name\n"
        "- Approximate amount\n"
        "- What you bought\n"
        "- Project name\n\n"
        "Example: Home Depot, about $45, roofing nails and caulk, Project Sparrow"
    ),
    "missed_receipt_prompt_es": (
        "No te preocupes, {name}. Vamos a registrarlo.\n"
        "Escribeme:\n"
        "- Nombre de la tienda\n"
        "- Monto aproximado\n"
        "- Que compraste\n"
        "- Nombre del proyecto\n\n"
        "Ejemplo: Home Depot, como $45, clavos y sellador, Proyecto Sparrow"
    ),

    "missed_receipt_saved_en": (
        "Got it, {name}. I've logged this as a missed receipt. "
        "It'll be reviewed at end of week. Thanks for letting us know!"
    ),
    "missed_receipt_saved_es": (
        "Listo, {name}. He registrado esto como recibo perdido. "
        "Se revisara al final de la semana. Gracias por informarnos!"
    ),

    # ── Unrecognized message ──────────────────────────────
    "unrecognized_en": (
        "Hey {name}, I didn't quite get that. "
        "To submit a receipt, text me a photo with the project name. "
        "Example: [photo] Project Sparrow"
    ),
    "unrecognized_es": (
        "Hola {name}, no entendi eso. "
        "Para enviar un recibo, mandame una foto con el nombre del proyecto. "
        "Ejemplo: [foto] Proyecto Sparrow"
    ),

    # ── Duplicate warning ─────────────────────────────────
    "duplicate_warning_en": "Note: This looks similar to a receipt you already sent. Both copies have been saved for review.",
    "duplicate_warning_es": "Nota: Esto parece similar a un recibo que ya enviaste. Ambas copias se guardaron para revision.",

    # ── Language selection invalid ────────────────────────
    "language_invalid": (
        "I didn't catch that. Please reply with English or Espanol.\n"
        "No entendi. Por favor responde English o Espanol."
    ),
}


def msg(key: str, lang: str = "en", **kwargs) -> str:
    """Get a localized message string.

    Tries key_lang (e.g. "receipt_saved_en"), falls back to key alone
    (for bilingual messages like language_prompt).
    """
    lang = lang or "en"
    lang_key = f"{key}_{lang}"

    text = MESSAGES.get(lang_key) or MESSAGES.get(key, "")
    if kwargs and text:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
