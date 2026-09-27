"""Synthesizes every original sound effect for Red Mesa Holdout into one
sound sheet (to stay within Roblox's audio upload quota) plus a manifest.

Usage: .venv-audio/bin/python tools/audio/synth.py
Outputs: assets/audio/sfx_sheet.wav/.ogg and assets/audio/sfx_sheet.json
"""

import json
import pathlib

import numpy as np
from scipy import signal

SR = 44100
GAP = 0.3  # silence between sheet entries (seconds)
RNG = np.random.default_rng(7)
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "audio"


# ---------------------------------------------------------------- helpers
def t(duration):
    return np.arange(int(duration * SR)) / SR


def noise(duration):
    return RNG.uniform(-1, 1, int(duration * SR))


def brown(duration):
    x = np.cumsum(RNG.normal(0, 1, int(duration * SR)))
    x = signal.lfilter([1, -1], [1, -0.995], x)
    return x / (np.max(np.abs(x)) + 1e-9)


def filt(x, kind, cutoff, order=4):
    b, a = signal.butter(order, np.array(cutoff) / (SR / 2), btype=kind)
    return signal.lfilter(b, a, x)


def env_exp(duration, tau, attack=0.002):
    tt = t(duration)
    e = np.exp(-tt / tau)
    a = np.clip(tt / max(attack, 1e-4), 0, 1)
    return e * a


def env_adsr(duration, a, d, s, r):
    n = int(duration * SR)
    tt = np.arange(n) / SR
    e = np.full(n, s)
    e[tt < a] = tt[tt < a] / a
    dm = (tt >= a) & (tt < a + d)
    e[dm] = 1 - (1 - s) * (tt[dm] - a) / d
    rm = tt > duration - r
    e[rm] *= (duration - tt[rm]) / r
    return e


def sweep(f0, f1, duration, shape="sine", curve="exp"):
    tt = t(duration)
    if curve == "exp":
        f = f0 * (f1 / f0) ** (tt / duration)
    else:
        f = f0 + (f1 - f0) * tt / duration
    ph = 2 * np.pi * np.cumsum(f) / SR
    if shape == "saw":
        return 2 * ((ph / (2 * np.pi)) % 1) - 1
    if shape == "square":
        return np.sign(np.sin(ph))
    return np.sin(ph)


def tone(freq, duration, shape="sine"):
    return sweep(freq, freq, duration, shape, "lin")


def pad(x, duration):
    n = int(duration * SR)
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def mix(*parts):
    n = max(len(p) for p in parts)
    return sum(np.pad(p, (0, n - len(p))) for p in parts)


def at(x, offset, total):
    out = np.zeros(int(total * SR))
    i = int(offset * SR)
    seg = x[: max(0, len(out) - i)]
    out[i : i + len(seg)] += seg
    return out


def sat(x, drive=1.5):
    return np.tanh(x * drive) / np.tanh(drive)


def reverb(x, length=0.8, amount=0.25, damp=3000):
    ir = noise(length) * np.exp(-t(length) / (length / 5))
    ir = filt(ir, "lowpass", damp, 2)
    wet = signal.fftconvolve(x, ir)[: len(x) + int(length * SR)]
    wet /= np.max(np.abs(wet)) + 1e-9
    dry = np.pad(x, (0, len(wet) - len(x)))
    return dry + amount * wet


def norm(x, peak=0.89):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def loopify(x, fade=0.08):
    """Crossfades the tail into the head so the buffer loops seamlessly."""
    n = int(fade * SR)
    head, tail = x[:n].copy(), x[-n:]
    ramp = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * ramp + tail * (1 - ramp)
    return x


# ----------------------------------------------------------------- sounds
def machine_gun():
    d = 0.32
    crack = filt(noise(d), "bandpass", [300, 5000]) * env_exp(d, 0.018)
    body = filt(noise(d), "lowpass", 900) * env_exp(d, 0.06) * 0.8
    thump = tone(62, d) * env_exp(d, 0.05) * 0.9
    click = filt(noise(d), "highpass", 4000) * env_exp(d, 0.004) * 0.5
    return reverb(sat(crack + body + thump + click, 2.2), 0.4, 0.15)


def overheat():
    d = 1.6
    hiss = filt(noise(d), "highpass", 2500) * env_adsr(d, 0.05, 0.2, 0.6, 0.8) * 0.5
    beep = at(tone(880, 0.12, "square") * 0.35, 0, d) + at(tone(660, 0.18, "square") * 0.35, 0.16, d)
    return filt(hiss + beep, "lowpass", 9000)


def click_pair():
    d = 0.2
    c = filt(noise(0.03), "bandpass", [2500, 7000]) * env_exp(0.03, 0.004)
    return at(c, 0, d) + at(c * 0.7, 0.07, d)


def reload_sfx():
    d = 0.6
    clunk = filt(noise(0.08), "bandpass", [300, 1500]) * env_exp(0.08, 0.015)
    slide = filt(noise(0.15), "bandpass", [1500, 4000]) * env_adsr(0.15, 0.02, 0.05, 0.5, 0.06) * 0.4
    clack = filt(noise(0.06), "bandpass", [800, 3500]) * env_exp(0.06, 0.01)
    return at(clunk, 0, d) + at(slide, 0.12, d) + at(clack, 0.34, d)


def weapon_switch():
    d = 0.45
    whir = filt(sweep(160, 280, 0.25, "saw"), "lowpass", 1200) * env_adsr(0.25, 0.03, 0.1, 0.7, 0.08) * 0.35
    clunk = filt(noise(0.08), "bandpass", [250, 1200]) * env_exp(0.08, 0.02)
    return at(whir, 0, d) + at(clunk, 0.26, d)


def rocket_launch():
    d = 1.6
    thump = tone(55, d) * env_exp(d, 0.08)
    whoosh = filt(noise(d), "bandpass", [250, 2500]) * env_adsr(d, 0.02, 0.2, 0.5, 1.0)
    roar = filt(brown(d), "lowpass", 400) * env_adsr(d, 0.01, 0.3, 0.4, 1.0)
    crackle = (RNG.random(int(d * SR)) > 0.9975) * RNG.uniform(-1, 1, int(d * SR)) * env_exp(d, 0.5)
    return reverb(sat(thump + whoosh * 0.8 + roar + crackle * 0.6, 1.8), 0.9, 0.2)


def missile_launch():
    d = 1.8
    hiss = filt(noise(d), "highpass", 1200) * env_adsr(d, 0.03, 0.3, 0.6, 1.1) * 0.7
    tonal = filt(sweep(260, 620, d, "saw"), "lowpass", 1800) * env_adsr(d, 0.05, 0.3, 0.4, 1.0) * 0.25
    pop = filt(noise(0.1), "lowpass", 800) * env_exp(0.1, 0.02)
    return reverb(mix(hiss + tonal, pop), 0.8, 0.2)


def lock_tone():
    return tone(1150, 0.08) * env_adsr(0.08, 0.004, 0.01, 0.9, 0.02) * 0.6


def lock_acquired():
    d = 0.6
    x = tone(1480, d) * 0.5 + tone(1480, d, "square") * 0.12
    return x * env_adsr(d, 0.005, 0.02, 0.9, 0.05)


def explosion(scale=1.0, bright=1.0):
    d = 2.6 * scale
    boom = filt(brown(d), "lowpass", 160) * env_exp(d, 0.55 * scale, 0.004) * 1.4
    sub = tone(42 / scale, d) * env_exp(d, 0.35 * scale, 0.003)
    mid = filt(noise(d), "bandpass", [300, 2400 * bright]) * env_exp(d, 0.18 * scale, 0.002) * 0.9
    n = int(d * SR)
    debris = (RNG.random(n) > 0.9985) * RNG.uniform(-1, 1, n)
    debris = filt(debris, "bandpass", [800, 5000]) * env_exp(d, 0.7 * scale) * 2.0
    return reverb(sat(boom + sub + mid + debris, 2.5), 1.2, 0.3, 2000)


def air_burst():
    d = 2.2
    crack = filt(noise(d), "bandpass", [600, 6000]) * env_exp(d, 0.08, 0.001)
    body = filt(brown(d), "lowpass", 300) * env_exp(d, 0.4) * 1.1
    return reverb(sat(crack + body, 2.2), 1.6, 0.45, 3000)


def ricochet():
    d = 0.5
    zing = sweep(3400, 1500, 0.4) * env_exp(0.4, 0.15) * (1 + 0.3 * np.sin(2 * np.pi * 38 * t(0.4)))
    tick = filt(noise(0.02), "highpass", 3000) * env_exp(0.02, 0.003)
    return pad(mix(zing * 0.45, tick), d)


def hit_tick():
    return tone(2600, 0.03) * env_exp(0.03, 0.008) * 0.6


def kill_confirm():
    d = 0.18
    return at(tone(1250, 0.07) * env_exp(0.07, 0.03), 0, d) + at(tone(1700, 0.09) * env_exp(0.09, 0.04), 0.06, d)


def damage_thud(heavy=False):
    d = 0.9 if heavy else 0.4
    thud = filt(noise(d), "lowpass", 500) * env_exp(d, 0.12 if heavy else 0.06)
    low = tone(80 if heavy else 110, d) * env_exp(d, 0.15 if heavy else 0.07)
    crunch = filt(noise(d), "bandpass", [900, 3500]) * env_exp(d, 0.05) * (0.8 if heavy else 0.3)
    return sat(thud + low + crunch, 2.0)


def alarm_loop():
    d = 1.0
    a = filt(tone(700, 0.5, "square"), "lowpass", 2500) * 0.4
    b = filt(tone(540, 0.5, "square"), "lowpass", 2500) * 0.4
    return np.concatenate([a, b])


def jet_siren():
    d = 3.2
    tt = t(d)
    f = 300 + 600 * np.sin(np.pi * np.clip(tt / d, 0, 1)) ** 0.7
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * 0.6 + np.sin(2 * ph) * 0.2 + np.sin(3 * ph) * 0.08
    return x * env_adsr(d, 0.2, 0.1, 1.0, 0.5)


def jet_flyby():
    d = 3.5
    tt = t(d)
    swell = np.exp(-((tt - 1.6) ** 2) / 0.5)
    roar = filt(noise(d), "lowpass", 2500) * 0.6 + filt(brown(d), "lowpass", 300)
    whine = sweep(2200, 900, d) * 0.12
    return sat((roar + whine) * swell, 1.5)


def heli_loop():
    d = 1.0
    tt = t(d)
    chop = 0.5 * (1 + np.sin(2 * np.pi * 6 * tt)) ** 3 / 8
    body = filt(noise(d), "lowpass", 350) * chop * 2
    turbine = tone(1180, d) * 0.03 + tone(2360, d) * 0.01
    return body + turbine


def tank_engine_loop():
    d = 2.0
    rumble = filt(tone(46, d, "saw"), "lowpass", 180) * 0.6
    grit = filt(brown(d), "lowpass", 250) * 0.5
    tt = t(d)
    clank = (np.sin(2 * np.pi * 4 * tt) > 0.97) * filt(noise(d), "bandpass", [600, 2000]) * 0.3
    return loopify(np.concatenate([rumble + grit + clank, (rumble + grit)[: int(0.08 * SR)]]))


def buggy_engine_loop():
    d = 1.0
    x = filt(tone(118, d + 0.08, "saw"), "lowpass", 900) * (0.7 + 0.3 * np.sin(2 * np.pi * 9 * t(d + 0.08)))
    return loopify(x * 0.6)


def tank_cannon():
    return explosion(0.75, 1.4)


def cannon_charge():
    d = 4.0
    tt = t(d)
    hum = sweep(70, 420, d, "saw")
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * (3 + 14 * tt / d) * tt)
    build = filt(noise(d), "bandpass", [400, 3000]) * (tt / d) ** 2 * 0.4
    return filt(hum, "lowpass", 1600) * trem * 0.5 * np.clip(tt / 0.3, 0, 1) + build


def snare_roll(d, rate0=8, rate1=30):
    out = np.zeros(int(d * SR))
    time = 0.0
    while time < d - 0.05:
        rate = rate0 + (rate1 - rate0) * time / d
        hit = filt(noise(0.08), "bandpass", [1500, 6000]) * env_exp(0.08, 0.02) * (0.3 + 0.7 * time / d)
        out += at(hit, time, d)
        time += 1 / rate
    return out


def brass(freqs, d, cutoff=1800):
    x = sum(tone(f, d, "saw") for f in freqs) / len(freqs)
    return filt(x, "lowpass", cutoff) * env_adsr(d, 0.04, 0.2, 0.7, 0.4)


def wave_start():
    d = 2.2
    roll = snare_roll(1.0)
    chord = brass([130.8, 155.6, 196.0, 261.6], 1.2)
    return reverb(at(roll, 0, d) + at(chord, 0.95, d) * 0.9, 1.0, 0.25)


def wave_clear():
    d = 2.0
    notes = [261.6, 329.6, 392.0, 523.3]
    out = np.zeros(int(d * SR))
    for i, f in enumerate(notes):
        out += at(brass([f, f * 2], 0.5 if i < 3 else 1.0, 2400), i * 0.14, d)
    return reverb(out, 1.0, 0.3)


def crate_pickup():
    d = 0.7
    out = np.zeros(int(d * SR))
    for i, f in enumerate([1046.5, 1318.5, 1568.0]):
        out += at(tone(f, 0.35) * env_exp(0.35, 0.12), i * 0.07, d) * 0.5
    return out


def crate_drop():
    d = 0.8
    radio = filt(noise(d), "bandpass", [800, 2400]) * env_adsr(d, 0.01, 0.1, 0.3, 0.2) * 0.3
    beeps = at(tone(1000, 0.1) * 0.4, 0.1, d) + at(tone(1000, 0.1) * 0.4, 0.3, d)
    return radio + beeps


def victory():
    d = 4.5
    prog = [([261.6, 329.6, 392.0], 0.0, 0.8), ([293.7, 370.0, 440.0], 0.8, 0.8), ([392.0, 493.9, 587.3], 1.6, 0.6), ([523.3, 659.3, 784.0, 1046.5], 2.2, 2.0)]
    out = np.zeros(int(d * SR))
    for freqs, start, length in prog:
        out += at(brass(freqs, length, 2600), start, d)
    return reverb(out + at(snare_roll(0.6, 20, 30) * 0.5, 1.6, d), 1.4, 0.3)


def defeat():
    d = 4.0
    out = np.zeros(int(d * SR))
    for i, freqs in enumerate([[196.0, 233.1, 293.7], [174.6, 207.7, 261.6], [155.6, 185.0, 233.1], [130.8, 155.6, 196.0]]):
        out += at(brass(freqs, 1.0 if i < 3 else 1.8, 1200), i * 0.7, d)
    rumble = filt(brown(d), "lowpass", 120) * env_adsr(d, 0.5, 0.5, 0.6, 1.5) * 0.6
    return reverb(out + rumble, 1.5, 0.3)


def wind_loop():
    d = 6.0
    tt = t(d + 0.5)
    base = filt(brown(d + 0.5), "bandpass", [150, 700])
    gust = 0.6 + 0.4 * np.sin(2 * np.pi * tt / (d + 0.5)) * np.sin(2 * np.pi * 0.37 * tt)
    return loopify(base * gust, 0.5)


def enemy_rifle():
    d = 0.5
    crack = filt(noise(d), "bandpass", [700, 4000]) * env_exp(d, 0.012)
    return reverb(crack * 0.7, 0.5, 0.4)


def heli_rockets():
    d = 1.6
    out = np.zeros(int(d * SR))
    for i in range(4):
        w = filt(noise(0.7), "bandpass", [400, 3000]) * env_adsr(0.7, 0.01, 0.1, 0.4, 0.5)
        out += at(w * 0.6, i * 0.14, d)
    return out


def bomb_whistle():
    d = 1.5
    return sweep(1400, 500, d) * env_adsr(d, 0.1, 0.1, 0.8, 0.1) * 0.35


def infantry_death():
    d = 0.35
    return filt(noise(d), "lowpass", 700) * env_exp(d, 0.05) * 0.5


# ------------------------------------------------- airdrop (AD-2, appended)
# Appended after the original 36 so every earlier region keeps its offset
# and its samples (the shared RNG is consumed in list order).
def transport_drone_loop():
    """Four turboprops a few hundred studs up: a low blade-pass drone from
    four slightly detuned engines (they beat slowly against each other),
    their harmonics, a faint turbine whine and wind-rush noise."""
    d = 4.0
    tt = t(d + 0.2)
    out = np.zeros(len(tt))
    for k, f0 in enumerate((71.0, 71.6, 72.3, 70.4)):
        ph = 2 * np.pi * f0 * tt + k * 1.3
        # Blade-pass pulse train: a soft saw-like buzz, band limited.
        buzz = sum(np.sin(n * ph) / n ** 0.85 for n in range(1, 14))
        out += buzz * 0.25
    out = filt(out, "lowpass", 1400)
    whine = (tone(1180, d + 0.2) * 0.012 + tone(2360, d + 0.2) * 0.005) * (1 + 0.3 * np.sin(2 * np.pi * 0.7 * tt))
    rush = filt(brown(d + 0.2), "bandpass", [250, 1400]) * 0.3
    return loopify(sat(out + whine + rush, 1.3), 0.2)


def ramp_open():
    """Hydraulic whine as the ramp lowers, ending in a heavy clunk."""
    d = 2.2
    whine = filt(sweep(210, 320, 1.7, "saw"), "bandpass", [180, 1400]) * env_adsr(1.7, 0.2, 0.2, 0.8, 0.3) * 0.3
    hiss = filt(noise(1.7), "bandpass", [1500, 5000]) * env_adsr(1.7, 0.3, 0.2, 0.5, 0.4) * 0.08
    clunk = (filt(noise(0.35), "bandpass", [120, 900]) * env_exp(0.35, 0.05) * 0.9
             + tone(58, 0.35) * env_exp(0.35, 0.08) * 0.8
             + filt(noise(0.35), "bandpass", [1800, 4200]) * env_exp(0.35, 0.012) * 0.35)
    return reverb(at(whine + hiss, 0, d) + at(clunk, 1.72, d), 0.9, 0.3, 2500)


def chute_pop():
    """Canopy snatch: a fabric crack, a low whump as it fills, a flutter."""
    d = 0.7
    crack = filt(noise(d), "bandpass", [600, 4000]) * env_exp(d, 0.03, 0.003) * 1.8
    whump = filt(brown(d), "bandpass", [90, 420]) * env_exp(d, 0.1, 0.01) * 0.9
    flutter = filt(noise(d), "bandpass", [200, 1200]) * env_exp(d, 0.2) * (0.5 + 0.5 * np.sin(2 * np.pi * 23 * t(d))) * 0.35
    return reverb(sat(crack * 0.8 + whump + flutter, 1.6), 0.6, 0.25, 2500)


def landing_thud():
    """A soldier hitting sand: a dull thump and a short hiss of sand."""
    d = 0.55
    thump = filt(noise(d), "bandpass", [120, 700]) * env_exp(d, 0.05, 0.003) * 1.4 + tone(110, d) * env_exp(d, 0.06) * 0.4
    sand = filt(noise(d), "bandpass", [1200, 5000]) * env_adsr(d, 0.01, 0.05, 0.25, 0.3) * 0.35
    return sat(thump + sand, 1.4)


def platform_thud():
    """A heavy-drop platform slamming into the ground: a deep boom, the
    crush pads, a metal clank and a rattle of lashings."""
    d = 1.6
    boom = filt(brown(d), "lowpass", 140) * env_exp(d, 0.35, 0.004) * 1.4 + tone(40, d) * env_exp(d, 0.3) * 0.8
    crush = filt(noise(d), "bandpass", [250, 1600]) * env_exp(d, 0.14, 0.003) * 1.6
    clank = sum(tone(f, d) * env_exp(d, tau, 0.002) for f, tau in ((410, 0.25), (655, 0.18), (1170, 0.1))) * 0.35
    n = int(d * SR)
    rattle = (RNG.random(n) > 0.997) * RNG.uniform(-1, 1, n)
    rattle = filt(rattle, "bandpass", [700, 4000]) * env_exp(d, 0.4) * 1.2
    return reverb(sat(boom + crush + clank + at(rattle, 0.08, d), 2.0), 1.0, 0.25, 2000)


def deflect_ping():
    """A round glancing off something that can't be hurt yet: a soft,
    clean metallic ping (inharmonic partials, fast decay), no zing."""
    d = 0.4
    partials = ((2150, 0.09, 1.0), (3320, 0.06, 0.55), (5010, 0.035, 0.3), (1260, 0.05, 0.25))
    ping = sum(sweep(f, f * 0.985, d) * env_exp(d, tau, 0.0015) * a for f, tau, a in partials)
    tick = filt(noise(0.015), "highpass", 3500) * env_exp(0.015, 0.002) * 0.4
    return reverb(pad(mix(ping * 0.6, tick), d), 0.3, 0.12, 6000)


SOUNDS = [
    # name, generator, loop
    ("MachineGun", machine_gun, False),
    ("Overheat", overheat, False),
    ("Empty", click_pair, False),
    ("Reload", reload_sfx, False),
    ("WeaponSwitch", weapon_switch, False),
    ("RocketLaunch", rocket_launch, False),
    ("MissileLaunch", missile_launch, False),
    ("LockTone", lock_tone, False),
    ("LockAcquired", lock_acquired, False),
    ("Explosion", lambda: explosion(1.0), False),
    ("ExplosionSmall", lambda: explosion(0.55, 1.3), False),
    ("AirBurst", air_burst, False),
    ("Ricochet", ricochet, False),
    ("Hit", hit_tick, False),
    ("Kill", kill_confirm, False),
    ("Damage", lambda: damage_thud(False), False),
    ("HeavyHit", lambda: damage_thud(True), False),
    ("Alarm", alarm_loop, True),
    ("JetSiren", jet_siren, False),
    ("JetFlyby", jet_flyby, False),
    ("HeliRotor", heli_loop, True),
    ("TankEngine", tank_engine_loop, True),
    ("BuggyEngine", buggy_engine_loop, True),
    ("TankCannon", tank_cannon, False),
    ("CannonCharge", cannon_charge, False),
    ("WaveStart", wave_start, False),
    ("WaveClear", wave_clear, False),
    ("CratePickup", crate_pickup, False),
    ("CrateDrop", crate_drop, False),
    ("Victory", victory, False),
    ("Defeat", defeat, False),
    ("Wind", wind_loop, True),
    ("EnemyRifle", enemy_rifle, False),
    ("HeliRockets", heli_rockets, False),
    ("BombWhistle", bomb_whistle, False),
    ("InfantryDeath", infantry_death, False),
    # AD-2 airdrop sounds (appended: earlier regions keep their offsets).
    ("TransportDrone", transport_drone_loop, True),
    ("RampOpen", ramp_open, False),
    ("ChutePop", chute_pop, False),
    ("LandingThud", landing_thud, False),
    ("PlatformThud", platform_thud, False),
    ("DeflectPing", deflect_ping, False),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sheet = []
    manifest = {}
    cursor = 0.0
    gap = np.zeros(int(GAP * SR))
    for name, gen, loop in SOUNDS:
        x = norm(np.asarray(gen(), dtype=np.float64))
        start = cursor
        length = len(x) / SR
        manifest[name] = {"start": round(start, 4), "stop": round(start + length, 4), "loop": loop}
        sheet.extend([x, gap])
        cursor += length + GAP
    data = np.concatenate(sheet)
    wav = OUT / "sfx_sheet.wav"
    from scipy.io import wavfile

    wavfile.write(wav, SR, (data * 32767).astype(np.int16))
    (OUT / "sfx_sheet.json").write_text(json.dumps(manifest, indent=2))
    print(f"{len(SOUNDS)} sounds, {cursor:.1f}s -> {wav}")


if __name__ == "__main__":
    main()
