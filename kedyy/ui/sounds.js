"use strict";
/* Sound effects, synthesized with Web Audio (no audio files).
   Every note goes through one master bus with a compressor, so the sounds are
   loud and clear on laptop speakers without clipping. */
const KediSound = (() => {
  const MASTER = 0.9;     // overall loudness (0–1)
  let ctx = null, bus = null;

  function ac() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      const comp = ctx.createDynamicsCompressor();
      comp.threshold.value = -14;
      comp.knee.value = 8;
      comp.ratio.value = 5;
      comp.attack.value = 0.003;
      comp.release.value = 0.15;
      const gain = ctx.createGain();
      gain.gain.value = MASTER * 1.4;   // make-up gain after compression (peaks stay just under 0 dB)
      comp.connect(gain).connect(ctx.destination);
      bus = comp;
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  /* One note. `harm` adds an octave-up partial so the note cuts through small speakers. */
  function tone(freq, start, dur, { type = "triangle", vol = 0.5, slideTo = null, harm = 0.35, lp = null } = {}) {
    const c = ac(), t = c.currentTime + start;
    const g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.012);
    g.gain.setValueAtTime(vol, t + dur * 0.35);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    let out = g;
    if (lp) {   // soften harsh waveforms
      const f = c.createBiquadFilter();
      f.type = "lowpass"; f.frequency.value = lp; f.Q.value = 0.7;
      g.connect(f); out = f;
    }
    out.connect(bus);
    const parts = [[1, 1]];
    if (harm) parts.push([2, harm]);
    for (const [mul, amp] of parts) {
      const o = c.createOscillator(), og = c.createGain();
      o.type = type;
      o.frequency.setValueAtTime(freq * mul, t);
      if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo * mul, t + dur);
      og.gain.value = amp;
      o.connect(og).connect(g);
      o.start(t);
      o.stop(t + dur + 0.05);
    }
  }

  return {
    /* "yuppi!": quick rising arpeggio with a sparkle on top */
    ok() {
      [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => tone(f, i * 0.08, 0.26, { type: "square", vol: 0.32, harm: 0.2, lp: 3200 }));
      tone(1318.5, 0.34, 0.45, { type: "sine", vol: 0.45, harm: 0.25 });
      tone(1567.98, 0.42, 0.5, { type: "sine", vol: 0.3, harm: 0 });
    },
    /* sad "womp womp" */
    bad() {
      tone(392, 0, 0.3, { type: "sawtooth", vol: 0.42, slideTo: 370, harm: 0.4, lp: 1800 });
      tone(330, 0.33, 0.6, { type: "sawtooth", vol: 0.42, slideTo: 247, harm: 0.4, lp: 1600 });
    },
    /* soft "meow" notification */
    open() {
      tone(720, 0, 0.3, { type: "triangle", vol: 0.55, slideTo: 1080, harm: 0.45 });
      tone(1080, 0.28, 0.34, { type: "triangle", vol: 0.45, slideTo: 640, harm: 0.4 });
    },
  };
})();
