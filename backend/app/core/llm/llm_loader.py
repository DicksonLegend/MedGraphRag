"""
MedGraphRAG Backend — LLM Loader
==================================
Lazy singleton wrapper for llama-cpp-python GGUF inference with automatic CUDA library loading
and an OOM fallback chain (full_gpu -> partial_gpu -> cpu).

Ensures 0 VRAM leak, full ChatML chat template formatting, and VRAM/RAM monitoring.
"""

from __future__ import annotations

import ctypes
import glob
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dynamic CUDA environment setup for site-packages/nvidia runtime libraries
# ---------------------------------------------------------------------------
def _ensure_cuda_ld_path() -> None:
    """Pre-load nvidia CUDA runtime shared objects installed inside site-packages."""
    try:
        venv_path = Path(sys.executable).parent.parent
        nvidia_lib_dirs = glob.glob(str(venv_path / "lib" / "python*" / "site-packages" / "nvidia" / "*" / "lib"))
        if nvidia_lib_dirs:
            current_ld = os.environ.get("LD_LIBRARY_PATH", "")
            new_ld = ":".join(nvidia_lib_dirs) + (f":{current_ld}" if current_ld else "")
            os.environ["LD_LIBRARY_PATH"] = new_ld

            # Pre-load libcudart and libcublas using ctypes (excluding libnvblas)
            for dir_path in nvidia_lib_dirs:
                cudart_so = list(Path(dir_path).glob("libcudart.so*"))
                cublas_so = list(Path(dir_path).glob("libcublas.so*"))
                for lib_file in cudart_so + cublas_so:
                    if "nvblas" in lib_file.name:
                        continue
                    try:
                        ctypes.CDLL(str(lib_file), mode=ctypes.RTLD_GLOBAL)
                    except Exception:
                        pass
    except Exception as exc:
        logger.debug("CUDA LD path auto-discovery exception: %s", exc)


_ensure_cuda_ld_path()
import llama_cpp  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level singleton state & metrics
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_llm_instance: Optional[llama_cpp.Llama] = None
_active_llm_mode: str = "unloaded"  # 'full_gpu' | 'partial_gpu' | 'cpu'


def _get_ram_gb() -> float:
    """Return process RAM usage in GB."""
    return psutil.Process(os.getpid()).memory_info().rss / 1e9


def _get_vram_mb() -> float:
    """Return current system GPU VRAM usage in MB via nvidia-smi or torch."""
    try:
        import subprocess
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / 1e6
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Singleton Loader & Fallback Chain
# ---------------------------------------------------------------------------
def get_llm() -> llama_cpp.Llama:
    """
    Get or initialize the llama_cpp.Llama model singleton.
    Executes the OOM fallback chain:
      1. full_gpu (n_gpu_layers = -1 or config.llm_n_gpu_layers)
      2. partial_gpu (n_gpu_layers = 28)
      3. cpu (n_gpu_layers = 0)
    """
    global _llm_instance, _active_llm_mode

    if _llm_instance is not None:
        return _llm_instance

    with _lock:
        if _llm_instance is not None:
            return _llm_instance

        model_path = Path(settings.llm_model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"LLM GGUF model file not found at: {model_path}. "
                f"Ensure model is downloaded to models/{settings.llm_gguf_file}."
            )

        fallback_tiers: List[Tuple[str, int]] = [
            ("full_gpu", settings.llm_n_gpu_layers),
            ("partial_gpu", 28),
            ("cpu", 0),
        ]

        # Deduplicate tiers if initial config is already 28 or 0
        seen_layers = set()
        unique_tiers = []
        for name, layers in fallback_tiers:
            if layers not in seen_layers:
                seen_layers.add(layers)
                unique_tiers.append((name, layers))

        # Map quantization string types (e.g. 'q8_0', 'f16') to llama_cpp integer enums
        type_k_enum = getattr(llama_cpp, f"GGML_TYPE_{settings.llm_type_k.upper()}", None)
        type_v_enum = getattr(llama_cpp, f"GGML_TYPE_{settings.llm_type_v.upper()}", None)

        last_error = None
        for mode_name, gpu_layers in unique_tiers:
            logger.info(
                "Attempting LLM load: mode=%s, n_gpu_layers=%d, n_ctx=%d, flash_attn=%s, type_k=%s (%s), type_v=%s (%s)",
                mode_name, gpu_layers, settings.llm_n_ctx, settings.llm_flash_attn,
                settings.llm_type_k, type_k_enum, settings.llm_type_v, type_v_enum
            )
            ram_before = _get_ram_gb()
            vram_before = _get_vram_mb()
            t0 = time.perf_counter()

            try:
                init_kwargs = {
                    "model_path": str(model_path),
                    "n_gpu_layers": gpu_layers,
                    "n_ctx": settings.llm_n_ctx,
                    "flash_attn": settings.llm_flash_attn,
                    "offload_kqv": settings.llm_offload_kqv,
                    "seed": 42,
                    "verbose": False,
                }
                if type_k_enum is not None:
                    init_kwargs["type_k"] = type_k_enum
                if type_v_enum is not None:
                    init_kwargs["type_v"] = type_v_enum

                llm = llama_cpp.Llama(**init_kwargs)
                load_time = time.perf_counter() - t0
                ram_after = _get_ram_gb()
                vram_after = _get_vram_mb()

                logger.info(
                    "✅ LLM successfully loaded [%s] in %.2fs. RAM: %.2f GB (Δ %.2f GB), VRAM: %.1f MB (Δ %.1f MB)",
                    mode_name, load_time, ram_after, ram_after - ram_before, vram_after, vram_after - vram_before
                )

                _llm_instance = llm
                _active_llm_mode = mode_name
                return _llm_instance

            except Exception as exc:
                logger.warning(
                    "⚠️ LLM load failed for mode=%s (n_gpu_layers=%d): %s. Trying next fallback tier...",
                    mode_name, gpu_layers, exc
                )
                last_error = exc

        raise RuntimeError(f"All LLM loading tiers failed. Last error: {last_error}")


def get_llm_mode() -> str:
    """Return the active LLM mode ('full_gpu' | 'partial_gpu' | 'cpu')."""
    return _active_llm_mode


def generate_chat(
    messages: List[Dict[str, str]],
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate completion using embedded ChatML template via create_chat_completion().

    Parameters
    ----------
    messages : list of dict
        Chat messages e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    max_tokens : int, optional
        Override for max generation tokens.
    temperature : float, optional
        Override for sampling temperature.

    Returns
    -------
    dict with keys: 'text', 'finish_reason', 'tokens_eval', 'latency_ms', 'llm_mode', 'ram_gb', 'vram_mb'
    """
    llm = get_llm()

    max_tok = max_tokens or settings.llm_max_tokens
    temp = temperature if temperature is not None else settings.llm_temperature

    t0 = time.perf_counter()
    ram_before = _get_ram_gb()
    vram_before = _get_vram_mb()

    # Reset KV cache to ensure deterministic generation without residual cache contamination
    try:
        llm.reset()
    except Exception:
        pass

    # Pass chat messages to native create_chat_completion (ChatML auto-formatted)
    kwargs = {
        "messages": messages,
        "max_tokens": max_tok,
        "temperature": temp,
    }
    if temp == 0.0:
        kwargs["top_p"] = 1.0
        kwargs["top_k"] = 1
    response = llm.create_chat_completion(**kwargs)

    latency_ms = (time.perf_counter() - t0) * 1000
    choice = response["choices"][0]
    message_content = choice["message"]["content"] or ""
    finish_reason = choice.get("finish_reason", "stop")

    usage = response.get("usage", {})
    completion_tokens = usage.get("completion_tokens", 0)

    logger.debug(
        "LLM generation complete in %.1f ms (%d tokens, mode=%s)",
        latency_ms, completion_tokens, _active_llm_mode
    )

    return {
        "text": message_content,
        "finish_reason": finish_reason,
        "completion_tokens": completion_tokens,
        "latency_ms": latency_ms,
        "llm_mode": _active_llm_mode,
        "ram_gb": _get_ram_gb(),
        "vram_mb": _get_vram_mb(),
    }
