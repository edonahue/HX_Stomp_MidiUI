"""
hx_models.py

Catalog of Line 6 HX Stomp amp and effect model IDs with descriptions and
default parameters.  Used by hlx_builder.py to construct valid .hlx preset
files and to build the LLM system prompt.

Model IDs are community-documented (not officially published by Line 6).
Sources: helix-preset-viewer (hxModels.js), helix-py-api, phelix, real .hlx
files from EmmanuelBeziat/helix-presets.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HXModel:
    model_id:       str         # "HD2_AmpBritPlexiNrm"
    name:           str         # "Brit Plexi Nrm"
    category:       str         # "Amp" | "Cab" | "Distortion" | "Delay" | ...
    description:    str         # one-line tone character for LLM prompt
    default_params: dict        # sane starting values (most knobs 0.0-1.0)
    paired_cab:     str = ""    # best-match cab model_id (amps only)


# ---------------------------------------------------------------------------
# Amp models
# ---------------------------------------------------------------------------

AMP_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_AmpUSDoubleNrm",
        name        = "US Double Nrm",
        category    = "Amp",
        description = "Fender Twin-style clean with extended headroom. Bright, glassy, country/jazz.",
        default_params = {"Drive": 0.30, "Bass": 0.50, "Mid": 0.45, "Treble": 0.60,
                          "Master": 0.80, "ChVol": 1.0, "Sag": 0.50, "Bias": 0.50,
                          "BiasX": 0.50, "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_2x12DoubleC12N",
    ),
    HXModel(
        model_id    = "HD2_AmpUSSmallTweed",
        name        = "US Small Tweed",
        category    = "Amp",
        description = "Small tweed Fender. Warm, punchy breakup. Blues and roots rock.",
        default_params = {"Drive": 0.55, "Bass": 0.50, "Treble": 0.55,
                          "Master": 0.75, "ChVol": 1.0, "Sag": 0.60,
                          "Bias": 0.55, "BiasX": 0.50, "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_1x12USDeluxe",
    ),
    HXModel(
        model_id    = "HD2_AmpTweedBluesBrt",
        name        = "Tweed Blues Brt",
        category    = "Amp",
        description = "Tweed Bassman-style. Thick, harmonically rich overdrive. Classic blues/rock.",
        default_params = {"Drive": 0.60, "Bass": 0.50, "Mid": 0.55, "Treble": 0.55,
                          "Master": 0.80, "ChVol": 1.0, "Sag": 0.55,
                          "Bias": 0.55, "BiasX": 0.50, "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x10TweedP10R",
    ),
    HXModel(
        model_id    = "HD2_AmpMatchstickCh1",
        name        = "Matchstick Ch1",
        category    = "Amp",
        description = "Matchless DC-30 Ch1. Vox-like chime, sparkly clean to light crunch.",
        default_params = {"Drive": 0.40, "Bass": 0.45, "Cut": 0.50, "Treble": 0.60,
                          "Master": 0.75, "ChVol": 1.0, "Sag": 0.50,
                          "Bias": 0.50, "BiasX": 0.50, "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_2x12BlueBell",
    ),
    HXModel(
        model_id    = "HD2_AmpA30FawnNrm",
        name        = "A30 Fawn Nrm",
        category    = "Amp",
        description = "Vox AC30-style. Bright chime, compressed, jangly. Britpop and indie.",
        default_params = {"Drive": 0.40, "Bass": 0.45, "Cut": 0.50, "Treble": 0.60,
                          "Master": 0.75, "ChVol": 1.0, "Sag": 0.50,
                          "Bias": 0.50, "BiasX": 0.50, "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_2x12BlueBell",
    ),
    HXModel(
        model_id    = "HD2_AmpBritPlexiNrm",
        name        = "Brit Plexi Nrm",
        category    = "Amp",
        description = "Marshall Plexi Nrm channel. Classic British crunch, note-by-note dynamics. Rock.",
        default_params = {"Drive": 0.55, "Bass": 0.50, "Mid": 0.55, "Treble": 0.55,
                          "Presence": 0.50, "Master": 0.70, "ChVol": 1.0,
                          "Sag": 0.50, "Bias": 0.50, "BiasX": 0.50,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12Greenback25",
    ),
    HXModel(
        model_id    = "HD2_AmpBritPlexiBrt",
        name        = "Brit Plexi Brt",
        category    = "Amp",
        description = "Marshall Plexi Brt channel. Brighter, tighter crunch. Classic hard rock.",
        default_params = {"Drive": 0.60, "Bass": 0.45, "Mid": 0.55, "Treble": 0.60,
                          "Presence": 0.55, "Master": 0.70, "ChVol": 1.0,
                          "Sag": 0.50, "Bias": 0.50, "BiasX": 0.50,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12Greenback25",
    ),
    HXModel(
        model_id    = "HD2_AmpBritJ45Nrm",
        name        = "Brit J45 Nrm",
        category    = "Amp",
        description = "Marshall JMP 45W. Crunchy, mid-forward British tone. Classic rock lead.",
        default_params = {"Drive": 0.60, "Bass": 0.50, "Mid": 0.60, "Treble": 0.55,
                          "Presence": 0.50, "Master": 0.70, "ChVol": 1.0,
                          "Sag": 0.50, "Bias": 0.50, "BiasX": 0.50,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12Greenback25",
    ),
    HXModel(
        model_id    = "HD2_AmpPlacaterDirty",
        name        = "Placater Dirty",
        category    = "Amp",
        description = "Friedman BE-100 Dirty channel. High-gain, tight, punchy. Modern hard rock and metal.",
        default_params = {"Drive": 0.65, "Bass": 0.50, "Mid": 0.50, "Treble": 0.55,
                          "Presence": 0.55, "Master": 0.65, "ChVol": 1.0,
                          "Sag": 0.35, "Bias": 0.50, "BiasX": 0.50,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12CaliV30",
    ),
    HXModel(
        model_id    = "HD2_AmpCaliRectifire",
        name        = "Cali Rectifire",
        category    = "Amp",
        description = "Mesa Boogie Dual Rectifier. Massive high gain, scooped. Heavy metal.",
        default_params = {"Drive": 0.70, "Bass": 0.55, "Mid": 0.40, "Treble": 0.55,
                          "Presence": 0.55, "Master": 0.60, "ChVol": 1.0,
                          "Sag": 0.40, "Bias": 0.50, "BiasX": 0.50,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12CaliV30",
    ),
    HXModel(
        model_id    = "HD2_AmpPVPanama",
        name        = "PV Panama",
        category    = "Amp",
        description = "Peavey 5150 / EVH. Aggressive high gain, tight low end. Metal.",
        default_params = {"Drive": 0.70, "Bass": 0.50, "Mid": 0.45, "Treble": 0.55,
                          "Presence": 0.55, "Master": 0.60, "ChVol": 1.0,
                          "Sag": 0.35, "Bias": 0.55, "BiasX": 0.55,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12XXLV30",
    ),
    HXModel(
        model_id    = "HD2_AmpLine6Litigator",
        name        = "Line 6 Litigator",
        category    = "Amp",
        description = "Line 6 original. Versatile touch-sensitive crunch/high-gain. Great for lead tones.",
        default_params = {"Drive": 0.60, "Bass": 0.50, "Mid": 0.55, "Treble": 0.55,
                          "Presence": 0.50, "Master": 0.70, "ChVol": 1.0,
                          "Sag": 0.50, "Bias": 0.50, "BiasX": 0.50,
                          "Hum": 0.50, "Ripple": 0.50},
        paired_cab  = "HD2_CabMicIr_4x12CaliV30",
    ),
]


# ---------------------------------------------------------------------------
# Cab models  (current HD2_CabMicIr_* format, firmware 3.50+)
# ---------------------------------------------------------------------------

CAB_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_CabMicIr_1x12USDeluxe",
        name        = "1x12 US Deluxe",
        category    = "Cab",
        description = "Small Fender 1x12. Warm, tight, clean-friendly.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_2x12DoubleC12N",
        name        = "2x12 Double C12N",
        category    = "Cab",
        description = "Fender Twin 2x12. Open, airy. Suits clean and light-crunch amps.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_2x12BlueBell",
        name        = "2x12 Blue Bell",
        category    = "Cab",
        description = "Vox 2x12 with Celestion Blues. Chime, presence. Vox and British amps.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_4x10TweedP10R",
        name        = "4x10 Tweed P10R",
        category    = "Cab",
        description = "Bassman 4x10. Full-range with sparkle. Blues tweed tones.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 60.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_4x12Greenback25",
        name        = "4x12 Greenback 25",
        category    = "Cab",
        description = "Marshall 4x12 with Celestion Greenbacks. Warm, middy. Classic rock.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_4x12CaliV30",
        name        = "4x12 Cali V30",
        category    = "Cab",
        description = "Mesa 4x12 with Celestion V30s. Scooped, tight. Modern high-gain.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_4x12XXLV30",
        name        = "4x12 XXL V30",
        category    = "Cab",
        description = "Large 4x12 V30 cab. Massive low end. Heavy and metal tones.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 7000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
    HXModel(
        model_id    = "HD2_CabMicIr_1x12Fullerton",
        name        = "1x12 Fullerton",
        category    = "Cab",
        description = "Compact 1x12. Balanced, versatile. Good all-rounder.",
        default_params = {"Mic": 0, "Distance": 1.0, "HighCut": 8000.0,
                          "Level": 0.0, "LowCut": 80.0},
    ),
]


# ---------------------------------------------------------------------------
# Distortion / overdrive / fuzz
# ---------------------------------------------------------------------------

DISTORTION_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_DistScream808",
        name        = "Scream 808",
        category    = "Distortion",
        description = "Ibanez Tube Screamer. Mid-boost, smooth overdrive. Blues and rock.",
        default_params = {"Drive": 0.50, "Tone": 0.50, "Level": 0.60},
    ),
    HXModel(
        model_id    = "HD2_DistMinotaur",
        name        = "Minotaur",
        category    = "Distortion",
        description = "Klon Centaur. Transparent drive, adds harmonic shimmer. Low-to-mid gain.",
        default_params = {"Gain": 0.45, "Tone": 0.50, "Level": 0.65},
    ),
    HXModel(
        model_id    = "HD2_DistTeemah",
        name        = "Teemah!",
        category    = "Distortion",
        description = "Paul Cochrane Timmy. Transparent, musical breakup. Touch-sensitive.",
        default_params = {"Drive": 0.50, "Bass": 0.50, "Treble": 0.50, "Level": 0.60},
    ),
    HXModel(
        model_id    = "HD2_DistKinkyBoost",
        name        = "Kinky Boost",
        category    = "Distortion",
        description = "Xotic EP Booster. Clean boost with musical EQ. Adds dimension.",
        default_params = {"Gain": 0.35, "Level": 0.70},
    ),
    HXModel(
        model_id    = "HD2_DistVerminDist",
        name        = "Vermin Dist",
        category    = "Distortion",
        description = "ProCo RAT. Hard-clipping distortion, aggressive mids. Punk and grunge.",
        default_params = {"Distortion": 0.60, "Filter": 0.50, "Level": 0.60},
    ),
    HXModel(
        model_id    = "HD2_DistArbitratorFuzz",
        name        = "Arbitrator Fuzz",
        category    = "Distortion",
        description = "Arbiter Fuzz Face. Vintage silicon fuzz. Hendrix and psychedelic rock.",
        default_params = {"Fuzz": 0.65, "Level": 0.60},
    ),
    HXModel(
        model_id    = "HD2_DistRamsHead",
        name        = "Ram's Head",
        category    = "Distortion",
        description = "EHX Big Muff Ram's Head. Thick, sustaining fuzz. Prog and shoegaze.",
        default_params = {"Sustain": 0.65, "Tone": 0.50, "Level": 0.60},
    ),
    HXModel(
        model_id    = "HD2_DistHeirApparent",
        name        = "Heir Apparent",
        category    = "Distortion",
        description = "OCD overdrive. High-headroom drive, tight and punchy. Rock and metal.",
        default_params = {"Drive": 0.55, "Tone": 0.50, "Level": 0.60},
    ),
]


# ---------------------------------------------------------------------------
# Delay
# ---------------------------------------------------------------------------

DELAY_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_DelaySimpleDelay",
        name        = "Simple Delay",
        category    = "Delay",
        description = "Clean digital delay. Transparent repeats. Versatile.",
        default_params = {"Time": 0.35, "Feedback": 0.30, "Mix": 0.25, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_DelayTransistorTape",
        name        = "Transistor Tape",
        category    = "Delay",
        description = "Analog tape-style delay. Warm, slightly degrading repeats. Classic rock.",
        default_params = {"Time": 0.35, "Feedback": 0.30, "Mix": 0.25, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_DelayBucketBrigade",
        name        = "Bucket Brigade",
        category    = "Delay",
        description = "BBD analog delay. Dark, modulated repeats. Vintage character.",
        default_params = {"Time": 0.30, "Feedback": 0.28, "Mix": 0.22, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_DelayElephantMan",
        name        = "Elephant Man",
        category    = "Delay",
        description = "Maestro Echoplex-style. Warm, musical tape echo. U2-style dotted 8th.",
        default_params = {"Time": 0.40, "Feedback": 0.35, "Mix": 0.28, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_DelayPingPong",
        name        = "Ping Pong",
        category    = "Delay",
        description = "Stereo ping-pong delay. Wide, immersive. Ambient and lead.",
        default_params = {"Time": 0.35, "Feedback": 0.30, "Mix": 0.25, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_DelayAdriaticDelay",
        name        = "Adriatic Delay",
        category    = "Delay",
        description = "TC Electronic TonePrint-style delay. Versatile, studio-quality repeats.",
        default_params = {"Time": 0.35, "Feedback": 0.30, "Mix": 0.25, "Trails": False},
    ),
]


# ---------------------------------------------------------------------------
# Reverb
# ---------------------------------------------------------------------------

REVERB_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_ReverbPlate",
        name        = "Plate Reverb",
        category    = "Reverb",
        description = "Classic studio plate reverb. Dense, smooth tail. Suits most genres.",
        default_params = {"Decay": 0.35, "Predelay": 0.0, "Mix": 0.22, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_Reverb63Spring",
        name        = "63 Spring",
        category    = "Reverb",
        description = "1963 tank spring reverb. Splashy, vintage character. Blues and surf.",
        default_params = {"Decay": 0.40, "Dwell": 0.50, "Mix": 0.22, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_ReverbRoom",
        name        = "Room Reverb",
        category    = "Reverb",
        description = "Small room ambience. Natural, realistic. Subtle presence without wash.",
        default_params = {"Decay": 0.25, "Predelay": 0.0, "Mix": 0.18, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_ReverbHall",
        name        = "Hall Reverb",
        category    = "Reverb",
        description = "Large concert hall reverb. Long, lush decay. Ambient and lead.",
        default_params = {"Decay": 0.55, "Predelay": 0.05, "Mix": 0.25, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_ReverbGanymede",
        name        = "Ganymede",
        category    = "Reverb",
        description = "Shimmer reverb. Ethereal, pitch-shifted reflections. Ambient and experimental.",
        default_params = {"Decay": 0.60, "Shimmer": 0.40, "Mix": 0.30, "Trails": False},
    ),
    HXModel(
        model_id    = "HD2_ReverbSearchlights",
        name        = "Searchlights",
        category    = "Reverb",
        description = "Modulated reverb. Slowly moving, wide soundscape. Post-rock and ambient.",
        default_params = {"Decay": 0.55, "Mod": 0.40, "Mix": 0.28, "Trails": False},
    ),
]


# ---------------------------------------------------------------------------
# Modulation
# ---------------------------------------------------------------------------

MODULATION_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_Chorus",
        name        = "Chorus",
        category    = "Modulation",
        description = "Classic analog chorus. Lush, swirling. 80s clean tones.",
        default_params = {"Rate": 0.35, "Depth": 0.45, "Mix": 0.50},
    ),
    HXModel(
        model_id    = "HD2_TremoloTremolo",
        name        = "Tremolo",
        category    = "Modulation",
        description = "Classic optical tremolo. Pulsing volume. Surf and vintage country.",
        default_params = {"Rate": 0.40, "Depth": 0.60, "Wave": 0.0},
    ),
    HXModel(
        model_id    = "HD2_FlangerGrayFlanger",
        name        = "Gray Flanger",
        category    = "Modulation",
        description = "MXR 117 flanger. Sweeping jet effect. Van Halen-style.",
        default_params = {"Rate": 0.30, "Depth": 0.60, "Mix": 0.50},
    ),
    HXModel(
        model_id    = "HD2_PhaserScriptModPhase",
        name        = "Script Mod Phase",
        category    = "Modulation",
        description = "MXR Phase 45/90 script logo. Smooth, musical phasing. Funk and classic rock.",
        default_params = {"Rate": 0.30, "Mix": 0.50},
    ),
    HXModel(
        model_id    = "HD2_Rotary145Rotary",
        name        = "Rotary",
        category    = "Modulation",
        description = "Leslie 145 rotary speaker. Doppler-effect wobble. Organ-like, ambient.",
        default_params = {"Speed": 0.40, "Mix": 0.70},
    ),
]


# ---------------------------------------------------------------------------
# Dynamics (compressors + gates)
# ---------------------------------------------------------------------------

DYNAMICS_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_CompressorRedSqueeze",
        name        = "Red Squeeze",
        category    = "Dynamics",
        description = "MXR Dyna Comp. Poppy, pronounced squish. Country and funk.",
        default_params = {"Sustain": 0.50, "Level": 0.65, "Attack": 0.40},
    ),
    HXModel(
        model_id    = "HD2_CompressorDeluxeComp",
        name        = "Deluxe Comp",
        category    = "Dynamics",
        description = "Diamond CPR1 compressor. Transparent, musical. Suits clean to medium gain.",
        default_params = {"Comp": 0.45, "Attack": 0.40, "Gain": 0.0, "Mix": 1.0},
    ),
    HXModel(
        model_id    = "HD2_CompressorKinkyComp",
        name        = "Kinky Comp",
        category    = "Dynamics",
        description = "Xotic SP compressor. Subtle, studio-style. Adds sustain without squishing.",
        default_params = {"Comp": 0.40, "Attack": 0.40, "Mix": 1.0},
    ),
    HXModel(
        model_id    = "HD2_GateNoiseGate",
        name        = "Noise Gate",
        category    = "Dynamics",
        description = "Simple noise gate. Cuts hum and hiss between notes.",
        default_params = {"Threshold": -65.0, "Decay": 0.10},
    ),
]


# ---------------------------------------------------------------------------
# EQ
# ---------------------------------------------------------------------------

EQ_MODELS: list[HXModel] = [
    HXModel(
        model_id    = "HD2_EQParametric",
        name        = "Parametric EQ",
        category    = "EQ",
        description = "Parametric EQ with sweepable mids. Surgical tone shaping.",
        default_params = {"LowFreq": 100.0, "LowGain": 0.0, "MidFreq": 800.0,
                          "MidGain": 0.0, "HighFreq": 5000.0, "HighGain": 0.0,
                          "Level": 0.0},
    ),
    HXModel(
        model_id    = "HD2_EQLowCutHighCut",
        name        = "Low/High Cut",
        category    = "EQ",
        description = "Simple HP/LP filter pair. Cleans up muddiness or harshness.",
        default_params = {"LowCut": 80.0, "HighCut": 8000.0, "Level": 0.0},
    ),
    HXModel(
        model_id    = "HD2_EQGraphic10Band",
        name        = "10 Band EQ",
        category    = "EQ",
        description = "10-band graphic EQ. Full spectrum tone control.",
        default_params = {"31p25Hz": 0.0, "62p5Hz": 0.0, "125Hz": 0.0,
                          "250Hz": 0.0, "500Hz": 0.0, "1kHz": 0.0,
                          "2kHz": 0.0, "4kHz": 0.0, "8kHz": 0.0,
                          "16kHz": 0.0, "Level": 0.0},
    ),
]


# ---------------------------------------------------------------------------
# Master lookup
# ---------------------------------------------------------------------------

ALL_MODELS: dict[str, HXModel] = {
    m.model_id: m
    for m in (
        AMP_MODELS
        + CAB_MODELS
        + DISTORTION_MODELS
        + DELAY_MODELS
        + REVERB_MODELS
        + MODULATION_MODELS
        + DYNAMICS_MODELS
        + EQ_MODELS
    )
}

_CATEGORY_ORDER = [
    "Amp", "Cab", "Distortion", "Dynamics", "EQ",
    "Modulation", "Delay", "Reverb",
]

_CATEGORY_LISTS: dict[str, list[HXModel]] = {
    "Amp":        AMP_MODELS,
    "Cab":        CAB_MODELS,
    "Distortion": DISTORTION_MODELS,
    "Delay":      DELAY_MODELS,
    "Reverb":     REVERB_MODELS,
    "Modulation": MODULATION_MODELS,
    "Dynamics":   DYNAMICS_MODELS,
    "EQ":         EQ_MODELS,
}


def catalog_for_prompt(categories: list[str] | None = None) -> str:
    """
    Return a compact text representation of the model catalog for injection
    into the LLM system prompt.

    Each line: `- <model_id> | <name> | <description>`

    Pass `categories` to include only a subset (e.g. ["Amp", "Distortion"]).
    """
    cats = categories or _CATEGORY_ORDER
    lines: list[str] = []
    for cat in cats:
        models = _CATEGORY_LISTS.get(cat, [])
        if not models:
            continue
        lines.append(f"\n## {cat}s" if cat != "EQ" else "\n## EQ")
        for m in models:
            lines.append(f"- {m.model_id} | {m.name} | {m.description}")
    return "\n".join(lines).strip()
