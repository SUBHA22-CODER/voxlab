"use client";

/**
 * Typed wrappers around the browser Web Speech API (Chrome/Edge).
 * STT runs in the browser; VoxLab's backend receives the transcript and
 * records stt_completed events with the measured duration.
 */

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: { length: number; [index: number]: SpeechRecognitionResultLike };
}

interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

interface SpeechWindow extends Window {
  SpeechRecognition?: SpeechRecognitionCtor;
  webkitSpeechRecognition?: SpeechRecognitionCtor;
}

export function speechRecognitionAvailable(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as SpeechWindow;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

export interface RecognitionHandle {
  stop: () => void;
}

export function startRecognition(
  onTranscript: (transcript: string, sttMs: number) => void,
  onError: (message: string) => void,
): RecognitionHandle | null {
  const w = window as SpeechWindow;
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  if (!Ctor) {
    onError("Speech recognition is not available in this browser. Use Chrome or Edge, or switch to Text mode.");
    return null;
  }
  const recognition = new Ctor();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;

  const startedAt = performance.now();
  let stopped = false;

  recognition.onresult = (event) => {
    const sttMs = Math.round(performance.now() - startedAt);
    const result = event.results[event.results.length - 1];
    const transcript = result?.[0]?.transcript?.trim();
    if (transcript) onTranscript(transcript, sttMs);
  };
  recognition.onerror = (event) => {
    if (stopped) return;
    const code = event.error ?? "unknown";
    onError(code === "not-allowed" ? "Microphone permission denied." : `Speech recognition error: ${code}`);
  };
  recognition.onend = () => {
    stopped = true;
  };

  recognition.start();
  return {
    stop: () => {
      stopped = true;
      try {
        recognition.stop();
      } catch {
        /* already stopped */
      }
    },
  };
}

export function speak(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
}
