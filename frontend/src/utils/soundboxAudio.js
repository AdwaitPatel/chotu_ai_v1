/**
 * Web Audio API Soundbox Chime & Voice Synthesizer
 * Emulates the iconic Paytm Soundbox 4G alert chime and bilingual announcement.
 */

class SoundboxAudioEngine {
  constructor() {
    this.ctx = null;
  }

  getAudioContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  // Plays the signature upbeat 3-tone Paytm payment chime
  playChime() {
    const ctx = this.getAudioContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const notes = [
      { freq: 523.25, time: 0.00, duration: 0.12 }, // C5
      { freq: 659.25, time: 0.10, duration: 0.12 }, // E5
      { freq: 783.99, time: 0.20, duration: 0.28 }, // G5
      { freq: 1046.5, time: 0.32, duration: 0.35 }, // C6
    ];

    notes.forEach(({ freq, time, duration }) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now + time);

      gain.gain.setValueAtTime(0.001, now + time);
      gain.gain.exponentialRampToValueAtTime(0.3, now + time + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + time + duration);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now + time);
      osc.stop(now + time + duration + 0.05);
    });
  }

  // Announces payment via browser SpeechSynthesis
  speak(text, lang = 'hi-IN') {
    if (!('speechSynthesis' in window)) return;
    
    // Cancel previous speech if ongoing
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = 1.0;
    utterance.pitch = 1.05;

    // Try to find a Hindi or Indian English voice if available
    const voices = window.speechSynthesis.getVoices();
    const targetVoice = voices.find(v => v.lang.includes('hi') || v.lang.includes('IN'));
    if (targetVoice) {
      utterance.voice = targetVoice;
    }

    window.speechSynthesis.speak(utterance);
  }

  // Full Paytm Soundbox payment announcement flow
  announcePayment(amount, lang = 'hi') {
    this.playChime();

    setTimeout(() => {
      let text = `Paytm par ${amount} rupaye prapt hue`;
      if (lang === 'en') {
        text = `Received ${amount} rupees on Paytm`;
      }
      this.speak(text, lang === 'hi' ? 'hi-IN' : 'en-IN');
    }, 700);
  }

  // Spoken voice reply for Copilot queries
  speakCopilotReply(text, lang = 'hi') {
    this.speak(text, lang === 'hi' ? 'hi-IN' : 'en-IN');
  }
}

export const soundbox = new SoundboxAudioEngine();
