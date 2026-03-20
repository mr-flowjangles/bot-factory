#!/usr/bin/env python3
"""
Knowledge Coverage Regression Test (Retrieval-Only)

Tests retrieval scores for every topic in the bot's knowledge base.
Calls retrieve_relevant_chunks() directly — no LLM calls, no self-heal.

A question FAILs if its top retrieval score is below the bot's
confidence_threshold (default 0.6).

Usage:
    python3 scripts/test_knowledge_coverage.py              # run against local DynamoDB
    python3 scripts/test_knowledge_coverage.py --prod       # run against prod DynamoDB
    make test-coverage                                      # prod (Makefile target)
    make test-coverage-local                                # local (Makefile target)
"""

import os
import sys
import time
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path so we can import factory modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Set APP_ENV before importing factory modules
if "--prod" in sys.argv:
    os.environ["APP_ENV"] = "production"
    # Clear LocalStack test credentials so boto3 uses real AWS
    os.environ.pop("AWS_ACCESS_KEY_ID", None)
    os.environ.pop("AWS_SECRET_ACCESS_KEY", None)

from factory.core.retrieval import retrieve_relevant_chunks  # noqa: E402
from factory.core.bot_utils import load_bot_config  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BOT_ID = "the-fret-detective"

RESULTS_DIR = "_scratch"
RESULTS_FILE = os.path.join(RESULTS_DIR, "coverage_results.yml")

# ---------------------------------------------------------------------------
# All landing page topics — grouped by category
# ---------------------------------------------------------------------------

QUESTIONS = [
    # ── Guitar Basics ──
    {"category": "Guitar Basics", "topic": "Parts of guitar", "question": "What are the parts of an electric guitar?"},
    {"category": "Guitar Basics", "topic": "Parts of guitar", "question": "Can you name the different components on a guitar?"},
    {"category": "Guitar Basics", "topic": "Parts of guitar", "question": "Tell me about the headstock, pickups, bridge and other guitar parts"},
    {"category": "Guitar Basics", "topic": "Parts of guitar", "question": "Can you walk me through the parts of a guitar?"},
    {"category": "Guitar Basics", "topic": "Parts of guitar", "question": "What is each part of an electric guitar called?"},
    {"category": "Guitar Basics", "topic": "Parts of guitar", "question": "Can you explain what all the guitar parts do?"},

    {"category": "Guitar Basics", "topic": "String names", "question": "What are the string names and numbers on a guitar?"},
    {"category": "Guitar Basics", "topic": "String names", "question": "Which string is which on a guitar?"},
    {"category": "Guitar Basics", "topic": "String names", "question": "What does EADGBE mean?"},
    {"category": "Guitar Basics", "topic": "String names", "question": "How are the guitar strings named?"},
    {"category": "Guitar Basics", "topic": "String names", "question": "Which string is the low E and which one is the high E?"},
    {"category": "Guitar Basics", "topic": "String names", "question": "Can you help me remember the guitar string names?"},

    {"category": "Guitar Basics", "topic": "Holding guitar", "question": "How do I hold an electric guitar properly?"},
    {"category": "Guitar Basics", "topic": "Holding guitar", "question": "What is the correct posture for playing guitar?"},
    {"category": "Guitar Basics", "topic": "Holding guitar", "question": "Show me how to hold a guitar and pick"},
    {"category": "Guitar Basics", "topic": "Holding guitar", "question": "What's the best way to sit with a guitar?"},
    {"category": "Guitar Basics", "topic": "Holding guitar", "question": "How should I position my hands when holding a guitar?"},
    {"category": "Guitar Basics", "topic": "Holding guitar", "question": "Can you show me proper guitar posture for beginners?"},

    {"category": "Guitar Basics", "topic": "Reading tab", "question": "How do I read guitar tab notation?"},
    {"category": "Guitar Basics", "topic": "Reading tab", "question": "What do the numbers on guitar tabs mean?"},
    {"category": "Guitar Basics", "topic": "Reading tab", "question": "Explain tablature to me"},
    {"category": "Guitar Basics", "topic": "Reading tab", "question": "Can you teach me how to read guitar tabs?"},
    {"category": "Guitar Basics", "topic": "Reading tab", "question": "How am I supposed to understand tablature?"},
    {"category": "Guitar Basics", "topic": "Reading tab", "question": "What do all the lines and numbers in guitar tab mean?"},

    {"category": "Guitar Basics", "topic": "Fret numbering", "question": "How does fret numbering work on a guitar?"},
    {"category": "Guitar Basics", "topic": "Fret numbering", "question": "Which fret is which on the neck?"},
    {"category": "Guitar Basics", "topic": "Fret numbering", "question": "Where is the 5th fret on a guitar?"},
    {"category": "Guitar Basics", "topic": "Fret numbering", "question": "How do I know which fret I'm on?"},
    {"category": "Guitar Basics", "topic": "Fret numbering", "question": "Can you explain how frets are numbered on guitar?"},
    {"category": "Guitar Basics", "topic": "Fret numbering", "question": "How do I find a certain fret on the neck?"},

    # ── Open Chords ──
    {"category": "Chords", "topic": "A major", "question": "Show me an A major chord"},
    {"category": "Chords", "topic": "A major", "question": "How do I play an A chord on guitar?"},
    {"category": "Chords", "topic": "A major", "question": "What's the fingering for A major?"},
    {"category": "Chords", "topic": "A major", "question": "What does an A major chord look like on guitar?"},
    {"category": "Chords", "topic": "A major", "question": "Can you show me where to put my fingers for A major?"},
    {"category": "Chords", "topic": "A major", "question": "What's the easiest way to play A major?"},

    {"category": "Chords", "topic": "A minor", "question": "How do I play an Am chord?"},
    {"category": "Chords", "topic": "A minor", "question": "Show me A minor on guitar"},
    {"category": "Chords", "topic": "A minor", "question": "What does Am look like?"},
    {"category": "Chords", "topic": "A minor", "question": "Can you show me the finger placement for A minor?"},
    {"category": "Chords", "topic": "A minor", "question": "What's the easiest way to play Am?"},
    {"category": "Chords", "topic": "A minor", "question": "Where do my fingers go for an A minor chord?"},

    {"category": "Chords", "topic": "C major", "question": "Show me a C major chord"},
    {"category": "Chords", "topic": "C major", "question": "How do I play C on guitar?"},
    {"category": "Chords", "topic": "C major", "question": "What's the fingering for a C chord?"},
    {"category": "Chords", "topic": "C major", "question": "What does a C chord look like on guitar?"},
    {"category": "Chords", "topic": "C major", "question": "Can you show me how to finger C major?"},
    {"category": "Chords", "topic": "C major", "question": "Where do I put my fingers for a C chord?"},

    {"category": "Chords", "topic": "D major", "question": "How do I play a D chord?"},
    {"category": "Chords", "topic": "D major", "question": "Show me D major on guitar"},
    {"category": "Chords", "topic": "D major", "question": "What does a D chord look like?"},
    {"category": "Chords", "topic": "D major", "question": "Can you show me the finger placement for D major?"},
    {"category": "Chords", "topic": "D major", "question": "What's the easiest way to make a D chord?"},
    {"category": "Chords", "topic": "D major", "question": "Where do my fingers go for D major?"},

    {"category": "Chords", "topic": "D minor", "question": "Show me D minor"},
    {"category": "Chords", "topic": "D minor", "question": "How do I play a Dm chord?"},
    {"category": "Chords", "topic": "D minor", "question": "What's the fingering for D minor?"},
    {"category": "Chords", "topic": "D minor", "question": "What does a D minor chord look like?"},
    {"category": "Chords", "topic": "D minor", "question": "Can you show me where to put my fingers for Dm?"},
    {"category": "Chords", "topic": "D minor", "question": "What's the easiest way to play D minor?"},

    {"category": "Chords", "topic": "E major", "question": "How do I play E major?"},
    {"category": "Chords", "topic": "E major", "question": "Show me an E chord"},
    {"category": "Chords", "topic": "E major", "question": "What does E major look like on guitar?"},
    {"category": "Chords", "topic": "E major", "question": "Can you show me how to finger an E major chord?"},
    {"category": "Chords", "topic": "E major", "question": "Where do my fingers go for E major?"},
    {"category": "Chords", "topic": "E major", "question": "What's the easiest way to play an E chord?"},

    {"category": "Chords", "topic": "E minor", "question": "Show me E minor"},
    {"category": "Chords", "topic": "E minor", "question": "How do I play Em on guitar?"},
    {"category": "Chords", "topic": "E minor", "question": "What's the easiest way to play E minor?"},
    {"category": "Chords", "topic": "E minor", "question": "What does an E minor chord look like?"},
    {"category": "Chords", "topic": "E minor", "question": "Can you show me the finger placement for Em?"},
    {"category": "Chords", "topic": "E minor", "question": "Where do I put my fingers for E minor?"},

    {"category": "Chords", "topic": "F major", "question": "How do I play an F chord?"},
    {"category": "Chords", "topic": "F major", "question": "Show me an easy F chord that doesn't wreck my hand"},
    {"category": "Chords", "topic": "F major", "question": "What's the trick to playing F on guitar?"},
    {"category": "Chords", "topic": "F major", "question": "Can you show me a beginner-friendly way to play F?"},
    {"category": "Chords", "topic": "F major", "question": "What does an F chord look like on guitar?"},
    {"category": "Chords", "topic": "F major", "question": "How should I finger the F chord?"},

    {"category": "Chords", "topic": "G major", "question": "Show me a G chord"},
    {"category": "Chords", "topic": "G major", "question": "How do I play G major?"},
    {"category": "Chords", "topic": "G major", "question": "What's the fingering for a G chord?"},
    {"category": "Chords", "topic": "G major", "question": "What does a G major chord look like?"},
    {"category": "Chords", "topic": "G major", "question": "Can you show me where to put my fingers for G?"},
    {"category": "Chords", "topic": "G major", "question": "What's the easiest way to play a G chord?"},

    # ── Barre Chords ──
    {"category": "Chords", "topic": "Barre chords", "question": "How do I play barre chords?"},
    {"category": "Chords", "topic": "Barre chords", "question": "What is a barre chord and how does it work?"},
    {"category": "Chords", "topic": "Barre chords", "question": "Any tips for getting barre chords to ring clean?"},
    {"category": "Chords", "topic": "Barre chords", "question": "Can you explain barre chords in a simple way?"},
    {"category": "Chords", "topic": "Barre chords", "question": "Why are barre chords so hard to play cleanly?"},
    {"category": "Chords", "topic": "Barre chords", "question": "How do beginners learn barre chords?"},

    {"category": "Chords", "topic": "E-shape barre", "question": "Show me an E-shape barre chord"},
    {"category": "Chords", "topic": "E-shape barre", "question": "How do I move an E chord shape up the neck?"},
    {"category": "Chords", "topic": "E-shape barre", "question": "What is the E-form barre chord?"},
    {"category": "Chords", "topic": "E-shape barre", "question": "How do I use the E shape to make barre chords?"},
    {"category": "Chords", "topic": "E-shape barre", "question": "Can you show me how an E-form barre chord works?"},
    {"category": "Chords", "topic": "E-shape barre", "question": "How do I turn an open E shape into a movable chord?"},

    {"category": "Chords", "topic": "A-shape barre", "question": "Show me an A-shape barre chord"},
    {"category": "Chords", "topic": "A-shape barre", "question": "How do I use the A chord shape as a barre?"},
    {"category": "Chords", "topic": "A-shape barre", "question": "What is the A-form barre chord?"},
    {"category": "Chords", "topic": "A-shape barre", "question": "How do I move the A chord shape up the neck?"},
    {"category": "Chords", "topic": "A-shape barre", "question": "Can you explain how A-shape barre chords work?"},
    {"category": "Chords", "topic": "A-shape barre", "question": "How do I turn an A chord into a movable barre chord?"},

    # ── Seventh Chords ──
    {"category": "Chords", "topic": "A7", "question": "How do I play A7?"},
    {"category": "Chords", "topic": "A7", "question": "Show me the A dominant 7 chord"},
    {"category": "Chords", "topic": "A7", "question": "What's the fingering for A7 on guitar?"},
    {"category": "Chords", "topic": "A7", "question": "What does an A7 chord look like?"},
    {"category": "Chords", "topic": "A7", "question": "Can you show me where to put my fingers for A7?"},
    {"category": "Chords", "topic": "A7", "question": "What's an easy way to play A7 on guitar?"},

    {"category": "Chords", "topic": "Am7", "question": "Show me Am7"},
    {"category": "Chords", "topic": "Am7", "question": "How do I play A minor 7?"},
    {"category": "Chords", "topic": "Am7", "question": "What does Am7 look like on guitar?"},
    {"category": "Chords", "topic": "Am7", "question": "What does A minor 7 look like on guitar?"},
    {"category": "Chords", "topic": "Am7", "question": "Can you show me the finger placement for Am7?"},
    {"category": "Chords", "topic": "Am7", "question": "What's an easy shape for Am7?"},

    {"category": "Chords", "topic": "D7", "question": "How do I play D7?"},
    {"category": "Chords", "topic": "D7", "question": "Show me a D dominant 7 chord"},
    {"category": "Chords", "topic": "D7", "question": "What's the D7 chord shape?"},
    {"category": "Chords", "topic": "D7", "question": "What does a D7 chord look like on guitar?"},
    {"category": "Chords", "topic": "D7", "question": "Can you show me how to finger D7?"},
    {"category": "Chords", "topic": "D7", "question": "Where do my fingers go for D7?"},

    {"category": "Chords", "topic": "E7", "question": "Show me E7"},
    {"category": "Chords", "topic": "E7", "question": "How do I play E dominant 7?"},
    {"category": "Chords", "topic": "E7", "question": "What does E7 look like?"},
    {"category": "Chords", "topic": "E7", "question": "What does an E7 chord look like on guitar?"},
    {"category": "Chords", "topic": "E7", "question": "Can you show me the finger placement for E7?"},
    {"category": "Chords", "topic": "E7", "question": "What's the easiest way to play E7?"},

    # ── Sus Chords ──
    {"category": "Chords", "topic": "Asus2", "question": "How do I play Asus2?"},
    {"category": "Chords", "topic": "Asus2", "question": "Show me an A suspended 2 chord"},
    {"category": "Chords", "topic": "Asus2", "question": "What does Asus2 look like on guitar?"},
    {"category": "Chords", "topic": "Asus2", "question": "What does an Asus2 chord look like?"},
    {"category": "Chords", "topic": "Asus2", "question": "Can you show me where to put my fingers for Asus2?"},
    {"category": "Chords", "topic": "Asus2", "question": "What's the easiest way to play Asus2?"},

    {"category": "Chords", "topic": "Dsus4", "question": "Show me Dsus4"},
    {"category": "Chords", "topic": "Dsus4", "question": "How do I play D suspended 4?"},
    {"category": "Chords", "topic": "Dsus4", "question": "What's the fingering for Dsus4?"},
    {"category": "Chords", "topic": "Dsus4", "question": "What does a Dsus4 chord look like on guitar?"},
    {"category": "Chords", "topic": "Dsus4", "question": "Can you show me how to finger Dsus4?"},
    {"category": "Chords", "topic": "Dsus4", "question": "Where do my fingers go for a Dsus4 chord?"},

    # ── Power Chords ──
    {"category": "Chords", "topic": "Power chords", "question": "How do I play a power chord?"},
    {"category": "Chords", "topic": "Power chords", "question": "What is a power chord and how is it shaped?"},
    {"category": "Chords", "topic": "Power chords", "question": "Show me the basic power chord shape for rock"},
    {"category": "Chords", "topic": "Power chords", "question": "Can you show me the basic shape for a power chord?"},
    {"category": "Chords", "topic": "Power chords", "question": "How do I play rock power chords on guitar?"},
    {"category": "Chords", "topic": "Power chords", "question": "What do power chords look like on the fretboard?"},

    # ── Triads ──
    {"category": "Triads", "topic": "G major triad", "question": "What are the notes in a G major triad?"},
    {"category": "Triads", "topic": "G major triad", "question": "Show me G major triad voicings on the fretboard"},
    {"category": "Triads", "topic": "G major triad", "question": "How do I play a G triad?"},
    {"category": "Triads", "topic": "G major triad", "question": "Can you show me the notes that make up G major?"},
    {"category": "Triads", "topic": "G major triad", "question": "Where can I find G major triads on guitar?"},
    {"category": "Triads", "topic": "G major triad", "question": "What are the G major triad shapes on the neck?"},

    {"category": "Triads", "topic": "C major triad", "question": "Show me C major triad voicings"},
    {"category": "Triads", "topic": "C major triad", "question": "Where can I play C major triads on the neck?"},
    {"category": "Triads", "topic": "C major triad", "question": "What are the C triad shapes?"},
    {"category": "Triads", "topic": "C major triad", "question": "Can you show me the notes in a C major triad?"},
    {"category": "Triads", "topic": "C major triad", "question": "How do I play C triads on guitar?"},
    {"category": "Triads", "topic": "C major triad", "question": "What does a C major triad look like across the neck?"},

    {"category": "Triads", "topic": "A minor triad", "question": "Show me A minor triad voicings"},
    {"category": "Triads", "topic": "A minor triad", "question": "How do I play Am triads on guitar?"},
    {"category": "Triads", "topic": "A minor triad", "question": "What are the A minor triad shapes?"},
    {"category": "Triads", "topic": "A minor triad", "question": "Can you show me the notes in an A minor triad?"},
    {"category": "Triads", "topic": "A minor triad", "question": "Where can I play A minor triads on guitar?"},
    {"category": "Triads", "topic": "A minor triad", "question": "What do A minor triad shapes look like on the neck?"},

    {"category": "Triads", "topic": "Inversions", "question": "What is root position vs inversions for triads?"},
    {"category": "Triads", "topic": "Inversions", "question": "Explain 1st and 2nd inversion triads"},
    {"category": "Triads", "topic": "Inversions", "question": "What's the difference between root position and an inversion?"},
    {"category": "Triads", "topic": "Inversions", "question": "Can you explain triad inversions in plain English?"},
    {"category": "Triads", "topic": "Inversions", "question": "How do I know if a triad is root position or an inversion?"},
    {"category": "Triads", "topic": "Inversions", "question": "What changes when a triad is inverted?"},

    {"category": "Triads", "topic": "DGB strings", "question": "Show me triads on the DGB strings"},
    {"category": "Triads", "topic": "DGB strings", "question": "What triad voicings can I play on the D G B strings?"},
    {"category": "Triads", "topic": "DGB strings", "question": "Show me three-string triad shapes on the middle strings"},
    {"category": "Triads", "topic": "DGB strings", "question": "Can you show me triad shapes on the D, G, and B strings?"},
    {"category": "Triads", "topic": "DGB strings", "question": "How do triads work on the middle three strings?"},
    {"category": "Triads", "topic": "DGB strings", "question": "What are the common triad shapes on DGB?"},

    # ── Scales ──
    {"category": "Scales", "topic": "Minor pentatonic", "question": "How do I play the minor pentatonic scale?"},
    {"category": "Scales", "topic": "Minor pentatonic", "question": "Show me the minor pentatonic box pattern"},
    {"category": "Scales", "topic": "Minor pentatonic", "question": "What is the pentatonic scale for soloing?"},
    {"category": "Scales", "topic": "Minor pentatonic", "question": "Can you show me the minor pentatonic scale shape?"},
    {"category": "Scales", "topic": "Minor pentatonic", "question": "Where do I start with minor pentatonic on guitar?"},
    {"category": "Scales", "topic": "Minor pentatonic", "question": "How do guitar players use the minor pentatonic scale?"},

    {"category": "Scales", "topic": "Major pentatonic", "question": "Show me the major pentatonic scale"},
    {"category": "Scales", "topic": "Major pentatonic", "question": "How do I play major pentatonic on guitar?"},
    {"category": "Scales", "topic": "Major pentatonic", "question": "What's the difference between major and minor pentatonic?"},
    {"category": "Scales", "topic": "Major pentatonic", "question": "Can you show me the major pentatonic pattern on guitar?"},
    {"category": "Scales", "topic": "Major pentatonic", "question": "How does the major pentatonic scale work?"},
    {"category": "Scales", "topic": "Major pentatonic", "question": "Where do I play major pentatonic on the neck?"},

    {"category": "Scales", "topic": "Blues scale", "question": "How do I play the blues scale?"},
    {"category": "Scales", "topic": "Blues scale", "question": "Show me the blues scale pattern in A"},
    {"category": "Scales", "topic": "Blues scale", "question": "What note makes the blues scale different from pentatonic?"},
    {"category": "Scales", "topic": "Blues scale", "question": "Can you show me the blues scale on guitar?"},
    {"category": "Scales", "topic": "Blues scale", "question": "How is the blues scale different from minor pentatonic?"},
    {"category": "Scales", "topic": "Blues scale", "question": "Where does the extra blues note go?"},

    # ── Techniques ──
    {"category": "Techniques", "topic": "Strumming", "question": "What are some basic strumming patterns?"},
    {"category": "Techniques", "topic": "Strumming", "question": "How do I strum a guitar properly?"},
    {"category": "Techniques", "topic": "Strumming", "question": "Show me a beginner strumming pattern"},
    {"category": "Techniques", "topic": "Strumming", "question": "Can you show me some easy strumming patterns?"},
    {"category": "Techniques", "topic": "Strumming", "question": "How should a beginner practice strumming?"},
    {"category": "Techniques", "topic": "Strumming", "question": "What's a simple strum pattern I can start with?"},

    {"category": "Techniques", "topic": "Palm muting", "question": "How do I palm mute on guitar?"},
    {"category": "Techniques", "topic": "Palm muting", "question": "What is palm muting and how do I do it?"},
    {"category": "Techniques", "topic": "Palm muting", "question": "How do I get that chunky muted sound?"},
    {"category": "Techniques", "topic": "Palm muting", "question": "Can you show me how to palm mute correctly?"},
    {"category": "Techniques", "topic": "Palm muting", "question": "Where should my picking hand sit for palm muting?"},
    {"category": "Techniques", "topic": "Palm muting", "question": "How do I get a tight palm-muted sound?"},

    {"category": "Techniques", "topic": "Hammer-ons/pull-offs", "question": "How do I do hammer-ons and pull-offs?"},
    {"category": "Techniques", "topic": "Hammer-ons/pull-offs", "question": "What is a hammer-on?"},
    {"category": "Techniques", "topic": "Hammer-ons/pull-offs", "question": "Explain legato technique on guitar"},
    {"category": "Techniques", "topic": "Hammer-ons/pull-offs", "question": "Can you explain hammer-ons and pull-offs simply?"},
    {"category": "Techniques", "topic": "Hammer-ons/pull-offs", "question": "How do I practice hammer-ons and pull-offs cleanly?"},
    {"category": "Techniques", "topic": "Hammer-ons/pull-offs", "question": "What's the difference between a hammer-on and a pull-off?"},

    {"category": "Techniques", "topic": "Bending", "question": "How do I bend strings on guitar?"},
    {"category": "Techniques", "topic": "Bending", "question": "What's the proper technique for string bending?"},
    {"category": "Techniques", "topic": "Bending", "question": "Why are my bends sharp?"},
    {"category": "Techniques", "topic": "Bending", "question": "Can you show me how to bend notes in tune?"},
    {"category": "Techniques", "topic": "Bending", "question": "Why do my string bends sound off?"},
    {"category": "Techniques", "topic": "Bending", "question": "How do I control bends better on guitar?"},

    {"category": "Techniques", "topic": "Alternate picking", "question": "What is alternate picking?"},
    {"category": "Techniques", "topic": "Alternate picking", "question": "How do I alternate pick faster?"},
    {"category": "Techniques", "topic": "Alternate picking", "question": "Explain down-up picking technique"},
    {"category": "Techniques", "topic": "Alternate picking", "question": "Can you explain alternate picking for beginners?"},
    {"category": "Techniques", "topic": "Alternate picking", "question": "How do I get smoother with down-up picking?"},
    {"category": "Techniques", "topic": "Alternate picking", "question": "What's the best way to practice alternate picking?"},

    {"category": "Techniques", "topic": "Slides", "question": "How do I do slides on guitar?"},
    {"category": "Techniques", "topic": "Slides", "question": "What is a slide technique?"},
    {"category": "Techniques", "topic": "Slides", "question": "How do I slide between notes on the fretboard?"},
    {"category": "Techniques", "topic": "Slides", "question": "Can you show me how to slide into notes?"},
    {"category": "Techniques", "topic": "Slides", "question": "How do I practice slides cleanly on guitar?"},
    {"category": "Techniques", "topic": "Slides", "question": "What's the right way to do a slide on the fretboard?"},

    # ── Music Theory ──
    {"category": "Music Theory", "topic": "Chord formulas", "question": "What are chord formulas and how are chords built?"},
    {"category": "Music Theory", "topic": "Chord formulas", "question": "How do you construct a major chord from intervals?"},
    {"category": "Music Theory", "topic": "Chord formulas", "question": "What intervals make up a minor chord?"},
    {"category": "Music Theory", "topic": "Chord formulas", "question": "How are major and minor chords built?"},
    {"category": "Music Theory", "topic": "Chord formulas", "question": "Can you explain chord formulas in a simple way?"},
    {"category": "Music Theory", "topic": "Chord formulas", "question": "What notes make up a basic chord?"},

    {"category": "Music Theory", "topic": "I-IV-V", "question": "Explain the I-IV-V chord progression"},
    {"category": "Music Theory", "topic": "I-IV-V", "question": "What is a 1-4-5 progression?"},
    {"category": "Music Theory", "topic": "I-IV-V", "question": "Show me a I-IV-V in the key of G"},
    {"category": "Music Theory", "topic": "I-IV-V", "question": "Can you explain a 1-4-5 progression in simple terms?"},
    {"category": "Music Theory", "topic": "I-IV-V", "question": "What chords make up a I-IV-V progression?"},
    {"category": "Music Theory", "topic": "I-IV-V", "question": "How does a I-IV-V work in a key?"},

    {"category": "Music Theory", "topic": "I-V-vi-IV", "question": "What is the I-V-vi-IV progression?"},
    {"category": "Music Theory", "topic": "I-V-vi-IV", "question": "What's the most common pop chord progression?"},
    {"category": "Music Theory", "topic": "I-V-vi-IV", "question": "Show me the 1-5-6-4 progression"},
    {"category": "Music Theory", "topic": "I-V-vi-IV", "question": "Can you explain the 1-5-6-4 progression?"},
    {"category": "Music Theory", "topic": "I-V-vi-IV", "question": "What chords are in a I-V-vi-IV progression?"},
    {"category": "Music Theory", "topic": "I-V-vi-IV", "question": "Why is the I-V-vi-IV progression used so much?"},

    {"category": "Music Theory", "topic": "CAGED", "question": "What is the CAGED system?"},
    {"category": "Music Theory", "topic": "CAGED", "question": "How does CAGED help me learn the fretboard?"},
    {"category": "Music Theory", "topic": "CAGED", "question": "Explain the CAGED chord shapes"},
    {"category": "Music Theory", "topic": "CAGED", "question": "Can you explain the CAGED system simply?"},
    {"category": "Music Theory", "topic": "CAGED", "question": "How do the CAGED shapes connect across the neck?"},
    {"category": "Music Theory", "topic": "CAGED", "question": "Why do guitar players use the CAGED system?"},

    {"category": "Music Theory", "topic": "Key chords", "question": "What chords are in the key of G?"},
    {"category": "Music Theory", "topic": "Key chords", "question": "Show me the diatonic chords in D major"},
    {"category": "Music Theory", "topic": "Key chords", "question": "What is a key signature chart for guitar?"},
    {"category": "Music Theory", "topic": "Key chords", "question": "What chords naturally belong in a key?"},
    {"category": "Music Theory", "topic": "Key chords", "question": "Can you show me the chords that fit in a major key?"},
    {"category": "Music Theory", "topic": "Key chords", "question": "How do I figure out what chords are in a key?"},

    # ── Gear & Setup ──
    {"category": "Gear & Setup", "topic": "String gauges", "question": "What string gauges should I use?"},
    {"category": "Gear & Setup", "topic": "String gauges", "question": "What's the difference between 9s and 10s?"},
    {"category": "Gear & Setup", "topic": "String gauges", "question": "Are light or heavy strings better for beginners?"},
    {"category": "Gear & Setup", "topic": "String gauges", "question": "How do I choose the right string gauge?"},
    {"category": "Gear & Setup", "topic": "String gauges", "question": "Which guitar strings should a beginner start with?"},
    {"category": "Gear & Setup", "topic": "String gauges", "question": "Should I use lighter or heavier strings?"},

    {"category": "Gear & Setup", "topic": "Pick thickness", "question": "What pick thickness should I use?"},
    {"category": "Gear & Setup", "topic": "Pick thickness", "question": "Does pick thickness matter?"},
    {"category": "Gear & Setup", "topic": "Pick thickness", "question": "What's the best pick for a beginner?"},
    {"category": "Gear & Setup", "topic": "Pick thickness", "question": "How do I choose the right guitar pick thickness?"},
    {"category": "Gear & Setup", "topic": "Pick thickness", "question": "Should I use a thin or thick pick?"},
    {"category": "Gear & Setup", "topic": "Pick thickness", "question": "What kind of pick should a beginner use?"},

    {"category": "Gear & Setup", "topic": "Restringing", "question": "How do I restring an electric guitar?"},
    {"category": "Gear & Setup", "topic": "Restringing", "question": "What's the right way to change guitar strings?"},
    {"category": "Gear & Setup", "topic": "Restringing", "question": "My strings are old, how do I put new ones on?"},
    {"category": "Gear & Setup", "topic": "Restringing", "question": "Can you walk me through changing guitar strings?"},
    {"category": "Gear & Setup", "topic": "Restringing", "question": "How do I put a fresh set of strings on my guitar?"},
    {"category": "Gear & Setup", "topic": "Restringing", "question": "What's the easiest way to restring an electric guitar?"},

    {"category": "Gear & Setup", "topic": "Tuning", "question": "How do I tune my guitar to standard tuning?"},
    {"category": "Gear & Setup", "topic": "Tuning", "question": "What are the reference pitches for each string?"},
    {"category": "Gear & Setup", "topic": "Tuning", "question": "What is 440 Hz tuning?"},
    {"category": "Gear & Setup", "topic": "Tuning", "question": "Can you show me how to tune a guitar by string?"},
    {"category": "Gear & Setup", "topic": "Tuning", "question": "What notes should each guitar string be tuned to?"},
    {"category": "Gear & Setup", "topic": "Tuning", "question": "How do I get my guitar into standard tuning?"},

    # ── Practice ──
    {"category": "Practice", "topic": "Practice routine", "question": "How should I structure my guitar practice sessions?"},
    {"category": "Practice", "topic": "Practice routine", "question": "What's a good daily practice routine for guitar?"},
    {"category": "Practice", "topic": "Practice routine", "question": "How do I get better at guitar faster?"},
    {"category": "Practice", "topic": "Practice routine", "question": "Can you help me build a guitar practice routine?"},
    {"category": "Practice", "topic": "Practice routine", "question": "What should I practice each day on guitar?"},
    {"category": "Practice", "topic": "Practice routine", "question": "How can I make my guitar practice more effective?"},

    # ── Meta ──
    {"category": "Meta", "topic": "Capabilities", "question": "What topics can you help me with?"},
    {"category": "Meta", "topic": "Capabilities", "question": "What do you know about?"},
    {"category": "Meta", "topic": "Capabilities", "question": "Show me everything you can teach me"},
    {"category": "Meta", "topic": "Capabilities", "question": "What kinds of guitar stuff can you help me learn?"},
    {"category": "Meta", "topic": "Capabilities", "question": "What can you teach me about guitar?"},
    {"category": "Meta", "topic": "Capabilities", "question": "What are all the guitar topics you can help with?"},
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    is_prod = "--prod" in sys.argv
    env_label = "PROD" if is_prod else "LOCAL"

    # Load bot config for thresholds
    config = load_bot_config(BOT_ID)
    rag_config = config.get("bot", {}).get("rag", {})
    top_k = rag_config.get("top_k", 10)
    similarity_threshold = rag_config.get("similarity_threshold", 0.4)
    confidence_threshold = config.get("bot", {}).get("agentic", {}).get("confidence_threshold", 0.6)

    print()
    print("=" * 70)
    print(f"  Knowledge Coverage Regression Test — {env_label} (retrieval-only)")
    print(f"  Bot: {BOT_ID}")
    print(f"  Questions: {len(QUESTIONS)}")
    print(f"  Similarity threshold: {similarity_threshold}")
    print(f"  Confidence threshold: {confidence_threshold} (FAIL below this)")
    print("=" * 70)
    print()

    results = []
    passed = 0
    failed = 0
    errors = 0
    topic_scores = {}

    current_category = ""
    current_topic = ""
    total = len(QUESTIONS)
    t_start = time.time()

    for idx, q in enumerate(QUESTIONS):
        # Print category/topic headers
        if q["category"] != current_category:
            current_category = q["category"]
            print(f"\n  ── {current_category} ──")
        topic = q.get("topic", "")
        if topic != current_topic:
            current_topic = topic
            print(f"  [{current_topic}]")

        short_q = q["question"][:52]

        try:
            chunks = retrieve_relevant_chunks(
                bot_id=BOT_ID,
                query=q["question"],
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )

            top_score = chunks[0]["similarity"] if chunks else 0.0
            is_pass = top_score >= confidence_threshold

            result = {
                "category": q["category"],
                "topic": topic,
                "question": q["question"],
                "passed": is_pass,
                "top_score": round(top_score, 4),
                "chunk_count": len(chunks),
            }

            if chunks:
                result["top_match"] = {
                    "id": chunks[0]["id"],
                    "category": chunks[0]["category"],
                    "heading": chunks[0].get("heading", ""),
                }

            results.append(result)

            if is_pass:
                passed += 1
                print(f"    [{idx + 1:3d}/{total}] {short_q:54s} PASS  score={top_score:.3f}")
            else:
                failed += 1
                heading = chunks[0].get("heading", "")[:40] if chunks else "no matches"
                print(f"    [{idx + 1:3d}/{total}] {short_q:54s} FAIL  score={top_score:.3f}  [{heading}]")

        except Exception as e:
            errors += 1
            results.append({
                "category": q["category"],
                "topic": topic,
                "question": q["question"],
                "passed": False,
                "error": str(e),
            })
            print(f"    [{idx + 1:3d}/{total}] {short_q:54s} ERROR  {e}")

        # Track per-topic scores
        topic_key = f"{q['category']}: {topic}"
        if topic_key not in topic_scores:
            topic_scores[topic_key] = []
        if "top_score" in result:
            topic_scores[topic_key].append(result["top_score"])

    elapsed = time.time() - t_start

    # Build topic summary
    topic_summary = []
    for topic_key, scores in topic_scores.items():
        topic_summary.append({
            "topic": topic_key,
            "min_score": round(min(scores), 4),
            "avg_score": round(sum(scores) / len(scores), 4),
            "max_score": round(max(scores), 4),
            "variants": len(scores),
        })
    topic_summary.sort(key=lambda x: x["min_score"])

    # Write results file
    os.makedirs(RESULTS_DIR, exist_ok=True)
    failures = [r for r in results if not r.get("passed", False)]

    output = {
        "run_date": datetime.now().isoformat(),
        "environment": env_label,
        "bot_id": BOT_ID,
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": f"{(passed / total) * 100:.1f}%",
        "elapsed_seconds": round(elapsed, 1),
        "confidence_threshold": confidence_threshold,
        "topic_summary": topic_summary,
        "results": results,
    }
    if failures:
        output["failures_summary"] = failures

    with open(RESULTS_FILE, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, width=200)

    # Print summary
    print()
    print("=" * 70)
    print(f"  PASSED: {passed}  FAILED: {failed}  ERRORS: {errors}  ({(passed / total) * 100:.1f}%)")
    print(f"  Time: {elapsed:.1f}s  |  Results: {RESULTS_FILE}")
    print("=" * 70)

    # Topic summary table
    print()
    print(f"  {'TOPIC':<40s} {'MIN':>6s} {'AVG':>6s} {'MAX':>6s}")
    print(f"  {'─' * 40} {'─' * 6} {'─' * 6} {'─' * 6}")
    for ts in topic_summary:
        flag = " ◀" if ts["min_score"] < confidence_threshold else ""
        print(f"  {ts['topic']:<40s} {ts['min_score']:>6.3f} {ts['avg_score']:>6.3f} {ts['max_score']:>6.3f}{flag}")
    print()

    below_threshold = [ts for ts in topic_summary if ts["min_score"] < confidence_threshold]
    if below_threshold:
        print(f"  WARNING: {len(below_threshold)} topic(s) below {confidence_threshold} confidence threshold")
        print()

    # Print failures at the end
    if failures:
        print("  ━━ FAILURES ━━")
        print()
        for f_item in failures:
            score = f_item.get("top_score", "?")
            match_info = ""
            if "top_match" in f_item:
                match_info = f" → {f_item['top_match'].get('heading', f_item['top_match'].get('id', ''))}"
            print(f"    {score:>6} | {f_item['category']}: {f_item.get('topic', '')}")
            print(f"           {f_item['question']}{match_info}")
            if "error" in f_item:
                print(f"           ERROR: {f_item['error']}")
            print()

    sys.exit(0 if failed == 0 and errors == 0 else 1)


if __name__ == "__main__":
    main()
