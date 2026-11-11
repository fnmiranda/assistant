"""Motor de TTS neural via Qwen3-TTS (qualidade alta, custo de VRAM real).

Requer: pip install -U qwen-tts soundfile
Modelo escolhido (0.6B) pensando em GPUs de 6GB VRAM compartilhadas com o LLM.
"""

from __future__ import annotations

import io
import re
import subprocess
import threading

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
DEVICE = "cuda:0"
SPEAKER_PADRAO = "Vivian"  # voz feminina suave; ver lista de speakers no README
IDIOMA_PADRAO = "Portuguese"

_lock = threading.Lock()
_model: Qwen3TTSModel | None = None


def _carregar_modelo() -> Qwen3TTSModel:
    """Carrega o modelo uma única vez e mantém residente na VRAM."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = Qwen3TTSModel.from_pretrained(
                    MODEL_ID,
                    device_map=DEVICE,
                    dtype=torch.bfloat16,
                )
    return _model


def falar(texto: str, *, speaker: str = SPEAKER_PADRAO, idioma: str = IDIOMA_PADRAO) -> None:
    """Gera áudio a partir do texto via Qwen3-TTS e toca imediatamente."""
    if not texto.strip():
        return

    model = _carregar_modelo()
    wavs, sample_rate = model.generate_custom_voice(
        text=texto,
        language=idioma,
        speaker=speaker,
    )

    buffer = io.BytesIO()
    sf.write(buffer, wavs[0], sample_rate, format="WAV")
    buffer.seek(0)
    subprocess.run(["aplay"], input=buffer.read())


def dividir_em_frases(texto_completo: str) -> list[str]:
    """Quebra a resposta do LLM em frases para falar de forma incremental."""
    return [f for f in re.split(r"(?<=[.!?])\s+", texto_completo) if f.strip()]


if __name__ == "__main__":
    falar("o que você está fazendo?")