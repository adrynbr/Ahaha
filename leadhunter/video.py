"""Vídeos recebidos no Telegram: juntar vários num só (9:16) e tirar quadros para a IA analisar.

Usa o ffmpeg do sistema ou, se não houver, o que vem no pacote imageio-ffmpeg.
Pensado para hospedagem pequena (256 MB): uma thread, preset rápido, 720x1280.
"""

from __future__ import annotations

import re
import shutil
import subprocess

LARGURA, ALTURA = 720, 1280


def ffmpeg_exe() -> str | None:
    caminho = shutil.which("ffmpeg")
    if caminho:
        return caminho
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - pacote ausente ou sem binário para esta máquina
        return None


def _info(exe: str, arquivo: str) -> str:
    r = subprocess.run([exe, "-hide_banner", "-i", arquivo], capture_output=True, text=True,
                       errors="ignore", timeout=60)
    return r.stderr


def duracao(info: str) -> float:
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def tem_audio(info: str) -> bool:
    return bool(re.search(r"Stream #\S+.*Audio:", info))


def comando_juntar(exe: str, entradas: list[str], saida: str, audios: list[bool],
                   duracoes: list[float]) -> list[str]:
    """Monta o comando do ffmpeg que junta os vídeos na ordem, em 720x1280 (9:16)."""
    cmd = [exe, "-hide_banner", "-y"]
    for e in entradas:
        cmd += ["-i", e]
    n = len(entradas)
    # Vídeo sem áudio ganha um silêncio do mesmo tamanho (o concat exige áudio em todos).
    silencios = {}
    for i, (tem, dur) in enumerate(zip(audios, duracoes)):
        if not tem:
            silencios[i] = n + len(silencios)
            cmd += ["-f", "lavfi", "-t", f"{max(dur, 0.1):.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
    filtros, pares = [], ""
    for i in range(n):
        filtros.append(
            f"[{i}:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=decrease,"
            f"pad={LARGURA}:{ALTURA}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]")
        origem = f"{silencios[i]}:a" if i in silencios else f"{i}:a"
        filtros.append(f"[{origem}]aresample=44100,aformat=channel_layouts=stereo[a{i}]")
        pares += f"[v{i}][a{i}]"
    filtros.append(f"{pares}concat=n={n}:v=1:a=1[v][a]")
    cmd += ["-filter_complex", ";".join(filtros), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-threads", "1",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", saida]
    return cmd


def juntar(entradas: list[str], saida: str, timeout: int = 600) -> str | None:
    """Junta os vídeos. Retorna None se deu certo, ou a mensagem de erro."""
    exe = ffmpeg_exe()
    if not exe:
        return "ffmpeg não está instalado no servidor."
    infos = [_info(exe, e) for e in entradas]
    cmd = comando_juntar(exe, entradas, saida, [tem_audio(i) for i in infos],
                         [duracao(i) for i in infos])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=timeout)
    except subprocess.TimeoutExpired:
        return "Demorou demais para juntar (vídeos muito longos?)."
    if r.returncode != 0:
        return "ffmpeg falhou: " + r.stderr.strip()[-300:]
    return None


def quadros(arquivo: str, saida_jpg: str, n: int = 9) -> str | None:
    """Gera UMA imagem com `n` quadros do vídeo em grade 3x3 (para a IA ver o criativo).

    Retorna None se deu certo, ou a mensagem de erro.
    """
    exe = ffmpeg_exe()
    if not exe:
        return "ffmpeg não está instalado no servidor."
    dur = duracao(_info(exe, arquivo)) or 10.0
    fps = n / dur
    cmd = [exe, "-hide_banner", "-y", "-i", arquivo, "-vf",
           f"fps={fps:.4f},scale=320:-2,tile=3x3", "-frames:v", "1", "-q:v", "4", saida_jpg]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="ignore", timeout=180)
    except subprocess.TimeoutExpired:
        return "Demorou demais para ler o vídeo."
    if r.returncode != 0:
        return "ffmpeg falhou: " + r.stderr.strip()[-300:]
    return None
