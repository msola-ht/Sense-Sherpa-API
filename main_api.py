#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SenseVoice API 服务器 - 最终全量定稿版 (全参数支持)
所属机构: 老何的AIGC研究室
作者: HeGenAI
联系方式: hlsaigc
更新时间: 2026/1/5周一 20:44:42
"""

import argparse
import os
import re
import json
import time
import threading
import numpy as np
import sherpa_onnx
import subprocess
import uvicorn
import gc
import tempfile
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from datetime import timedelta
from typing import List, Optional, Dict

app = FastAPI(title="SenseVoice Pro API - Full Parameter Edition")

# --- 1. 全局配置与持久化状态 ---
args = None
vad_config = None
MAPPING_DICT = {}
FILLER_REGEX = None
ENGINE_POOL: Dict[str, sherpa_onnx.OfflineRecognizer] = {}
POOL_LOCK = threading.Lock()
CURRENT_LANGUAGE = ""
CURRENT_USE_ITN = 1
LARGE_FILE_THRESHOLD_MB = 50 

class ConfigSchema(BaseModel):
    language: Optional[str] = None
    mapping: Optional[dict] = None
    filler_words: Optional[str] = None
    use_itn: Optional[int] = None
    vad_threshold: Optional[float] = None
    vad_min_silence: Optional[float] = None
    vad_min_speech: Optional[float] = None
    vad_max_speech: Optional[float] = None

# --- 2. 辅助工具 ---
def format_time(seconds):
    td = timedelta(seconds=max(0, seconds))
    total_sec = int(td.total_seconds())
    ms = int(td.microseconds / 1000)
    return f"{total_sec // 3600:02d}:{(total_sec % 3600) // 60:02d}:{total_sec % 60:02d},{ms:03d}"

def update_filler_regex(words_list):
    global FILLER_REGEX
    if not words_list:
        FILLER_REGEX = None
        return
    valid_words = sorted([w.strip() for w in words_list if w.strip()], key=len, reverse=True)
    if not valid_words:
        FILLER_REGEX = None
        return
    regex_str = "|".join(map(re.escape, valid_words))
    FILLER_REGEX = re.compile(rf'^({regex_str})[，,]?')

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<\|.*?\|>', '', text)
    text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)
    if FILLER_REGEX: text = FILLER_REGEX.sub('', text)
    for k, v in MAPPING_DICT.items(): text = text.replace(k, v)
    return text.strip().rstrip('。').rstrip('.').rstrip('，')

def get_recognizer(lang: str, use_itn: int) -> sherpa_onnx.OfflineRecognizer:
    global ENGINE_POOL
    key = f"{lang}_{use_itn}"
    with POOL_LOCK:
        if key not in ENGINE_POOL:
            recognize_lang = "" if lang == "auto" else lang
            ENGINE_POOL[key] = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=args.sense_voice, tokens=args.tokens,
                num_threads=args.num_threads, use_itn=(use_itn == 1),
                language=recognize_lang, debug=False
            )
        return ENGINE_POOL[key]

# --- 3. 核心推理引擎 ---
class LogicEngine:
    def __init__(self, recognizer, custom_vad_cfg=None):
        cfg = custom_vad_cfg if custom_vad_cfg else vad_config
        self.vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=100)
        self.recognizer = recognizer
        self.audio_buffer = np.array([], dtype=np.float32)
        self.offset = 0 
        self.window_size = 512
        self.padding_duration = 0.3 
        self.sample_rate = 16000
        self.processed_samples_count = 0 

    def process_samples(self, samples: np.ndarray, end_of_stream: bool = False):
        if samples is not None and len(samples) > 0:
            self.audio_buffer = np.concatenate([self.audio_buffer, samples])
        while self.offset + self.window_size < len(self.audio_buffer):
            self.vad.accept_waveform(self.audio_buffer[self.offset : self.offset + self.window_size])
            self.offset += self.window_size
        if end_of_stream: self.vad.flush()
        
        segments = []
        while not self.vad.empty():
            seg_data = self.vad.front
            global_start = seg_data.start
            relative_start = global_start - self.processed_samples_count
            seg_len = len(seg_data.samples)
            pad = int(self.padding_duration * self.sample_rate)
            crop_start = max(0, relative_start - pad)
            crop_end = min(len(self.audio_buffer), relative_start + seg_len + pad)
            inference_samples = self.audio_buffer[crop_start : crop_end]
            if len(inference_samples) > 0:
                stream = self.recognizer.create_stream()
                stream.accept_waveform(self.sample_rate, inference_samples)
                self.recognizer.decode_stream(stream)
                full_text = clean_text(stream.result.text)
                abs_start_sec = global_start / self.sample_rate
                dur_sec = seg_len / self.sample_rate
                if len(full_text) > 0:
                    if len(full_text) > 20 and "，" in full_text:
                        sub = [p.strip() for p in full_text.split("，") if len(p.strip()) > 1]
                        avg = dur_sec / len(sub)
                        for i, p in enumerate(sub):
                            segments.append({"start": abs_start_sec + i * avg, "end": abs_start_sec + (i + 1) * avg, "text": p})
                    else:
                        segments.append({"start": abs_start_sec, "end": abs_start_sec + dur_sec, "text": full_text})
            self.vad.pop()
        
        if self.vad.empty() and len(self.audio_buffer) > self.sample_rate * 60:
            discard_len = len(self.audio_buffer) - (self.sample_rate * 5)
            self.processed_samples_count += discard_len
            self.audio_buffer = self.audio_buffer[discard_len:]
            self.offset = max(0, self.offset - discard_len)
        return segments

# --- 4. 接口定义 ---

@app.post("/config")
async def update_config(conf: ConfigSchema):
    global MAPPING_DICT, CURRENT_LANGUAGE, CURRENT_USE_ITN
    if conf.language is not None: CURRENT_LANGUAGE = conf.language
    if conf.use_itn is not None: CURRENT_USE_ITN = conf.use_itn
    if conf.mapping is not None: MAPPING_DICT = conf.mapping
    if conf.filler_words is not None: update_filler_regex(conf.filler_words.split(','))
    
    # 动态更新 VAD 参数
    if conf.vad_threshold is not None: vad_config.silero_vad.threshold = conf.vad_threshold
    if conf.vad_min_silence is not None: vad_config.silero_vad.min_silence_duration = conf.vad_min_silence
    if conf.vad_min_speech is not None: vad_config.silero_vad.min_speech_duration = conf.vad_min_speech
    if conf.vad_max_speech is not None: vad_config.silero_vad.max_speech_duration = conf.vad_max_speech
    
    print(f"⚙️ [配置更新] VAD 及文本映射参数已同步")
    return {"status": "success"}

@app.post("/transcribe")
async def transcribe_file(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    use_itn: Optional[int] = Form(None),
    vad_threshold: Optional[float] = Form(None)
):
    start_ts = time.time()
    file_size_mb = (file.size or 0) / (1024 * 1024)
    print(f"\n[Step 1/4] 📥 接收任务: {file.filename} ({file_size_mb:.2f}MB)")

    req_lang = language if language is not None else CURRENT_LANGUAGE
    req_itn = use_itn if use_itn is not None else CURRENT_USE_ITN
    recognizer_inst = get_recognizer(req_lang, req_itn)
    
    active_cfg = sherpa_onnx.VadModelConfig()
    active_cfg.silero_vad.model = args.silero_vad_model
    active_cfg.sample_rate = 16000
    active_cfg.silero_vad.threshold = vad_threshold if vad_threshold is not None else vad_config.silero_vad.threshold
    active_cfg.silero_vad.min_silence_duration = vad_config.silero_vad.min_silence_duration
    active_cfg.silero_vad.min_speech_duration = vad_config.silero_vad.min_speech_duration
    active_cfg.silero_vad.max_speech_duration = vad_config.silero_vad.max_speech_duration

    engine = LogicEngine(recognizer=recognizer_inst, custom_vad_cfg=active_cfg)
    all_segments = []
    total_audio_len = 0

    try:
        if file_size_mb >= LARGE_FILE_THRESHOLD_MB:
            print(f"[Step 2/4] 🛠️  大文件模式: 正在进行 FFmpeg 降噪转换...")
            with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp_in, \
                 tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp_out:
                try:
                    shutil.copyfileobj(file.file, tmp_in)
                    tmp_in.close()
                    conv_cmd = ["ffmpeg", "-y", "-i", tmp_in.name, "-af", "afftdn,speechnorm", "-ar", "16000", "-ac", "1", "-f", "s16le", tmp_out.name]
                    subprocess.run(conv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"[Step 3/4] 🧠 正在进行核心引擎推理识别 (无进度静默模式)...")
                    with open(tmp_out.name, "rb") as f:
                        while True:
                            chunk = f.read(160000)
                            if not chunk: break
                            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                            total_audio_len += len(samples)
                            res = engine.process_samples(samples)
                            if res: all_segments.extend(res)
                finally:
                    for p in [tmp_in.name, tmp_out.name]:
                        if os.path.exists(p): os.unlink(p)
        else:
            print(f"[Step 2/4] 🛠️  小文件模式: FFmpeg 流式预处理...")
            cmd = ["ffmpeg", "-i", "pipe:0", "-af", "afftdn,speechnorm", "-f", "s16le", "-ac", "1", "-ar", "16000", "-"]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            def feeder():
                try: shutil.copyfileobj(file.file, proc.stdin); proc.stdin.close()
                except: pass
            threading.Thread(target=feeder, daemon=True).start()
            print(f"[Step 3/4] 🧠 正在进行核心引擎推理识别...")
            while True:
                raw = proc.stdout.read(160000)
                if not raw: break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                total_audio_len += len(samples)
                res = engine.process_samples(samples)
                if res: all_segments.extend(res)
            proc.wait()
            
        final_res = engine.process_samples(np.array([], dtype=np.float32), end_of_stream=True)
        if final_res: all_segments.extend(final_res)

        duration = total_audio_len / 16000
        srt = ""
        for idx, seg in enumerate(all_segments, 1):
            srt += f"{idx}\n{format_time(seg['start'])} --> {format_time(seg['end'])}\n{seg['text']}\n\n"

    except Exception as e:
        print(f"❌ [错误] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()

    rtf = (time.time() - start_ts) / (duration or 1)
    print(f"[Step 4/4] ✨ 完成! [句数: {len(all_segments)} | 时长: {duration:.2f}s | RTF: {rtf:.4f}]")
    gc.collect()
    return {
        "sentence_count": len(all_segments),
        "text": "，".join([s["text"] for s in all_segments]),
        "segments": all_segments,
        "srt": srt.strip(),
        "audio_duration": round(duration, 2),
        "rtf": round(rtf, 4)
    }

# --- 5. 启动入口 (参数已补齐) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SenseVoice Pro - Final Full Audit Edition")
    parser.add_argument("--sense-voice", type=str, required=True)
    parser.add_argument("--tokens", type=str, required=True)
    parser.add_argument("--silero-vad-model", type=str, required=True)
    parser.add_argument("--mapping-file", type=str)
    parser.add_argument("--filler-words-file", type=str)
    parser.add_argument("--language", type=str, default="auto")
    parser.add_argument("--use-itn", type=int, default=1)
    parser.add_argument("--vad-threshold", type=float, default=0.4)
    # --- 重新加入的缺失参数 ---
    parser.add_argument("--vad-min-silence", type=float, default=0.4, help="最小静音时长")
    parser.add_argument("--vad-min-speech", type=float, default=0.25, help="最小语音时长")
    parser.add_argument("--vad-max-speech", type=float, default=5.0, help="最大语音切片时长")
    # -----------------------
    parser.add_argument("--num-threads", type=int, default=4)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    vad_config = sherpa_onnx.VadModelConfig()
    vad_config.silero_vad.model = args.silero_vad_model
    vad_config.silero_vad.threshold = args.vad_threshold
    vad_config.silero_vad.min_silence_duration = args.vad_min_silence
    vad_config.silero_vad.min_speech_duration = args.vad_min_speech
    vad_config.silero_vad.max_speech_duration = args.vad_max_speech
    vad_config.sample_rate = 16000

    if args.mapping_file and os.path.exists(args.mapping_file):
        with open(args.mapping_file, 'r', encoding='utf-8') as f: MAPPING_DICT = json.load(f)
    if args.filler_words_file and os.path.exists(args.filler_words_file):
        with open(args.filler_words_file, 'r', encoding='utf-8') as f:
            update_filler_regex([line.strip() for line in f if line.strip()])

    CURRENT_LANGUAGE, CURRENT_USE_ITN = args.language, args.use_itn
    get_recognizer(CURRENT_LANGUAGE, CURRENT_USE_ITN)
    
    print(f"\n✅ [老何的AIGC研究室] 参数解锁定稿版已就绪")
    print(f"⏰ 时间: 2026/1/5周一 20:44:42 | 作者: HeGenAI")
    uvicorn.run(app, host=args.host, port=args.port)
