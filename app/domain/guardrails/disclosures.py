"""Pengungkapan yang ditulis server (Architecture.md 6.6). Model tidak pernah menulis teks ini.

Teks harus identik dengan web/lib/disclosures.ts. Ubah keduanya bersamaan.
"""

DISCLOSURES: dict[str, dict[str, str]] = {
    "id": {
        "ai": "Anda sedang berbicara dengan sistem AI, bukan manusia.",
        "responsibility": (
            "Pada akhirnya semua keputusan finansial ada di tangan Anda. Saya hanya advisor berbasis data "
            "yang membantu penilaian Anda. Ini bukan nasihat keuangan dan saya tidak menjamin hasil apa pun."
        ),
        "handoff": (
            "Permintaan ini di luar skrip yang saya setujui, jadi saya tidak menjawabnya. Percakapan ini "
            "diteruskan ke pemilik untuk ditinjau manusia."
        ),
    },
    "en": {
        "ai": "You are talking to an AI system, not a human.",
        "responsibility": (
            "Ultimately, every financial decision is yours. I am only a data-based advisor helping your "
            "assessment. This is not financial advice and I do not guarantee any outcome."
        ),
        "handoff": (
            "This request is outside my approved script, so I will not answer it. This conversation has "
            "been passed to the owner for human review."
        ),
    },
}


def get_disclosures(language: str) -> dict[str, str]:
    """Bahasa tidak dikenal jatuh ke bahasa Indonesia (bawaan)."""
    return DISCLOSURES.get(language, DISCLOSURES["id"])
